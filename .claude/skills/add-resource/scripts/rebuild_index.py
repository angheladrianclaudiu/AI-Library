#!/usr/bin/env python3
"""Regenerate index.html from data/library.json.

    python3 rebuild_index.py

index.html is generated, never hand-edited. The library data is baked into the
page as an inline `window.LIBRARY` array rather than fetched from the JSON file,
because `fetch` of a local file fails under file:// — baking it means the page
behaves identically opened from disk and served from GitHub Pages.

Idempotent: running it twice produces byte-identical output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, REPO, SKILL, read_json  # noqa: E402

TEMPLATE = SKILL / "assets" / "index-template.html"
START = "/*__LIBRARY_JSON__*/"
END = "/*__END_LIBRARY_JSON__*/"

# Only these keys reach the browser; `words` and friends stay server-side.
CARD_KEYS = ("slug", "title", "type", "authors", "venue", "year",
             "tags", "hook", "read_minutes", "page", "added")


def main() -> int:
    library = read_json(DATA / "library.json", default=[]) or []

    cards = []
    for entry in library:
        cards.append({k: entry.get(k) for k in CARD_KEYS if entry.get(k) is not None})
    cards.sort(key=lambda e: (str(e.get("added", "")), str(e.get("slug", ""))), reverse=True)

    template = TEMPLATE.read_text(encoding="utf-8")
    start = template.index(START)
    end = template.index(END) + len(END)

    payload = json.dumps(cards, indent=2, ensure_ascii=False)
    # Never let a "</script>" inside data terminate the tag early.
    payload = payload.replace("</", "<\\/")

    page = template[:start] + START + payload + END + template[end:]

    out = REPO / "index.html"
    out.write_text(page, encoding="utf-8")

    print(json.dumps({
        "index": "index.html",
        "resources": len(cards),
        "tags": sorted({t for c in cards for t in c.get("tags", [])}),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
