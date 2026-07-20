"""Configuration + environment loading for the standalone Azure renderer.

Resolves this package's own root (the azure_speech/ dir), loads its `.env`, and
reads its `config.yaml`. Relative config paths resolve against that root; absolute
paths are kept as-is.
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


def require_credentials() -> tuple[str, str]:
    """Return (key, region) from the environment or fail with a clear message."""
    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not key or not region:
        raise RuntimeError(
            "Missing AZURE_SPEECH_KEY / AZURE_SPEECH_REGION. Copy .env.example to "
            ".env and fill them in (Portal -> Speech resource -> Keys and Endpoint)."
        )
    return key, region
