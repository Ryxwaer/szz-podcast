"""Transcript parsing and chunking (self-contained copy; same format as szzpod)."""
from __future__ import annotations

import re

SPEAKER_RE = re.compile(r"^\s*(Person1|Person2|P1|P2)\s*:\s*(.*)$", re.IGNORECASE)
XML_TURN_RE = re.compile(r"<(Person1|Person2)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)

Turn = tuple[str, str]  # (speaker, text); speaker is "person1" | "person2"


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


def chunk(turns: list[Turn], max_chars: int) -> list[list[Turn]]:
    """Split turns into chunks of ~max_chars. Turns are never split.

    A chunk break is only allowed before a person1 turn: Gemini multi-speaker
    anchors speaker identity anew each request, and chunks opening with the
    person2 (female) turn are the ones that come out with a wrong/male voice.
    Since turns alternate, this overflows max_chars by at most one turn.
    """
    chunks: list[list[Turn]] = []
    cur: list[Turn] = []
    cur_len = 0
    for speaker, line in turns:
        if cur and cur_len + len(line) > max_chars and speaker == "person1":
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append((speaker, line))
        cur_len += len(line)
    if cur:
        chunks.append(cur)
    return chunks
