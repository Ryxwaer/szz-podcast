"""ffmpeg audio assembly: adaptive per-speaker loudness leveling + concatenation.

The two cloned voices come out of ElevenLabs at different (and per-chunk varying)
loudness, so a fixed gain cannot balance them. Instead we measure each speaker's
integrated loudness within every chunk (using the API's ``voice_segments``) and
apply a per-speaker gain that brings both to a common ``target_lufs``. A final
true-peak limiter guards against clipping after any boost.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

# Cap per-speaker correction so we never over-amplify a near-silent/noisy segment.
MAX_GAIN_DB = 12.0
# Final safety ceiling (true peak), as a linear amplitude. -1.0 dBFS ~= 0.891.
TRUE_PEAK_LIMIT = 0.891
SILENCE_FLOOR_LUFS = -70.0

# Final mastering chain over the whole episode: a compressor catches loud phrase
# onsets (fast attack), a dynamic normalizer evens out slower loudness drift
# (threshold keeps it off the silences), then a true-peak limiter for safety.
MASTER_CHAIN = (
    "acompressor=threshold=-20dB:ratio=4:attack=5:release=150:makeup=3,"
    "dynaudnorm=f=400:g=21:p=0.9:m=3:t=0.02,"
    f"alimiter=limit={TRUE_PEAK_LIMIT}"
)


def make_silence(seconds: float, sample_rate: int, bitrate: str, out_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"anullsrc=r={sample_rate}:cl=mono", "-t", str(seconds),
         "-c:a", "libmp3lame", "-b:a", bitrate, str(out_path)],
        check=True, capture_output=True,
    )


def _enable_expr(ranges: list[tuple[float, float]]) -> str:
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges)


def _integrated_loudness(src: Path, mute_ranges: list[tuple[float, float]]) -> float | None:
    """Integrated loudness (LUFS) of ``src`` with ``mute_ranges`` silenced."""
    pre = ""
    if mute_ranges:
        pre = f"volume=enable='{_enable_expr(mute_ranges)}':volume=0,"
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(src),
         "-af", f"{pre}ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)", proc.stderr)
    return float(m.group(1)) if m else None


def _segments_by_voice(segments: list[dict]) -> dict[str, list[tuple[float, float]]]:
    by: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for s in segments:
        v = s.get("voice_id")
        if v is None:
            continue
        by[v].append((float(s["start_time_seconds"]), float(s["end_time_seconds"])))
    return by


def speaker_gains(src: Path, by_voice: dict[str, list[tuple[float, float]]],
                  target_lufs: float) -> dict[str, float]:
    """Per-voice linear gain that lifts/cuts each speaker to ``target_lufs``."""
    gains: dict[str, float] = {}
    for voice, ranges in by_voice.items():
        others = [r for ov, rs in by_voice.items() if ov != voice for r in rs]
        loud = _integrated_loudness(src, others)
        if loud is None or loud <= SILENCE_FLOOR_LUFS:
            continue
        g_db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, target_lufs - loud))
        gains[voice] = 10 ** (g_db / 20.0)
    return gains


def build_filter(by_voice: dict[str, list[tuple[float, float]]],
                 gains: dict[str, float]) -> list[str]:
    parts: list[str] = []
    for voice, ranges in by_voice.items():
        g = gains.get(voice)
        if g is None or abs(g - 1.0) < 1e-3:
            continue
        parts.append(f"volume=enable='{_enable_expr(ranges)}':volume={g:.4f}")
    return parts


def process_chunk(src: Path, segments: list[dict], target_lufs: float,
                  dst: Path, sample_rate: int, bitrate: str) -> dict[str, float]:
    """Level each speaker to ``target_lufs``, limit true peak, write ``dst``."""
    by_voice = _segments_by_voice(segments)
    gains = speaker_gains(src, by_voice, target_lufs)
    af_parts = build_filter(by_voice, gains)
    af_parts.append(f"alimiter=limit={TRUE_PEAK_LIMIT}")
    cmd = ["ffmpeg", "-y", "-i", str(src), "-af", ",".join(af_parts),
           "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", str(sample_rate), str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)
    return gains


def master(src: Path, dst: Path, sample_rate: int, bitrate: str) -> None:
    """Apply the final dynamics chain across the whole episode."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-af", MASTER_CHAIN,
         "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", str(sample_rate), str(dst)],
        check=True, capture_output=True,
    )


def concat(segments: list[Path], sample_rate: int, bitrate: str, out_path: Path) -> None:
    list_file = out_path.parent / "_concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg.resolve()}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", str(sample_rate), str(out_path)],
        check=True, capture_output=True,
    )
    list_file.unlink(missing_ok=True)


def assemble(chunk_files: list[Path], silence: Path | None, sample_rate: int, bitrate: str,
             out_path: Path, tmp: Path, normalize: bool, target_lufs: float,
             dynamics: bool) -> list[dict[str, float]]:
    """Level (optional), concatenate, and master (optional); return gains applied."""
    final: list[Path] = []
    applied: list[dict[str, float]] = []
    for idx, ch in enumerate(chunk_files):
        if normalize:
            segs_path = ch.with_suffix(".json")
            segments = json.loads(segs_path.read_text(encoding="utf-8")) if segs_path.exists() else []
            proc = tmp / f"proc_{idx:03d}.mp3"
            applied.append(process_chunk(ch, segments, target_lufs, proc, sample_rate, bitrate))
            final.append(proc)
        else:
            final.append(ch)
        if silence is not None and idx < len(chunk_files) - 1:
            final.append(silence)
    if dynamics:
        joined = tmp / "_joined.mp3"
        concat(final, sample_rate, bitrate, joined)
        master(joined, out_path, sample_rate, bitrate)
    else:
        concat(final, sample_rate, bitrate, out_path)
    return applied


def format_params(output_format: str) -> tuple[int, str]:
    """Derive (sample_rate, bitrate) from an output_format like 'mp3_44100_192'."""
    parts = output_format.split("_")
    sample_rate = int(parts[1]) if len(parts) > 1 else 44100
    bitrate = f"{parts[2]}k" if len(parts) > 2 else "128k"
    return sample_rate, bitrate
