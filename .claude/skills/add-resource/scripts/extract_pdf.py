#!/usr/bin/env python3
"""Extract text, metadata and figures from a PDF for the AI Library.

    python3 extract_pdf.py inbox/paper.pdf [--slug my-slug]

Writes three things:

  inbox/<slug>.text.json      full text, page by page, plus detected metadata
  inbox/<slug>.figures.json   a menu of figure candidates to choose from
  assets/images/<slug>/       the candidate images themselves, as .webp

Figures come from two passes, because either one alone misses half of them:

  1. Embedded raster images (screenshots, plots exported as PNG).
  2. Regions rendered from the page above a "Figure N:" caption — ML papers
     draw architecture diagrams as vector art, which pass 1 cannot see at all.

Nothing here is destructive: unused candidates are deleted later by the skill,
and `inbox/` is git-ignored.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is missing. Run: pip install -r requirements.txt")

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is missing. Run: pip install -r requirements.txt")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    IMAGES,
    INBOX,
    PDF_SIZE_LIMIT,
    find_arxiv_id,
    find_doi,
    find_year,
    human_size,
    slugify,
    word_count,
    write_json,
)

# Tuning for what counts as a real figure rather than a logo, rule or icon.
MIN_SIDE = 120           # px — anything thinner is a divider or a bullet
MIN_AREA = 25_000        # px² — roughly 160×160
MAX_ASPECT = 12.0        # a 12:1 strip is a rule, not a diagram
MAX_WIDTH = 1400         # px — downscale ceiling for stored figures
WEBP_QUALITY = 82

CAPTION_RE = re.compile(
    r"^\s*(Fig(?:ure)?\.?\s*\d+[.:]?|Table\s*\d+[.:]?)\s*(.*)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------

def extract_text(doc) -> list[dict]:
    pages = []
    for i, page in enumerate(doc):
        pages.append({"page": i + 1, "text": page.get_text("text")})
    return pages


def guess_title(doc, pages: list[dict]) -> str:
    """Prefer the largest text on page 1; fall back to PDF metadata.

    PDF `title` metadata is unreliable in academic PDFs — it is often the LaTeX
    filename or empty — so the visual heuristic goes first.
    """
    try:
        blocks = doc[0].get_text("dict")["blocks"]
        best_size, best_text = 0.0, ""
        for block in blocks:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                size = max(s["size"] for s in spans)
                text = "".join(s["text"] for s in spans).strip()
                if not text or len(text) < 6:
                    continue
                # Skip the arXiv stamp printed sideways down the left margin.
                if text.lower().startswith("arxiv:"):
                    continue
                if size > best_size:
                    best_size, best_text = size, text
                elif abs(size - best_size) < 0.5 and best_text and len(best_text) < 90:
                    # Titles often wrap onto a second line at the same size.
                    best_text = f"{best_text} {text}"
        if best_text:
            return re.sub(r"\s+", " ", best_text).strip()
    except Exception:
        pass

    meta_title = (doc.metadata or {}).get("title") or ""
    if meta_title.strip():
        return meta_title.strip()
    return (pages[0]["text"].strip().splitlines() or ["Untitled"])[0][:120]


def guess_authors(pages: list[dict], title: str) -> str:
    """Lines just under the title that look like a list of names."""
    lines = [l.strip() for l in pages[0]["text"].splitlines() if l.strip()]
    title_words = set(title.lower().split())
    for line in lines[:22]:
        low = line.lower()
        if title_words and len(set(low.split()) & title_words) > 2:
            continue
        if "@" in line or "abstract" in low or low.startswith("arxiv"):
            continue
        if len(line) > 220:
            continue
        # Names: several capitalised words, often comma- or 'and'-separated.
        names = re.findall(r"\b[A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-\.]+)+", line)
        if len(names) >= 2 or (names and ("," in line or " and " in low)):
            return re.sub(r"\s*[\d\*†‡§¶]+\s*", " ", line).strip(" ,;")
    return ""


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def save_webp(img: Image.Image, dest: Path) -> tuple[int, int]:
    if img.mode in ("RGBA", "LA", "P"):
        # Flatten onto white: paper figures assume a white page.
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize((MAX_WIDTH, max(1, int(img.height * ratio))), Image.LANCZOS)

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
    return img.width, img.height


def is_worth_keeping(w: int, h: int) -> bool:
    if w < MIN_SIDE or h < MIN_SIDE:
        return False
    if w * h < MIN_AREA:
        return False
    aspect = max(w / h, h / w)
    return aspect <= MAX_ASPECT


def caption_blocks(page) -> list[dict]:
    """Find 'Figure N: ...' / 'Table N: ...' blocks and their bounding boxes."""
    found = []
    try:
        data = page.get_text("dict")
    except Exception:
        return found

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        text = " ".join(
            "".join(s["text"] for s in line.get("spans", []))
            for line in block.get("lines", [])
        ).strip()
        m = CAPTION_RE.match(text)
        if not m:
            continue
        found.append({
            "label": re.sub(r"[.:]\s*$", "", m.group(1).strip()),
            "caption": re.sub(r"\s+", " ", text)[:600],
            "bbox": list(block["bbox"]),
            "is_table": m.group(1).lower().startswith("table"),
        })
    return found


def extract_embedded(doc, out_dir: Path, slug: str) -> list[dict]:
    """Pass 1 — raster images already embedded in the PDF."""
    results, seen = [], set()

    for pno, page in enumerate(doc):
        captions = caption_blocks(page)

        for xref, *_ in page.get_images(full=True):
            if xref in seen:
                continue
            seen.add(xref)
            try:
                raw = doc.extract_image(xref)
                img = Image.open(io.BytesIO(raw["image"]))
            except Exception:
                continue
            if not is_worth_keeping(img.width, img.height):
                continue

            name = f"fig-p{pno + 1:02d}-x{xref}.webp"
            dest = out_dir / name
            try:
                w, h = save_webp(img, dest)
            except Exception:
                continue

            # Attach the nearest caption on the same page, if any.
            nearest = ""
            try:
                rects = page.get_image_rects(xref)
                if rects and captions:
                    bottom = max(r.y1 for r in rects)
                    below = [c for c in captions if c["bbox"][1] >= bottom - 20]
                    pick = min(below, key=lambda c: c["bbox"][1] - bottom) if below else None
                    if pick:
                        nearest = pick["caption"]
            except Exception:
                pass

            results.append({
                "file": f"assets/images/{slug}/{name}",
                "page": pno + 1,
                "source": "embedded",
                "width": w,
                "height": h,
                "bytes": dest.stat().st_size,
                "caption_in_pdf": nearest,
            })

    return results


# Artwork geometry, in PDF points (72pt = 1 inch).
MIN_ART_SIDE = 28.0      # a 28pt mark is a logo or a bullet, not a figure
CLUSTER_GAP = 42.0       # vertical whitespace that separates two figures


def artwork_bbox(page, band: fitz.Rect) -> fitz.Rect | None:
    """Tight bounding box of the artwork sitting directly above a caption.

    Taking the whole band would drag in the body text above the figure, and
    taking the caption's width would clip a figure wider than its caption. So:
    collect the vector paths and images in the band, drop marks too small to be
    a figure, group what's left into vertically contiguous clusters, and keep
    the cluster nearest the caption — a page header logo lives in its own
    cluster far above and is left behind. Finally pull in text that sits inside
    the artwork: the labels drawn inside an architecture diagram's boxes.
    """
    rects: list[fitz.Rect] = []

    try:
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect and rect in band and max(rect.width, rect.height) >= MIN_ART_SIDE:
                rects.append(fitz.Rect(rect))
    except Exception:
        pass

    try:
        for info in page.get_image_info():
            rect = fitz.Rect(info["bbox"])
            if rect in band and min(rect.width, rect.height) >= MIN_ART_SIDE:
                rects.append(rect)
    except Exception:
        pass

    if not rects:
        return None

    # Cluster vertically, then keep the one closest to the caption.
    rects.sort(key=lambda r: r.y0)
    clusters: list[fitz.Rect] = []
    for rect in rects:
        if clusters and rect.y0 - clusters[-1].y1 <= CLUSTER_GAP:
            clusters[-1] |= rect
        else:
            clusters.append(fitz.Rect(rect))

    box = max(clusters, key=lambda c: c.y1)
    if box.width < 40 or box.height < 40:
        return None

    # Two passes: absorb text overlapping the artwork, then re-absorb anything
    # the enlarged box now touches (axis labels outside the plot frame).
    try:
        blocks = [
            fitz.Rect(b[:4])
            for b in page.get_text("blocks")
            if len(b) >= 5 and str(b[4]).strip()
        ]
        for _ in range(2):
            for rect in blocks:
                if rect in band and rect.intersects(box):
                    box |= rect
    except Exception:
        pass

    return box & band


def extract_regions(doc, out_dir: Path, slug: str) -> list[dict]:
    """Pass 2 — render the artwork above each figure caption.

    This is what captures vector diagrams: the architecture figure in a
    transformer paper is drawn with PDF path operators, so it simply does not
    exist as an embedded image.
    """
    results = []

    for pno, page in enumerate(doc):
        captions = [c for c in caption_blocks(page) if not c["is_table"]]
        if not captions:
            continue

        page_rect = page.rect
        # Sort so we can bound each figure by whatever sits above it.
        captions.sort(key=lambda c: c["bbox"][1])

        for idx, cap in enumerate(captions):
            cx0, cy0, cx1, cy1 = cap["bbox"]

            # Search band: below the previous caption on the page, else page top.
            top = page_rect.y0
            if idx > 0:
                top = max(top, captions[idx - 1]["bbox"][3] + 4)

            if cy0 - top < 40:  # caption sits at the top — nothing above it
                continue

            band = fitz.Rect(page_rect.x0, top, page_rect.x1, cy0 - 2)
            clip = artwork_bbox(page, band)
            if clip is None:
                continue

            clip = fitz.Rect(
                max(page_rect.x0, clip.x0 - 6), max(page_rect.y0, clip.y0 - 6),
                min(page_rect.x1, clip.x1 + 6), min(page_rect.y1, clip.y1 + 6),
            )
            if clip.width < 80 or clip.height < 60:
                continue

            try:
                pix = page.get_pixmap(clip=clip, dpi=200, alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
            except Exception:
                continue

            # Blank regions render as a solid white rectangle — drop them.
            try:
                extrema = img.convert("L").getextrema()
                if extrema and extrema[0] > 245:
                    continue
            except Exception:
                pass

            if not is_worth_keeping(img.width, img.height):
                continue

            label = slugify(cap["label"], max_words=3)
            name = f"fig-p{pno + 1:02d}-{label}.webp"
            dest = out_dir / name
            try:
                w, h = save_webp(img, dest)
            except Exception:
                continue

            results.append({
                "file": f"assets/images/{slug}/{name}",
                "page": pno + 1,
                "source": "rendered-region",
                "width": w,
                "height": h,
                "bytes": dest.stat().st_size,
                "caption_in_pdf": cap["caption"],
                "_clip": [clip.x0, clip.y0, clip.x1, clip.y1],
            })

    return results


def drop_redundant_regions(doc, embedded: list[dict], regions: list[dict],
                           out_dir: Path) -> list[dict]:
    """Discard a rendered region that merely re-photographs an embedded image.

    When a figure is a single raster, both passes find it. The embedded copy is
    the original at full resolution, so the region is the one to throw away —
    but only when it adds nothing, i.e. the image fills nearly all of it.
    """
    by_page: dict[int, list[fitz.Rect]] = {}
    for fig in embedded:
        pno = fig["page"] - 1
        try:
            for info in doc[pno].get_image_info():
                by_page.setdefault(fig["page"], []).append(fitz.Rect(info["bbox"]))
        except Exception:
            pass

    kept = []
    for region in regions:
        clip = fitz.Rect(region.pop("_clip"))
        area = clip.get_area()
        redundant = False
        for rect in by_page.get(region["page"], []):
            overlap = (clip & rect).get_area()
            # The image covers most of the region, and the region adds no margin.
            if area > 0 and overlap / area > 0.85:
                redundant = True
                break
        if redundant:
            (out_dir / Path(region["file"]).name).unlink(missing_ok=True)
        else:
            kept.append(region)
    return kept


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", help="path to the source PDF")
    ap.add_argument("--slug", help="slug to use (default: derived from the title)")
    ap.add_argument("--no-figures", action="store_true", help="text and metadata only")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        sys.exit(f"No such file: {pdf_path}")

    doc = fitz.open(pdf_path)
    pages = extract_text(doc)
    full_text = "\n".join(p["text"] for p in pages)
    head = full_text[:4000]

    title = guess_title(doc, pages)
    slug = args.slug or slugify(title)
    out_dir = IMAGES / slug

    arxiv = find_arxiv_id(full_text)
    meta = {
        "slug": slug,
        "title": title,
        "authors": guess_authors(pages, title),
        "year": find_year(head),
        "pages": len(pages),
        "words": word_count(full_text),
        "arxiv_id": arxiv,
        "source_url": f"https://arxiv.org/abs/{arxiv}" if arxiv else None,
        "doi": find_doi(full_text),
        "pdf_path": str(pdf_path),
        "pdf_bytes": pdf_path.stat().st_size,
        "pdf_under_limit": pdf_path.stat().st_size < PDF_SIZE_LIMIT,
        "pdf_metadata": {k: v for k, v in (doc.metadata or {}).items() if v},
    }

    figures: list[dict] = []
    if not args.no_figures:
        # Start clean so re-runs don't accumulate stale candidates.
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        embedded = extract_embedded(doc, out_dir, slug)
        regions = drop_redundant_regions(
            doc, embedded, extract_regions(doc, out_dir, slug), out_dir
        )
        figures = embedded + regions
        figures.sort(key=lambda f: (f["page"], f["file"]))

    INBOX.mkdir(parents=True, exist_ok=True)
    write_json(INBOX / f"{slug}.text.json", {"meta": meta, "pages": pages})
    write_json(INBOX / f"{slug}.figures.json", {"slug": slug, "figures": figures})

    doc.close()

    print(json.dumps({
        "slug": slug,
        "title": title,
        "authors": meta["authors"],
        "year": meta["year"],
        "pages": meta["pages"],
        "words": meta["words"],
        "source_url": meta["source_url"],
        "pdf_size": human_size(meta["pdf_bytes"]),
        "pdf_under_1mb": meta["pdf_under_limit"],
        "figure_candidates": len(figures),
        "text_file": f"inbox/{slug}.text.json",
        "figures_file": f"inbox/{slug}.figures.json",
        "images_dir": f"assets/images/{slug}/",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
