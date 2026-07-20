"""ffmpeg audio assembly: concatenate chunk WAVs, then optional mastering.

Gemini returns natural, level audio, so by default we only concatenate and apply a
gentle whole-episode loudnorm to a target LUFS. The dynamics master (compressor +
dynamic normalizer + limiter) is available but off by default to avoid coloring.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

TRUE_PEAK_DBFS = -1.5
_MASTER_CHAIN = (
    "acompressor=threshold=-20dB:ratio=4:attack=5:release=150:makeup=3,"
    "dynaudnorm=f=400:g=21:p=0.9:m=3:t=0.02,"
    "alimiter=limit=0.891"
)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def concat(segments: list[Path], sample_rate: int, bitrate: str, out_path: Path) -> None:
    """Concatenate audio segments, re-encoding to a uniform mp3 sample rate/bitrate."""
    list_file = out_path.parent / "_concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg.resolve()}'\n")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
          "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", str(sample_rate), str(out_path)])
    list_file.unlink(missing_ok=True)


def _filter_chain(normalize: bool, target_lufs: float, dynamics: bool) -> str:
    parts: list[str] = []
    if normalize:
        parts.append(f"loudnorm=I={target_lufs}:TP={TRUE_PEAK_DBFS}:LRA=11")
    if dynamics:
        parts.append(_MASTER_CHAIN)
    return ",".join(parts)


def master(src: Path, dst: Path, sample_rate: int, bitrate: str,
           normalize: bool, target_lufs: float, dynamics: bool) -> None:
    chain = _filter_chain(normalize, target_lufs, dynamics)
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if chain:
        cmd += ["-af", chain]
    cmd += ["-c:a", "libmp3lame", "-b:a", bitrate, "-ar", str(sample_rate), str(dst)]
    _run(cmd)


def assemble(chunk_files: list[Path], sample_rate: int, bitrate: str, out_path: Path,
             tmp: Path, normalize: bool, target_lufs: float, dynamics: bool) -> None:
    """Concatenate chunks and apply mastering (if any) into out_path."""
    if normalize or dynamics:
        joined = tmp / "_joined.mp3"
        concat(chunk_files, sample_rate, bitrate, joined)
        master(joined, out_path, sample_rate, bitrate, normalize, target_lufs, dynamics)
    else:
        concat(chunk_files, sample_rate, bitrate, out_path)
