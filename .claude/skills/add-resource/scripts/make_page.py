#!/usr/bin/env python3
"""Build one resource page from a content JSON, and register it in the library.

    python3 make_page.py inbox/attention-is-all-you-need.content.json

Generating the page rather than hand-writing it is what keeps twenty pages
consistent, makes read time honest, and turns a later theme change into a
single-file edit.

Content JSON shape
------------------
{
  "slug": "attention-is-all-you-need",
  "title": "Attention Is All You Need",
  "type": "paper",                       # "paper" | "article" | "guide"
  "authors": "Vaswani, Shazeer, Parmar, …",
  "venue": "NeurIPS",                    # or the site name for an article
  "year": 2017,
  "tags": ["transformers", "architecture"],
  "hook": "One or two sentences for the library card.",
  "tldr": ["<p>…</p>", "<p>…</p>"],      # HTML paragraphs, or plain strings
  "source_url": "https://arxiv.org/abs/1706.03762",
  "pdf": "assets/pdf/attention-is-all-you-need.pdf",   # optional, only if < 1MB
  "scripts": ["assets/fieldguide.js"],   # optional, local paths only
  "colophon_lead": "Republished … on {{ADDED}}.",   # optional, see below
  "sections": [
    {"id": "the-problem", "title": "The problem", "html": "<p>…</p>"}
  ]
}

Anything not supplied is simply left out of the page — no placeholders leak
into the output.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DATA,
    PAGES,
    REPO,
    SKILL,
    read_json,
    read_minutes,
    slugify,
    word_count,
    write_json,
)

TEMPLATE = SKILL / "assets" / "page-template.html"
REQUIRED = ("slug", "title", "sections", "hook")

# What a resource can be. "guide" is for something written for this library
# rather than explained from an outside source, so it has no original to link.
TYPE_LABELS = {"paper": "Paper", "article": "Article", "guide": "Guide"}

# The colophon's opening line. "Explained" is true of a page written from a
# source and false of one that reproduces it, so a resource can override this;
# {{ADDED}} still resolves inside whatever it supplies.
COLOPHON_LEAD_DEFAULT = "Explained and published in the AI Library on {{ADDED}}."

# The colophon's standing promise — true for anything explained from a source,
# and wrong for a guide, which has no original to send the reader back to.
COLOPHON_NOTES = {
    "default": (
        "This page is a plain-English explanation written from the source listed above — "
        "read the original for the authors' own words, exact numbers and full method details."
    ),
    "guide": (
        "This page was written for this library rather than explained from an outside "
        "source. Its claims are cited where they are load-bearing; everything else is "
        "exposition."
    ),
}


def esc(value) -> str:
    return html_mod.escape(str(value if value is not None else ""), quote=True)


def strip_tags(markup: str) -> str:
    return re.sub(r"<[^>]+>", " ", markup or "")


def as_paragraphs(value) -> str:
    """Accept a string or a list; wrap bare text in <p> but pass HTML through."""
    items = value if isinstance(value, list) else [value]
    out = []
    for item in items:
        item = str(item).strip()
        if not item:
            continue
        out.append(item if item.startswith("<") else f"<p>{esc(item)}</p>")
    return "\n    ".join(out)


def build_toc(sections: list[dict]) -> str:
    rows = [
        f'      <li><a href="#{esc(s["id"])}">{esc(s["title"])}</a></li>'
        for s in sections
    ]
    return "\n".join(rows)


def build_sections(sections: list[dict]) -> str:
    """Position number above each section title, unless the section sets `num`.

    Ordinal position is right when section names carry no number of their own.
    When they do — a source whose sections *are* "Factor 1", "Factor 2" — the
    ordinal disagrees with the name and the reader trusts neither, so the
    section can supply the label it should print instead.
    """
    parts = []
    for i, sec in enumerate(sections, start=1):
        num = sec.get("num", f"{i:02d}")
        parts.append(
            f'  <section id="{esc(sec["id"])}">\n'
            f'    <h2><span class="sec-num">{esc(num)}</span>{esc(sec["title"])}</h2>\n'
            f'{sec["html"].rstrip()}\n'
            f"  </section>\n"
        )
    return "\n".join(parts)


SOURCE_LABELS = {
    "paper": "Original paper",
    "article": "Original article",
    "guide": "Source",
}


def build_source_links(content: dict) -> str:
    rtype = content.get("type", "paper")
    links = []
    url = content.get("source_url")
    if url:
        label = SOURCE_LABELS.get(rtype, "Source")
        links.append(
            f'<a class="srclink" href="{esc(url)}" target="_blank" rel="noopener">↗ {label}</a>'
        )
    pdf = content.get("pdf")
    if pdf:
        # Pages live in pages/, assets one level up.
        href = pdf if pdf.startswith(("http", "../")) else f"../{pdf}"
        links.append(f'<a class="srclink" href="{esc(href)}">⬇ PDF in this repo</a>')
    for extra in content.get("extra_links", []):
        links.append(
            f'<a class="srclink" href="{esc(extra["url"])}" target="_blank" rel="noopener">'
            f'↗ {esc(extra["label"])}</a>'
        )
    if not links:
        # A guide is original to this library, so there is no missing original.
        note = (
            "Written for this library"
            if rtype == "guide"
            else "No public source link"
        )
        links.append(f'<span class="srclink">{note}</span>')
    return "\n      ".join(links)


def build_meta_line(content: dict, minutes: int) -> str:
    """Read time (plus venue/year only when the byline didn't already carry them),
    then tags on their own row.

    The tags go in their own element rather than being joined into the same
    separator list: the row wraps, and a joined list leaves a stranded "·" at
    the end of the first line.
    """
    bits = [f"{minutes} min read"]
    if not content.get("authors"):
        # No byline, so this line has to carry the provenance.
        if content.get("year"):
            bits.append(str(content["year"]))
        if content.get("venue"):
            bits.append(content["venue"])

    line = ' <span class="dot">·</span> '.join(esc(b) for b in bits)
    if content.get("tags"):
        tags = " · ".join(esc(t) for t in content["tags"])
        line += f'<span class="hero__tags">{tags}</span>'
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("content", help="path to the content JSON")
    ap.add_argument("--no-index", action="store_true", help="skip rebuilding index.html")
    args = ap.parse_args()

    content = read_json(Path(args.content))
    if content is None:
        sys.exit(f"No such file: {args.content}")

    missing = [k for k in REQUIRED if not content.get(k)]
    if missing:
        sys.exit(f"Content JSON is missing required key(s): {', '.join(missing)}")

    slug = content.get("slug") or slugify(content["title"])
    sections = content["sections"]
    for sec in sections:
        sec.setdefault("id", slugify(sec["title"]))

    ids = [s["id"] for s in sections]
    if len(ids) != len(set(ids)):
        sys.exit(f"Duplicate section ids: {[i for i in ids if ids.count(i) > 1]}")

    body_text = strip_tags(" ".join(s["html"] for s in sections))
    words = word_count(body_text)
    minutes = content.get("read_minutes") or read_minutes(words)

    rtype = content.get("type", "paper")
    if rtype not in TYPE_LABELS:
        sys.exit(f"type must be one of {', '.join(sorted(TYPE_LABELS))}")

    authors_block = ""
    if content.get("authors"):
        venue = content.get("venue") or ""
        year = content.get("year") or ""
        trailer = " · ".join(str(x) for x in (venue, year) if x)
        authors_block = (
            f'<p class="hero__authors">{esc(content["authors"])}'
            + (f' <span class="hero__venue">· {esc(trailer)}</span>' if trailer else "")
            + "</p>"
        )

    added = content.get("added") or date.today().isoformat()

    # Page-scoped scripts, so an interactive resource can ship its own local
    # JS without anyone hand-editing the generated HTML. Local paths only —
    # the site's one-external-dependency rule is the Google Fonts link.
    scripts = []
    for src in content.get("scripts", []):
        if src.startswith(("http://", "https://", "//")):
            sys.exit(f"scripts must be local to this repo, got: {src}")
        href = src if src.startswith("../") else f"../{src.lstrip('/')}"
        scripts.append(f'<script src="{esc(href)}"></script>')

    page = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": esc(content["title"]),
        "{{DESCRIPTION}}": esc(content["hook"]),
        "{{TYPE}}": rtype,
        "{{TYPE_LABEL}}": TYPE_LABELS[rtype],
        "{{AUTHORS_BLOCK}}": authors_block,
        "{{META}}": build_meta_line(content, minutes),
        "{{SOURCE_LINKS}}": build_source_links(content),
        "{{TLDR}}": as_paragraphs(content.get("tldr", content["hook"])),
        "{{TOC}}": build_toc(sections),
        "{{SECTIONS}}": build_sections(sections),
        # Ordered before {{ADDED}} so a supplied lead can still use that token.
        "{{COLOPHON_LEAD}}": as_paragraphs(
            content.get("colophon_lead") or COLOPHON_LEAD_DEFAULT
        ),
        "{{COLOPHON_NOTE}}": as_paragraphs(
            content.get("colophon_note")
            or COLOPHON_NOTES.get(rtype, COLOPHON_NOTES["default"])
        ),
        "{{ADDED}}": date.fromisoformat(added).strftime("%d %B %Y"),
        "{{EXTRA_SCRIPTS}}": "\n".join(scripts),
    }
    for needle, value in replacements.items():
        page = page.replace(needle, value)

    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    if left:
        sys.exit(f"Template placeholders were not filled: {sorted(set(left))}")

    PAGES.mkdir(parents=True, exist_ok=True)
    out = PAGES / f"{slug}.html"
    out.write_text(page, encoding="utf-8")

    # Upsert into the library index data.
    library = read_json(DATA / "library.json", default=[]) or []
    entry = {
        "slug": slug,
        "title": content["title"],
        "type": rtype,
        "authors": content.get("authors", ""),
        "venue": content.get("venue", ""),
        "year": content.get("year"),
        "tags": content.get("tags", []),
        "hook": content["hook"],
        "read_minutes": minutes,
        "words": words,
        "page": f"pages/{slug}.html",
        "source_url": content.get("source_url"),
        "pdf": content.get("pdf"),
        "added": added,
    }
    library = [e for e in library if e.get("slug") != slug]
    library.append(entry)
    library.sort(key=lambda e: (e.get("added", ""), e.get("slug", "")), reverse=True)
    write_json(DATA / "library.json", library)

    # Keep the tag vocabulary in sync so the skill can reuse existing tags.
    tags_path = DATA / "tags.json"
    known = read_json(tags_path, default=[]) or []
    merged = sorted({*known, *content.get("tags", [])})
    if merged != known:
        write_json(tags_path, merged)

    if not args.no_index:
        subprocess.check_call([sys.executable, str(Path(__file__).parent / "rebuild_index.py")])

    print(json.dumps({
        "page": str(out.relative_to(REPO)),
        "slug": slug,
        "sections": len(sections),
        "words": words,
        "read_minutes": minutes,
        "tags": content.get("tags", []),
        "library_size": len(library),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
