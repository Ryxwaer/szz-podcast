"""Global orchestration CLI - the backend-agnostic half of the pipeline.

Two commands, nothing more:
  upload    upload the rendered mp3 to R2 under --r2-key, print the public URL
  validate  parse + validate a transcript without calling any API

Audio generation (`tts`) is delegated to a backend renderer
(elevenlabs_speech / gemini_speech / azure_speech) selected by `backend:` in the
repo-root config.yaml and dispatched by ./szzpod. This CLI reads only the global
config (paths, r2); it never talks to a TTS engine.

Names, R2 keys, and embedding the player into the note are the orchestrator's job
(see AGENTS.md). Two files (e.g. výklad + komisia) = two runs with different names.
"""
from __future__ import annotations

import argparse
import sys

from . import config, log, pipeline
from .transcript import validate as validate_transcript


def _cmd_upload(args: argparse.Namespace, cfg: dict) -> int:
    pipeline.upload(cfg, args.name, args.r2_key)
    return 0


def _cmd_validate(args: argparse.Namespace, cfg: dict) -> int:
    tpath = pipeline.transcript_path(cfg, args.name)
    if not tpath.exists():
        log.err(f"Transcript not found: {tpath}")
        return 1
    result = validate_transcript(tpath.read_text(encoding="utf-8"))
    log.step(f"{args.name}: turns={result.turns} chars={result.chars}")
    for w in result.warnings:
        log.warn(f"  warning: {w}")
    for e in result.errors:
        log.err(f"  error: {e}")
    return 0 if result.ok else 1


_COMMANDS = {"upload": _cmd_upload, "validate": _cmd_validate}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="szzpod", description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_up = sub.add_parser("upload")
    p_up.add_argument("name", help="Artifact name")
    p_up.add_argument("--r2-key", dest="r2_key", required=True,
                      help="R2 object key, e.g. TIN/Q21_klasifikacia_jazykov_vyklad.mp3")

    p_val = sub.add_parser("validate")
    p_val.add_argument("name", help="Artifact name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config.load_env()
    cfg = config.load_config(args.config)
    try:
        return _COMMANDS[args.command](args, cfg)
    except KeyboardInterrupt:
        log.err("interrupted")
        return 130
    except Exception as exc:  # surface a clean, colored error
        log.err(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
