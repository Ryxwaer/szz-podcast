"""Configuration + environment loading.

Resolves the repo root, loads `.env`, and reads `config.yaml`. Relative paths in
the config are resolved against the repo root; absolute paths are kept as-is.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
ENV_PATH = ROOT / ".env"


def load_env() -> None:
    load_dotenv(ENV_PATH)


def load_config(path: str | Path | None = None) -> dict:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(value: str | Path) -> Path:
    """Resolve a config path against the repo root (absolute paths untouched)."""
    p = Path(value)
    return p if p.is_absolute() else (ROOT / p)


def paths(cfg: dict) -> dict[str, Path]:
    return {key: resolve_path(value) for key, value in cfg["paths"].items()}


def r2_account_id(cfg: dict) -> str:
    return os.getenv("CLOUDFLARE_ACCOUNT_ID") or cfg["r2"]["account_id"]
