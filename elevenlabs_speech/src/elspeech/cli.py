"""Command-line entry point for the standalone ElevenLabs renderer.

Commands:
  tts <name>       synthesize (cached) and assemble the episode mp3
  reassemble <n>   rebuild the mp3 from cached chunks only (no API calls)
  list             list transcripts available to render

This renderer only turns a transcript into audio/<name>.mp3. R2 upload, transcript
validation, and embedding into the note stay in the root ``szzpod`` tool.
"""
from __future__ import annotations

import argparse
import sys

from . import config, log, render


def _cmd_tts(args: argparse.Namespace, cfg: dict) -> int:
    render.render(cfg, args.name, reassemble=args.reassemble)
    return 0


def _cmd_reassemble(args: argparse.Namespace, cfg: dict) -> int:
    render.render(cfg, args.name, reassemble=True)
    return 0


def _cmd_list(args: argparse.Namespace, cfg: dict) -> int:
    tdir = config.paths(cfg)["transcripts"]
    names = sorted(p.stem for p in tdir.glob("*.txt"))
    log.step(f"transcripts in {tdir} ({len(names)})")
    for n in names:
        log.info(f"  {n}")
    return 0


_COMMANDS = {"tts": _cmd_tts, "reassemble": _cmd_reassemble, "list": _cmd_list}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elspeech", description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tts = sub.add_parser("tts")
    p_tts.add_argument("name", help="Transcript name without .txt (e.g. Q26_..._vyklad)")
    p_tts.add_argument("--reassemble", action="store_true",
                       help="Only reassemble from cached chunks (no API calls).")

    p_re = sub.add_parser("reassemble")
    p_re.add_argument("name", help="Transcript name without .txt")

    sub.add_parser("list")
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
