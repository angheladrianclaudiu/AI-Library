"""Helpers shared by the add-resource scripts."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# repo root = three levels above .claude/skills/add-resource/scripts/
REPO = Path(__file__).resolve().parents[4]

INBOX = REPO / "inbox"
PAGES = REPO / "pages"
DATA = REPO / "data"
IMAGES = REPO / "assets" / "images"
PDFS = REPO / "assets" / "pdf"
SKILL = Path(__file__).resolve().parents[1]

# The size ceiling for committing a source PDF into the repo.
PDF_SIZE_LIMIT = 1_000_000  # 1 MB


def slugify(text: str, max_words: int = 9) -> str:
    """Turn a title into a short, stable, filesystem-safe slug."""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    words = [w for w in text.split() if w]
    return "-".join(words[:max_words]) or "untitled"


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def read_minutes(words: int) -> int:
    """Reading time at ~220 wpm, with a floor of 1 minute."""
    return max(1, round(words / 220))


def human_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.0f} KB"
    return f"{n} bytes"


def find_arxiv_id(text: str) -> str | None:
    """Recover an arXiv ID from a paper's own front matter so we can link the source.

    Pass only the first page or two, not the full document. A mid-document
    citation to someone else's arXiv paper matches the same pattern as a
    preprint's own self-identification, and the two are not distinguishable by
    regex alone — only position is. See LEARNINGS.md session 9.
    """
    patterns = (
        r"arXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?",
        r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?",
    )
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def find_doi(text: str) -> str | None:
    m = re.search(r"\b(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\b", text)
    if not m:
        return None
    return m.group(1).rstrip(".,;)")


def find_year(text: str) -> int | None:
    """Most plausible publication year mentioned near the top of a document."""
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", text)]
    return max(years) if years else None
