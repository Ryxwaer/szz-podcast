"""Configuration + environment loading for the standalone Gemini renderer."""
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


def _collect_keys(prefix: str) -> list[str]:
    """Gather API keys for ``prefix`` from the environment, in a stable order.

    Supports two ways to supply several keys (they combine):
      - a comma-separated list in one var:  GEMINI_API_KEY=key1,key2,key3
      - numbered variants:                  GEMINI_API_KEY_2=..., GEMINI_API_KEY_3=...
    Duplicates are removed while preserving first-seen order.
    """
    names = [n for n in os.environ if n == prefix or n.startswith(prefix + "_")]

    def sort_key(name: str) -> tuple:
        if name == prefix:
            return (0, 0, "")
        suffix = name[len(prefix) + 1:]
        return (1, int(suffix), "") if suffix.isdigit() else (2, 0, suffix)

    found: list[str] = []
    seen: set[str] = set()
    for name in sorted(names, key=sort_key):
        for part in os.environ.get(name, "").replace("\n", ",").split(","):
            key = part.strip()
            if key and key not in seen:
                seen.add(key)
                found.append(key)
    return found


def require_api_keys() -> list[str]:
    """All configured Gemini API keys (>=1). Rotated on rate-limit during a run."""
    keys = _collect_keys("GEMINI_API_KEY")
    if not keys:
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Copy .env.example to .env and add a key from "
            "https://aistudio.google.com/apikey (you can list several, comma-separated "
            "or as GEMINI_API_KEY_2, GEMINI_API_KEY_3, ... to cycle on rate limits)."
        )
    return keys


def require_api_key() -> str:
    return require_api_keys()[0]
