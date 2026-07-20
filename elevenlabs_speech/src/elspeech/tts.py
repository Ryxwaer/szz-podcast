"""ElevenLabs Text to Dialogue (Eleven v3) with per-chunk file caching.

Each chunk is one call to the with-timestamps dialogue endpoint, which natively
handles voice alternation and prosody and returns per-voice ``voice_segments``
(used later for ducking). Chunks are cached by a content hash so reruns only
generate what is missing - including after a quota exhaustion mid-run.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import requests

from .transcript import Turn

DIALOGUE_URL = "https://api.elevenlabs.io/v1/text-to-dialogue/with-timestamps"


class QuotaExceeded(RuntimeError):
    """ElevenLabs quota exhausted - generation cannot continue."""


def derive_seed(base_seed: int, name: str) -> int:
    """Deterministic per-episode seed (stable across reruns -> stable cache)."""
    h = hashlib.sha1(f"{base_seed}|{name}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _chunk_inputs(chunk: list[Turn], voices: dict[str, str]) -> list[dict]:
    return [{"text": text, "voice_id": voices[speaker]} for speaker, text in chunk]


def _cache_path(cache: Path, index: int, inputs: list[dict], model_id: str,
                output_format: str, settings: dict | None, seed: int) -> Path:
    key = "|".join([
        model_id,
        output_format,
        json.dumps(settings, ensure_ascii=False, sort_keys=True),
        str(seed),
        json.dumps(inputs, ensure_ascii=False),
    ])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return cache / f"chunk_{index:03d}_{digest}.mp3"


def _request(api_key: str, inputs: list[dict], model_id: str, output_format: str,
             settings: dict | None, seed: int, out_path: Path, segs_path: Path,
             language_code: str | None = None) -> None:
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body: dict = {"inputs": inputs, "model_id": model_id, "seed": seed}
    if settings:
        body["settings"] = settings
    if language_code:
        body["language_code"] = language_code
    params = {"output_format": output_format}
    r = requests.post(DIALOGUE_URL, headers=headers, json=body, params=params, timeout=180)
    if r.status_code != 200:
        if "quota_exceeded" in r.text:
            raise QuotaExceeded(r.text[:400])
        raise RuntimeError(f"ElevenLabs API {r.status_code}: {r.text[:400]}")
    data = r.json()
    out_path.write_bytes(base64.b64decode(data["audio_base64"]))
    segs_path.write_text(
        json.dumps(data.get("voice_segments") or [], ensure_ascii=False), encoding="utf-8"
    )


def generate(chunks: list[list[Turn]], *, cache: Path, voices: dict[str, str],
             model_id: str, output_format: str, settings: dict | None, seed: int,
             api_key: str, language_code: str | None = None,
             on_progress=None) -> list[Path]:
    """Generate (or reuse cached) audio for every chunk; return chunk file paths.

    ``on_progress(index, total, from_cache)`` is called per chunk if provided.
    Raises ``QuotaExceeded`` if credits run out; already-cached chunks remain.

    ``language_code`` is passed to the API but intentionally kept out of the cache
    key, so toggling it never invalidates existing chunks.
    """
    cache.mkdir(parents=True, exist_ok=True)
    total = len(chunks)
    files: list[Path] = []
    for i, chunk in enumerate(chunks, 1):
        inputs = _chunk_inputs(chunk, voices)
        cf = _cache_path(cache, i, inputs, model_id, output_format, settings, seed)
        cached = cf.exists() and cf.stat().st_size > 0 and cf.with_suffix(".json").exists()
        if not cached:
            _request(api_key, inputs, model_id, output_format, settings, seed,
                     cf, cf.with_suffix(".json"), language_code=language_code)
        if on_progress:
            on_progress(i, total, cached)
        files.append(cf)
    return files


def cached_chunks(cache: Path) -> list[Path]:
    return sorted(cache.glob("chunk_*.mp3"))
