"""Azure AI Speech (Text-to-Speech REST) with per-chunk file caching.

Each chunk becomes one SSML document containing alternating ``<voice>`` blocks (one
per turn), so a single request renders a slice of the two-speaker dialogue. Chunks
are cached by a content hash so reruns only fetch what is missing - including after
a rate-limit (HTTP 429) interrupts a run on the Free F0 tier.

Docs: https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from xml.sax.saxutils import escape

import requests

from .transcript import Turn

ENDPOINT_TMPL = "https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
USER_AGENT = "azspeech/0.1"
SSML_NS = "http://www.w3.org/2001/10/synthesis"

# Pacing tags allowed in transcripts -> SSML break durations (ms come from config).
_PAUSE_TAGS = {"short pause": "short_pause_ms", "pause": "pause_ms", "long pause": "long_pause_ms"}
_TAG_RE = re.compile(r"\[([^\[\]]+)\]")
_MAX_RETRIES = 4


class SynthError(RuntimeError):
    """Azure TTS request failed."""


class RateLimited(SynthError):
    """Azure returned HTTP 429 after exhausting retries; cached chunks are kept."""


def _render_text(text: str, breaks: dict) -> str:
    """XML-escape a turn and convert pacing tags to <break/>; strip unknown tags."""
    escaped = escape(text)

    def repl(m: re.Match) -> str:
        key = _PAUSE_TAGS.get(m.group(1).strip().lower())
        if key is None:
            return ""  # never speak a stray "[something]"
        return f'<break time="{int(breaks.get(key, 500))}ms"/>'

    return _TAG_RE.sub(repl, escaped)


def build_ssml(chunk: list[Turn], *, voices: dict[str, str], language: str,
               prosody: dict | None, breaks: dict) -> str:
    """Build one SSML document for a chunk of alternating-speaker turns."""
    rate = (prosody or {}).get("rate", "0%")
    pitch = (prosody or {}).get("pitch", "0%")
    use_prosody = rate not in ("", "0%", None) or pitch not in ("", "0%", None)

    blocks: list[str] = []
    for speaker, text in chunk:
        inner = _render_text(text, breaks)
        if use_prosody:
            inner = f'<prosody rate="{rate}" pitch="{pitch}">{inner}</prosody>'
        blocks.append(f'<voice name="{voices[speaker]}">{inner}</voice>')

    return (
        f'<speak version="1.0" xmlns="{SSML_NS}" xml:lang="{language}">'
        + "".join(blocks)
        + "</speak>"
    )


def _cache_path(cache: Path, index: int, ssml: str, output_format: str) -> Path:
    key = f"{output_format}|{ssml}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return cache / f"chunk_{index:03d}_{digest}.mp3"


def _request(ssml: str, *, key: str, region: str, output_format: str, out_path: Path) -> None:
    url = ENDPOINT_TMPL.format(region=region)
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": output_format,
        "User-Agent": USER_AGENT,
    }
    for attempt in range(_MAX_RETRIES):
        r = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=180)
        if r.status_code == 200:
            out_path.write_bytes(r.content)
            return
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 2 ** attempt))
            if attempt < _MAX_RETRIES - 1:
                time.sleep(wait)
                continue
            raise RateLimited(
                f"Azure rate limit (429) after {_MAX_RETRIES} tries. Cached chunks "
                "are kept; rerun the same command to fetch only what is missing."
            )
        if r.status_code == 401:
            raise SynthError("Azure auth failed (401): check AZURE_SPEECH_KEY / region.")
        raise SynthError(f"Azure TTS {r.status_code}: {r.text[:400]}")


def generate(chunks: list[list[Turn]], *, cache: Path, voices: dict[str, str],
             language: str, prosody: dict | None, breaks: dict, output_format: str,
             key: str, region: str, on_progress=None) -> list[Path]:
    """Generate (or reuse cached) audio for every chunk; return chunk file paths."""
    cache.mkdir(parents=True, exist_ok=True)
    total = len(chunks)
    files: list[Path] = []
    for i, chunk in enumerate(chunks, 1):
        ssml = build_ssml(chunk, voices=voices, language=language,
                          prosody=prosody, breaks=breaks)
        cf = _cache_path(cache, i, ssml, output_format)
        cached = cf.exists() and cf.stat().st_size > 0
        if not cached:
            _request(ssml, key=key, region=region, output_format=output_format, out_path=cf)
        if on_progress:
            on_progress(i, total, cached)
        files.append(cf)
    return files


def cached_chunks(cache: Path) -> list[Path]:
    return sorted(cache.glob("chunk_*.mp3"))
