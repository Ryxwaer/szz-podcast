"""Orchestration: transcript -> ElevenLabs chunks (cached) -> assembled episode mp3.

No state file - chunk caching makes generation resumable and the seed is derived
deterministically from config + name. Upload to R2 and embedding into the note are
the root ``szzpod`` tool's job, not this renderer's.
"""
from __future__ import annotations

import tempfile
from math import log10 as _log10
from pathlib import Path

from . import audio as audio_mod
from . import config, log, tts
from .transcript import chunk as chunk_turns
from .transcript import parse as parse_transcript
from .transcript import validate as validate_transcript
from .tts import QuotaExceeded, derive_seed


def transcript_path(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["transcripts"] / f"{name}.txt"


def audio_path(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["audio"] / f"{name}.mp3"


def cache_dir(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["cache"] / name


def render(cfg: dict, name: str, *, reassemble: bool = False) -> Path:
    """Render (or reassemble from cache) the mp3 for ``name``; return its path."""
    log.step(f"elevenlabs tts + assemble: {name}")
    tpath = transcript_path(cfg, name)
    if not tpath.exists():
        raise FileNotFoundError(f"Transcript missing: {tpath}")

    text = tpath.read_text(encoding="utf-8")
    turns = parse_transcript(text)
    if not turns:
        raise ValueError("Transcript has no Person1:/Person2: turns.")

    result = validate_transcript(text)
    for w in result.warnings:
        log.warn(f"  warning: {w}")

    max_chars = int(cfg.get("max_chars_per_request", 1800))
    chunks = chunk_turns(turns, max_chars)
    chars_per_chunk = [sum(len(line) for _, line in ch) for ch in chunks]
    total_chars = sum(chars_per_chunk)
    sample_rate, bitrate = audio_mod.format_params(cfg["output_format"])
    cache = cache_dir(cfg, name)
    log.info(f"  turns: {len(turns)} | chunks: {len(chunks)} | chars: {total_chars}")

    silence = None
    pause = float(cfg.get("pause_between_chunks", 0.0))
    if pause > 0:
        cache.mkdir(parents=True, exist_ok=True)
        silence = cache / "silence.mp3"
        if not silence.exists():
            audio_mod.make_silence(pause, sample_rate, bitrate, silence)

    settings = cfg.get("settings") or None
    language_code = cfg.get("language_code") or None
    voices = cfg["voices"]
    seed = derive_seed(int(cfg.get("seed", 0)), name)
    new_chunks = cached_chunks = 0

    if reassemble:
        chunk_files = tts.cached_chunks(cache)
        if not chunk_files:
            raise FileNotFoundError(f"No cached chunks in {cache} to reassemble.")
        cached_chunks = len(chunk_files)
        log.info(f"  reassembling from {len(chunk_files)} cached chunks (no API)")
    else:
        api_key = config.require_api_key()

        def on_progress(i: int, total: int, cached: bool) -> None:
            nonlocal new_chunks, cached_chunks
            if cached:
                cached_chunks += 1
            else:
                new_chunks += 1
            log.info(f"  [{i}/{total}] {'cache' if cached else 'API '} | "
                     f"{len(chunks[i - 1])} replík, {chars_per_chunk[i - 1]} zn.")

        try:
            chunk_files = tts.generate(
                chunks, cache=cache, voices=voices,
                model_id=cfg["model_id"], output_format=cfg["output_format"],
                settings=settings, seed=seed, api_key=api_key,
                language_code=language_code, on_progress=on_progress,
            )
        except QuotaExceeded:
            log.err(
                "  ElevenLabs quota exceeded. Cached chunks are kept; rerun the same "
                "command after topping up to generate only what is missing."
            )
            raise

    out = audio_path(cfg, name)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="elspeech_"))
    target_lufs = float(cfg.get("target_lufs", -18.0))
    normalize = bool(cfg.get("normalize", True))
    dynamics = bool(cfg.get("dynamics", True))
    applied = audio_mod.assemble(
        chunk_files, silence, sample_rate, bitrate, out, tmp, normalize, target_lufs, dynamics,
    )
    log.ok(f"  done -> {out}")
    if normalize and applied:
        name_by_id = {vid: spk for spk, vid in voices.items()}
        per_voice: dict[str, list[float]] = {}
        for chunk_gains in applied:
            for vid, g in chunk_gains.items():
                per_voice.setdefault(name_by_id.get(vid, vid), []).append(20 * _log10(g))
        for spk, dbs in per_voice.items():
            log.info(f"  leveling {spk}: priemer {sum(dbs)/len(dbs):+.1f} dB "
                     f"(rozsah {min(dbs):+.1f}..{max(dbs):+.1f}), cieľ {target_lufs:.0f} LUFS")
    log.step("ElevenLabs súhrn:")
    log.info(f"  chunkov: {len(chunks)} (nové: {new_chunks}, z cache: {cached_chunks})")
    log.info(f"  znakov: {total_chars}")
    return out
