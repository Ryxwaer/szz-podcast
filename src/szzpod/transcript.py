"""Transcript parsing, validation, and chunking.

A transcript is a sequence of ``Person1:`` / ``Person2:`` turns. Only a minimal
set of Eleven v3 audio tags is allowed inline (pacing only); anything else is
flagged so the audio stays in the calm, study-material register.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Eleven v3 in-text audio tags we permit (pacing only). Everything else is a warning.
ALLOWED_TAGS = {"pause", "short pause", "long pause"}

TAG_RE = re.compile(r"\[([^\[\]]+)\]")
SPEAKER_RE = re.compile(r"^\s*(Person1|Person2|P1|P2)\s*:\s*(.*)$", re.IGNORECASE)
XML_TURN_RE = re.compile(r"<(Person1|Person2)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)

Turn = tuple[str, str]  # (speaker, text); speaker is "person1" | "person2"


@dataclass
class ValidationResult:
    turns: int
    chars: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _clean(s: str) -> str:
    s = " ".join(s.split()).strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] in "\"'":
        s = s[1:-1].strip()
    return s


def parse(text: str) -> list[Turn]:
    """Parse transcript text into a list of (speaker, text) turns."""
    turns: list[Turn] = []

    if "<Person1>" in text or "<Person2>" in text:
        for m in XML_TURN_RE.finditer(text):
            speaker = "person1" if m.group(1).lower() == "person1" else "person2"
            turns.append((speaker, _clean(m.group(2))))
        return [t for t in turns if t[1]]

    cur_speaker: str | None = None
    cur_lines: list[str] = []

    def flush() -> None:
        if cur_speaker and cur_lines:
            turns.append((cur_speaker, _clean(" ".join(cur_lines))))

    for line in text.splitlines():
        m = SPEAKER_RE.match(line)
        if m:
            flush()
            tag = m.group(1).lower()
            cur_speaker = "person1" if tag in ("person1", "p1") else "person2"
            cur_lines = [m.group(2)]
        elif cur_speaker is not None:
            cur_lines.append(line)
    flush()
    return [t for t in turns if t[1]]


def validate(text: str) -> ValidationResult:
    turns = parse(text)
    chars = sum(len(t[1]) for t in turns)
    res = ValidationResult(turns=len(turns), chars=chars)

    if not turns:
        res.errors.append("No Person1:/Person2: turns found.")
        return res

    if turns[0][0] != "person1":
        res.warnings.append("Transcript should start with Person1.")

    for tag in TAG_RE.findall(text):
        normalized = tag.strip().lower()
        if normalized not in ALLOWED_TAGS:
            res.warnings.append(
                f"Disallowed audio tag [{tag}] (allowed: "
                f"{', '.join(sorted(ALLOWED_TAGS))})."
            )

    return res


def chunk(turns: list[Turn], max_chars: int) -> list[list[Turn]]:
    """Split turns into chunks of <= max_chars. Turns are never split."""
    chunks: list[list[Turn]] = []
    cur: list[Turn] = []
    cur_len = 0
    for speaker, line in turns:
        if cur and cur_len + len(line) > max_chars:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append((speaker, line))
        cur_len += len(line)
    if cur:
        chunks.append(cur)
    return chunks
