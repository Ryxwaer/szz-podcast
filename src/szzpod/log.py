"""UTF-8, colorized console logging helpers (termcolor)."""
from __future__ import annotations

import sys

from termcolor import cprint


def _ensure_utf8() -> None:
    # Force UTF-8 and line buffering so progress prints live even when stdout is
    # captured/piped (a pipe defaults to block buffering -> output only at exit).
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", line_buffering=True)
            except (ValueError, OSError):
                pass


_ensure_utf8()


def info(msg: str) -> None:
    cprint(msg, "cyan", flush=True)


def step(msg: str) -> None:
    cprint(msg, "blue", attrs=["bold"], flush=True)


def ok(msg: str) -> None:
    cprint(msg, "green", flush=True)


def warn(msg: str) -> None:
    cprint(msg, "yellow", file=sys.stderr, flush=True)


def err(msg: str) -> None:
    cprint(msg, "red", attrs=["bold"], file=sys.stderr, flush=True)
