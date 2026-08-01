#!/usr/bin/env python3
"""Extract a long web article (or a saved copy of one) for the AI Library.

    python3 extract_article.py --url https://example.com/post [--slug my-slug]
    python3 extract_article.py --file inbox/saved-post.html --url https://…

Writes the same two working files as extract_pdf.py, so the rest of the
pipeline does not care which branch produced them:

  inbox/<slug>.text.json      article text + metadata
  inbox/<slug>.figures.json   downloaded images (or, if blocked, their URLs)

Network note: some environments — including Claude Code on the web — sit
behind an egress proxy that only allows GitHub and the package registries.
Fetching then fails with 403/407. That is not a bug to route around: save the
page yourself (Ctrl+P → PDF, or File → Save As → HTML) into `inbox/` and re-run
with --file. A saved .pdf is handed straight to extract_pdf.py.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    IMAGES,
    INBOX,
    find_year,
    slugify,
    word_count,
    write_json,
)

MIN_IMAGE_SIDE = 200
MAX_WIDTH = 1400
WEBP_QUALITY = 82
UA = "Mozilla/5.0 (compatible; AI-Library/1.0; +https://github.com/)"

BLOCKED_HINT = """
Could not fetch that URL from this environment.

If the failure is a 403/407 from a proxy, this environment's egress policy only
allows GitHub and package registries — the open web is not reachable, and there
is no way around that from inside the session.

What to do instead:
  1. Open the article in your browser.
  2. Save it into inbox/  —  Ctrl+P → "Save as PDF" keeps the images and layout,
     or File → "Save Page As" → "Webpage, Complete" for the raw HTML.
  3. Re-run:  python3 extract_article.py --file inbox/<saved-file> --url <original-url>

The --url is still worth passing: it becomes the "Source" link on the page.
""".strip()


def fetch(url: str) -> str:
    import requests

    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    except Exception as exc:  # proxy refusals surface here too
        sys.exit(f"{BLOCKED_HINT}\n\nUnderlying error: {exc}")

    if resp.status_code in (403, 405, 407):
        sys.exit(f"{BLOCKED_HINT}\n\nHTTP {resp.status_code} for {url}")
    if resp.status_code >= 400:
        sys.exit(f"HTTP {resp.status_code} fetching {url}")

    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def parse_html(html: str, base_url: str) -> dict:
    """Main content + title + images. trafilatura first, BeautifulSoup after."""
    title, text, date = "", "", None

    try:
        import trafilatura

        extracted = trafilatura.extract(
            html, include_comments=False, include_tables=True,
            include_images=False, with_metadata=True, output_format="json",
        )
        if extracted:
            payload = json.loads(extracted)
            title = payload.get("title") or ""
            text = payload.get("text") or ""
            date = payload.get("date")
    except Exception:
        pass

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    if not title:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

    if not text:
        # Fallback: the densest <article>/<main>, else the whole body.
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        root = soup.find("article") or soup.find("main") or soup.body or soup
        text = "\n\n".join(
            p.get_text(" ", strip=True)
            for p in root.find_all(["p", "h1", "h2", "h3", "li", "blockquote", "pre"])
            if p.get_text(strip=True)
        )

    author = ""
    for attrs in ({"name": "author"}, {"property": "article:author"}, {"name": "twitter:creator"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            author = tag["content"].strip()
            break

    site = ""
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        site = og_site["content"].strip()
    elif base_url:
        site = urlparse(base_url).netloc

    # Image candidates, biggest-first where srcset tells us the sizes.
    images = []
    seen = set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        srcset = img.get("srcset") or ""
        if srcset:
            best, best_w = src, 0
            for part in srcset.split(","):
                bits = part.strip().split()
                if len(bits) == 2 and bits[1].endswith("w"):
                    try:
                        w = int(bits[1][:-1])
                    except ValueError:
                        continue
                    if w > best_w:
                        best, best_w = bits[0], w
            src = best or src
        if not src or src.startswith("data:"):
            continue
        full = urljoin(base_url, src) if base_url else src
        if full in seen:
            continue
        seen.add(full)
        images.append({"url": full, "alt": (img.get("alt") or "").strip()})

    return {
        "title": title, "text": text, "author": author,
        "site": site, "date": date, "image_urls": images,
    }


def download_images(candidates: list[dict], out_dir: Path, slug: str) -> list[dict]:
    """Store images locally; fall back to hotlinking when a download is blocked."""
    import requests
    from PIL import Image

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, cand in enumerate(candidates[:40], start=1):
        url = cand["url"]
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
            resp.raise_for_status()
            import io

            img = Image.open(io.BytesIO(resp.content))
        except Exception as exc:
            # Record it anyway: the page can still reference the original URL,
            # flagged so the skill can tell you what didn't come across.
            results.append({
                "file": None, "remote_url": url, "hotlinked": True,
                "alt": cand["alt"], "error": str(exc)[:160],
            })
            continue

        if img.width < MIN_IMAGE_SIDE or img.height < MIN_IMAGE_SIDE:
            continue

        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            rgba = img.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            img = img.resize((MAX_WIDTH, max(1, int(img.height * ratio))), Image.LANCZOS)

        name = f"img-{i:02d}.webp"
        dest = out_dir / name
        img.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
        results.append({
            "file": f"assets/images/{slug}/{name}",
            "remote_url": url, "hotlinked": False, "alt": cand["alt"],
            "width": img.width, "height": img.height, "bytes": dest.stat().st_size,
        })

    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="article URL (fetched, and used as the Source link)")
    ap.add_argument("--file", help="a saved .html or .pdf copy in inbox/")
    ap.add_argument("--slug", help="slug to use (default: derived from the title)")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()

    if not args.url and not args.file:
        sys.exit("Pass --url, --file, or both.")

    # A saved PDF is just a PDF — reuse the better-tested extractor.
    if args.file and Path(args.file).suffix.lower() == ".pdf":
        cmd = [sys.executable, str(Path(__file__).parent / "extract_pdf.py"), args.file]
        if args.slug:
            cmd += ["--slug", args.slug]
        print("Saved copy is a PDF — handing off to extract_pdf.py\n", file=sys.stderr)
        return subprocess.call(cmd)

    if args.file:
        html = Path(args.file).read_text(encoding="utf-8", errors="replace")
    else:
        html = fetch(args.url)

    parsed = parse_html(html, args.url or "")
    if not parsed["text"].strip():
        sys.exit("No article text could be extracted — check the saved file is the full page.")

    title = parsed["title"] or "Untitled article"
    slug = args.slug or slugify(title)

    figures = []
    if not args.no_images and parsed["image_urls"]:
        figures = download_images(parsed["image_urls"], IMAGES / slug, slug)

    words = word_count(parsed["text"])
    meta = {
        "slug": slug,
        "title": title,
        "authors": parsed["author"],
        "venue": parsed["site"],
        "year": (int(parsed["date"][:4]) if parsed["date"] and parsed["date"][:4].isdigit()
                 else find_year(parsed["text"][:3000])),
        "published": parsed["date"],
        "words": words,
        "source_url": args.url,
        "saved_from": args.file,
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    INBOX.mkdir(parents=True, exist_ok=True)
    write_json(INBOX / f"{slug}.text.json",
               {"meta": meta, "pages": [{"page": 1, "text": parsed["text"]}]})
    write_json(INBOX / f"{slug}.figures.json", {"slug": slug, "figures": figures})

    hotlinked = sum(1 for f in figures if f.get("hotlinked"))
    print(json.dumps({
        "slug": slug, "title": title, "authors": meta["authors"],
        "venue": meta["venue"], "year": meta["year"], "words": words,
        "source_url": meta["source_url"],
        "images_downloaded": len(figures) - hotlinked,
        "images_blocked_hotlink_only": hotlinked,
        "text_file": f"inbox/{slug}.text.json",
        "figures_file": f"inbox/{slug}.figures.json",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
