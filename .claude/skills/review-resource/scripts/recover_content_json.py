#!/usr/bin/env python3
"""Rebuild a page's content JSON from the HTML it generated.

    python3 recover_content_json.py <slug> [--verify]

Why this exists
---------------
`.gitignore` matches `*.content.json` repo-wide, so the only editable
representation of a page never enters history. Once the ingest session's
`inbox/` is gone, a published page cannot be corrected the sanctioned way —
`pages/*.html` is generated and must not be hand-edited, and there is nothing
left to regenerate it from.

This script parses the generated page back into the shape `make_page.py`
expects. That is a reversal of a lossy-looking transform, so it is only
trustworthy if you prove it: `--verify` rebuilds from the recovered JSON and
diffs against the committed page, restoring everything if they differ. Treat a
non-empty diff as "the JSON is wrong", never as "the page is wrong" — you have
not earned the right to edit until the round-trip is byte-exact.

The escaped-markup case
-----------------------
`as_paragraphs()` in make_page.py passes an item through untouched only when it
starts with `<`; anything else is escaped. A `tldr` entry written as a bare
sentence carrying inline `<strong>` therefore renders its own tags as visible
text. That bug is invisible in the JSON and easy to miss in the HTML.

Recovery reproduces whichever form the page actually used, so the round-trip
stays exact either way — but when the escaped form is detected the script says
so loudly, because it is a real defect and wrapping those entries in `<p>`
should be your first fix.
"""

from __future__ import annotations

import argparse
import filecmp
import html as html_mod
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
ADD_RESOURCE = REPO / ".claude" / "skills" / "add-resource" / "scripts"
sys.path.insert(0, str(ADD_RESOURCE))
from common import DATA, INBOX, PAGES  # noqa: E402


SECTION_RE = re.compile(
    r'  <section id="(?P<id>[^"]+)">\n'
    r'    <h2><span class="sec-num">\d+</span>(?P<title>.*?)</h2>\n'
    r"(?P<html>.*?)\n"
    r"  </section>\n",
    re.S,
)
TLDR_RE = re.compile(r'<div class="tldr">\n    <h2>In short</h2>\n(.*?)\n  </div>', re.S)
SRCLINKS_RE = re.compile(r'<p class="srclinks">(.*?)</p>', re.S)
EXTRA_LINK_RE = re.compile(
    r'<a class="srclink" href="(?P<url>[^"]+)" target="_blank" rel="noopener">↗ (?P<label>[^<]+)</a>'
)


def recover_tldr(page: str) -> list[str]:
    """Return tldr entries in whichever form reproduces the page exactly.

    A paragraph holding real tags was passed through as HTML, so it round-trips
    as "<p>…</p>". A paragraph holding only escaped entities was a bare string
    that make_page.py escaped, so it round-trips as the unescaped plain text.
    """
    block = TLDR_RE.search(page)
    if not block:
        return []
    out, escaped = [], False
    for inner in re.findall(r"<p>(.*?)</p>", block.group(1), re.S):
        if re.search(r"<[a-zA-Z/]", inner):
            out.append(f"<p>{inner}</p>")
        else:
            if re.search(r"&lt;[a-zA-Z/]", inner):
                escaped = True
            out.append(html_mod.unescape(inner))
    if escaped:
        print(
            "\n  !! The 'In short' block contains ESCAPED markup — the page is\n"
            "     showing literal <strong>/<em> tags to the reader. Recovery has\n"
            "     reproduced the bug so the round-trip stays exact. Fix it by\n"
            "     wrapping those tldr entries in <p>…</p> after verification.\n",
            file=sys.stderr,
        )
    return out


def recover(slug: str) -> dict:
    page_path = PAGES / f"{slug}.html"
    if not page_path.exists():
        sys.exit(f"No such page: {page_path.relative_to(REPO)}")
    page = page_path.read_text(encoding="utf-8")

    sections = [
        {"id": m.group("id"), "title": html_mod.unescape(m.group("title")), "html": m.group("html")}
        for m in SECTION_RE.finditer(page)
    ]
    if not sections:
        sys.exit(
            "Parsed zero sections. The page template has probably changed since\n"
            "this script was written — fix SECTION_RE before going any further."
        )

    library = json.loads((DATA / "library.json").read_text(encoding="utf-8"))
    entry = next((e for e in library if e.get("slug") == slug), None)
    if entry is None:
        sys.exit(f"{slug} is not in data/library.json — is the slug right?")

    # The first srclink is the source_url and the PDF link is generated from
    # `pdf` (it carries ⬇ and no target, so it never matches here); everything
    # else on that line came from `extra_links`.
    srclinks = SRCLINKS_RE.search(page)
    extras = [
        {"label": m.group("label"), "url": m.group("url")}
        for m in EXTRA_LINK_RE.finditer(srclinks.group(1) if srclinks else "")
        if m.group("url") != entry.get("source_url")
    ]

    content = {
        "slug": slug,
        "title": entry["title"],
        "type": entry.get("type", "paper"),
        "authors": entry.get("authors", ""),
        "venue": entry.get("venue", ""),
        "year": entry.get("year"),
        "tags": entry.get("tags", []),
        "hook": entry["hook"],
        "tldr": recover_tldr(page),
        "source_url": entry.get("source_url"),
        "added": entry.get("added"),
        "sections": sections,
    }
    if entry.get("pdf"):
        content["pdf"] = entry["pdf"]
    if extras:
        content["extra_links"] = extras
    return content


def verify(slug: str, json_path: Path) -> int:
    """Rebuild from the recovered JSON and prove the page comes back identical."""
    targets = [PAGES / f"{slug}.html", REPO / "index.html", DATA / "library.json"]
    backups = {t: t.with_suffix(t.suffix + ".rvbak") for t in targets}
    for t, b in backups.items():
        shutil.copy2(t, b)
    try:
        subprocess.run(
            [sys.executable, str(ADD_RESOURCE / "make_page.py"), str(json_path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        page = PAGES / f"{slug}.html"
        if filecmp.cmp(page, backups[page], shallow=False):
            print(f"  round-trip exact: {page.relative_to(REPO)} rebuilt byte-for-byte")
            print("  the recovered JSON is trustworthy — you may now edit it")
            return 0
        diff = subprocess.run(
            ["diff", str(backups[page]), str(page)], capture_output=True, text=True
        ).stdout
        for t, b in backups.items():
            shutil.copy2(b, t)
        print("  ROUND-TRIP FAILED — restored the working tree.", file=sys.stderr)
        print("  The recovered JSON is wrong (the page is not). Diff:\n", file=sys.stderr)
        print("\n".join(diff.splitlines()[:60]), file=sys.stderr)
        return 1
    finally:
        for b in backups.values():
            b.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("slug", help="the resource slug, e.g. context-engineering-survey")
    ap.add_argument(
        "--verify",
        action="store_true",
        help="rebuild from the recovered JSON and diff against the committed page",
    )
    args = ap.parse_args()

    content = recover(args.slug)
    INBOX.mkdir(parents=True, exist_ok=True)
    out = INBOX / f"{args.slug}.content.json"
    out.write_text(
        json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"  wrote {out.relative_to(REPO)}  ({len(content['sections'])} sections)")

    if args.verify:
        return verify(args.slug, out)
    print("  run again with --verify before editing it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
