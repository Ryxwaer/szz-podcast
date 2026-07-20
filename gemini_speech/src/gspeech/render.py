"""Orchestration: transcript -> Gemini chunks (cached) -> assembled episode mp3."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import audio, config, log, synth
from .transcript import chunk as chunk_turns
from .transcript import parse as parse_transcript


def transcript_path(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["transcripts"] / f"{name}.txt"


def audio_path(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["audio"] / f"{name}.mp3"


def cache_dir(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["cache"] / name


def render(cfg: dict, name: str, *, reassemble: bool = False, limit: int | None = None) -> Path:
    """Render (or reassemble from cache) the mp3 for ``name``; return its path.

    ``limit`` (optional) renders only the first N chunks - handy for a quick test.
    """
    log.step(f"gemini tts + assemble: {name}")
    tpath = transcript_path(cfg, name)
    if not tpath.exists():
        raise FileNotFoundError(f"Transcript missing: {tpath}")

    turns = parse_transcript(tpath.read_text(encoding="utf-8"))
    if not turns:
        raise ValueError("Transcript has no Person1:/Person2: turns.")

    max_chars = int(cfg.get("max_chars_per_request", 1600))
    chunks = chunk_turns(turns, max_chars)
    if limit:
        chunks = chunks[:limit]
        log.warn(f"  test mode: only the first {len(chunks)} chunk(s)")
    chars_per_chunk = [sum(len(line) for _, line in ch) for ch in chunks]
    total_chars = sum(chars_per_chunk)
    cache = cache_dir(cfg, name)
    log.info(f"  turns: {len(turns)} | chunks: {len(chunks)} | chars: {total_chars}")

    new_chunks = cached_chunks = 0
    if reassemble:
        chunk_files = synth.cached_chunks(cache)
        if not chunk_files:
            raise FileNotFoundError(f"No cached chunks in {cache} to reassemble.")
        cached_chunks = len(chunk_files)
        log.info(f"  reassembling from {len(chunk_files)} cached chunks (no API)")
    else:
        api_keys = config.require_api_keys()
        if len(api_keys) > 1:
            log.info(f"  {len(api_keys)} API kľúčov - rotujem pri 429")

        def on_progress(i: int, total: int, was_cached: bool) -> None:
            nonlocal new_chunks, cached_chunks
            if was_cached:
                cached_chunks += 1
            else:
                new_chunks += 1
            log.info(f"  [{i}/{total}] {'cache' if was_cached else 'API '} | "
                     f"{len(chunks[i - 1])} replík, {chars_per_chunk[i - 1]} zn.")

        chunk_files = synth.generate(
            chunks, cache=cache, speakers=cfg["speakers"],
            style_prompt=cfg.get("style_prompt", ""), model=cfg["model"],
            api_keys=api_keys, language_code=cfg.get("language_code") or None,
            on_progress=on_progress,
        )

    out = audio_path(cfg, name)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="gspeech_"))
    audio.assemble(
        chunk_files,
        int(cfg.get("output_sample_rate", 44100)),
        str(cfg.get("output_bitrate", "192k")),
        out, tmp,
        bool(cfg.get("normalize", True)),
        float(cfg.get("target_lufs", -18.0)),
        bool(cfg.get("dynamics", False)),
    )
    log.ok(f"  done -> {out}")
    log.step("Gemini súhrn:")
    log.info(f"  chunkov: {len(chunks)} (nové: {new_chunks}, z cache: {cached_chunks})")
    log.info(f"  znakov: {total_chars}")
    return out
