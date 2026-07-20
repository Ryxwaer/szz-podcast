"""The backend-agnostic pipeline steps: locate artifacts and upload to R2.

Audio generation lives in the per-backend renderers (elevenlabs_speech /
gemini_speech / azure_speech). This module only resolves paths from the global
config and uploads the finished mp3; the orchestrator owns names, R2 keys, and
embedding into the note.
"""
from __future__ import annotations

from pathlib import Path

from . import config, log, r2


def transcript_path(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["transcripts"] / f"{name}.txt"


def audio_path(cfg: dict, name: str) -> Path:
    return config.paths(cfg)["audio"] / f"{name}.mp3"


def upload(cfg: dict, name: str, r2_key: str) -> str:
    """Upload the rendered mp3 to R2 under ``r2_key``; print and return the URL."""
    log.step(f"upload to R2: {name}")
    out = audio_path(cfg, name)
    if not out.exists():
        raise FileNotFoundError(f"Audio not found: {out} (run `tts {name}` first).")

    account_id = config.r2_account_id(cfg)
    r2.upload(out, r2_key, bucket=cfg["r2"]["bucket"], account_id=account_id)
    url = f"{cfg['r2']['base_url']}/{r2_key}"
    log.ok(f"  uploaded -> {url}")
    print(url, flush=True)  # plain stdout line so the orchestrator can capture the URL
    return url
