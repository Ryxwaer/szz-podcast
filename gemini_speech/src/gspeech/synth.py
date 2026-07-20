"""Gemini multi-speaker TTS (generateContent) with per-chunk WAV caching.

Each chunk is one ``generateContent`` call: the turns are sent verbatim as a labeled
conversation prompt (the transcript text is passed through unchanged - anything in it,
including ``[tags]``, goes to Gemini as-is) and both speakers are bound to Gemini
prebuilt voices via ``multiSpeakerVoiceConfig``. The response carries base64 PCM
(24 kHz, 16-bit mono), which we wrap into a WAV file and cache by content hash so
reruns only fetch what is missing - including after a free-tier rate limit (HTTP 429).

Docs: https://ai.google.dev/gemini-api/docs/speech-generation
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
import wave
from pathlib import Path

import requests

from . import log
from .transcript import Turn

ENDPOINT_TMPL = ("https://generativelanguage.googleapis.com/v1beta/models/"
                 "{model}:generateContent")
_DEFAULT_RATE = 24000
_MAX_RETRIES = 5


class SynthError(RuntimeError):
    """Gemini TTS request failed."""


class RateLimited(SynthError):
    """Gemini returned HTTP 429 after retries; cached chunks are kept."""


class KeyCycler:
    """Rotating pool of API keys, shared across all chunks of a run.

    On a 429 we move to the next key immediately (no wait) as long as another key
    hasn't been tried in the current round; only when every key is rate-limited do
    we back off. The position persists across chunks, so once a key is exhausted we
    keep using the next one instead of hammering the dead one again.
    """

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("KeyCycler needs at least one key.")
        self.keys = keys
        self.i = 0

    @property
    def current(self) -> str:
        return self.keys[self.i]

    @property
    def label(self) -> str:
        return f"#{self.i + 1}/{len(self.keys)}"

    def rotate(self) -> None:
        self.i = (self.i + 1) % len(self.keys)

    def __len__(self) -> int:
        return len(self.keys)


def build_prompt(chunk: list[Turn], *, speakers: dict, style_prompt: str) -> str:
    """Global style prompt + per-speaker directives + turns as ``Alias: verbatim text``.

    The Gemini API has no structured per-speaker style field (speech_config binds only
    speaker name -> voice), so per-speaker guidance is prompt text addressed by name,
    as the docs recommend ("Make Speaker1 sound tired...").
    """
    aliases = {key: spk["alias"] for key, spk in speakers.items()}
    lines = [f"{aliases[speaker]}: {text}" for speaker, text in chunk]
    body = "\n".join(lines)
    parts = []
    if (style_prompt or "").strip():
        parts.append(style_prompt.strip())
    for spk in speakers.values():
        style = (spk.get("style") or "").strip()
        if style:
            parts.append(f"Pokyny pre rečníka {spk['alias']}: {style}.")
    parts.append(body)
    return "\n\n".join(parts)


def _request_body(prompt: str, speakers: dict, language_code: str | None) -> dict:
    speaker_configs = [
        {
            "speaker": spk["alias"],
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": spk["voice"]}},
        }
        for spk in (speakers["person1"], speakers["person2"])
    ]
    speech_config: dict = {
        "multiSpeakerVoiceConfig": {"speakerVoiceConfigs": speaker_configs}
    }
    if language_code:
        speech_config["languageCode"] = language_code
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": speech_config,
        },
    }


def _cache_path(cache: Path, index: int, body: dict, model: str) -> Path:
    key = f"{model}|{json.dumps(body, ensure_ascii=False, sort_keys=True)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return cache / f"chunk_{index:03d}_{digest}.wav"


def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _extract_audio(data: dict) -> tuple[bytes, int]:
    candidates = data.get("candidates") or []
    if not candidates:
        fb = data.get("promptFeedback") or {}
        raise SynthError(f"No audio returned (promptFeedback={fb}).")
    for part in candidates[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            pcm = base64.b64decode(inline["data"])
            mime = inline.get("mimeType") or inline.get("mime_type") or ""
            m = re.search(r"rate=(\d+)", mime)
            return pcm, int(m.group(1)) if m else _DEFAULT_RATE
    raise SynthError("Response contained no inline audio data.")


def _retry_delay(text: str, fallback: float) -> float:
    m = re.search(r'"retryDelay":\s*"(\d+)s"', text)
    return int(m.group(1)) + 1 if m else fallback


def _request(body: dict, *, model: str, keys: KeyCycler, out_path: Path) -> None:
    url = ENDPOINT_TMPL.format(model=model)
    text_retries = 0        # 200 with no audio (model emitted a text token)
    server_retries = 0      # 500/503
    keys_tried = 0          # keys hit by 429 in the current round
    backoffs = 0            # full rounds where every key was rate-limited
    while True:
        headers = {"x-goog-api-key": keys.current, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json=body, timeout=300)

        if r.status_code == 200:
            try:
                pcm, rate = _extract_audio(r.json())
            except SynthError:
                if text_retries < _MAX_RETRIES - 1:
                    text_retries += 1
                    time.sleep(2 ** text_retries)
                    continue
                raise
            out_path.write_bytes(_pcm_to_wav(pcm, rate))
            return

        if r.status_code == 429:
            keys_tried += 1
            if keys_tried < len(keys):
                # Another key may still have quota: switch immediately, no wait.
                log.warn(f"  429 na kľúči {keys.label} - skúšam ďalší kľúč")
                keys.rotate()
                continue
            # Every key is rate-limited this round -> back off, then try again.
            keys_tried = 0
            if backoffs < _MAX_RETRIES:
                wait = _retry_delay(r.text, 2 ** backoffs * 5)
                backoffs += 1
                log.warn(f"  všetky kľúče ({len(keys)}) na 429 - čakám {wait:.0f}s "
                         f"(pokus {backoffs}/{_MAX_RETRIES})")
                time.sleep(wait)
                keys.rotate()
                continue
            raise RateLimited(
                "Gemini rate limit (429): every key is exhausted after retries. Cached "
                "chunks are kept; rerun the same command to fetch only what is missing "
                "(free tier has low per-minute/day limits; add more keys to GEMINI_API_KEY)."
            )

        if r.status_code in (500, 503):
            # Gemini occasionally returns a text token instead of audio -> 500. Docs
            # recommend a simple retry.
            if server_retries < _MAX_RETRIES - 1:
                server_retries += 1
                time.sleep(2 ** server_retries)
                continue
            raise SynthError(f"Gemini API {r.status_code} after retries: {r.text[:300]}")
        if r.status_code in (401, 403):
            raise SynthError(
                f"Gemini auth failed ({r.status_code}) on key {keys.label}: check GEMINI_API_KEY."
            )
        raise SynthError(f"Gemini API {r.status_code}: {r.text[:400]}")


def generate(chunks: list[list[Turn]], *, cache: Path, speakers: dict, style_prompt: str,
             model: str, api_keys: list[str], language_code: str | None = None,
             on_progress=None) -> list[Path]:
    """Generate (or reuse cached) audio for every chunk; return chunk WAV paths.

    ``api_keys`` is a pool of one or more keys; on HTTP 429 we rotate to the next
    key (only backing off once every key is rate-limited). The rotation position is
    shared across chunks, so we don't retry a known-exhausted key on every chunk.
    """
    cache.mkdir(parents=True, exist_ok=True)
    keys = KeyCycler(api_keys)
    total = len(chunks)
    files: list[Path] = []
    for i, chunk in enumerate(chunks, 1):
        prompt = build_prompt(chunk, speakers=speakers, style_prompt=style_prompt)
        body = _request_body(prompt, speakers, language_code)
        cf = _cache_path(cache, i, body, model)
        cached = cf.exists() and cf.stat().st_size > 0
        if not cached:
            _request(body, model=model, keys=keys, out_path=cf)
        if on_progress:
            on_progress(i, total, cached)
        files.append(cf)
    return files


def cached_chunks(cache: Path) -> list[Path]:
    return sorted(cache.glob("chunk_*.wav"))
