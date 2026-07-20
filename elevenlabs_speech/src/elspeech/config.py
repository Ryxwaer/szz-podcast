"""Configuration + environment loading for the standalone ElevenLabs renderer.

Self-contained: reads this folder's own ``config.yaml`` (engine settings) and
``.env`` (``ELEVENLABS_API_KEY``). Relative paths resolve against this folder, so
``../transcripts`` and ``../audio`` point at the shared repo-root directories.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
ENV_PATH = ROOT / ".env"
REPO_ENV_PATH = ROOT.parent / ".env"  # shared repo-root .env (fallback)


def load_env() -> None:
    # Backend-local .env wins; the repo-root .env fills in anything it doesn't set
    # (load_dotenv defaults to override=False, so the first load takes precedence).
    load_dotenv(ENV_PATH)
    load_dotenv(REPO_ENV_PATH)


def load_config(path: str | Path | None = None) -> dict:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (ROOT / p)


def paths(cfg: dict) -> dict[str, Path]:
    return {key: resolve_path(value) for key, value in cfg["paths"].items()}


def require_api_key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing ELEVENLABS_API_KEY. Copy .env.example to .env and add your key "
            "from https://elevenlabs.io/app/settings/api-keys"
        )
    return key
