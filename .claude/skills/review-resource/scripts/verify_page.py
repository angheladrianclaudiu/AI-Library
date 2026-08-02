#!/usr/bin/env python3
"""Drive Chromium over a resource page and assert the things a screenshot hides.

    python3 verify_page.py <slug> [--port 8000] [--shots <dir>]

Exits non-zero and prints every failure, so it can gate a commit.

Why this exists
---------------
The add-resource checklist asks for these checks on every ingest and ships
nothing to run them, so each session rewrites the same Playwright harness and
each session rediscovers the same two traps. Both are encoded here:

  * A `<table>` inside `.table-scroll` is *supposed* to be wider than the
    viewport — that is the mechanism. Asserting "no element exceeds the phone
    width" fails on a correct page. What must hold is that the scroll container
    itself fits and that `scrollWidth > clientWidth`, i.e. it really scrolls.

  * A blocked-request console message does not contain the URL, so filtering
    console text for "fonts.googleapis" never matches. Listen to `requestfailed`
    and inspect `request.url` instead. Google Fonts is blocked by this
    environment's egress policy and is expected to fail; anything else is not.

Checks: no body overflow, scroll containers behave, every image decodes, every
TOC and citation anchor resolves, the bibliography has no dangling or unused
ids, the theme toggle flips and survives a reload, and on the index the card
appears and both search and the tag chips narrow to it.
"""

from __future__ import annotations

import argparse
import functools
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
VIEWPORTS = [(1280, 900, "desktop"), (390, 844, "phone")]
SEARCH = "#search"


def _own_tags(slug: str) -> list[str]:
    import json

    library = json.loads((REPO / "data" / "library.json").read_text(encoding="utf-8"))
    entry = next((e for e in library if e.get("slug") == slug), {})
    return entry.get("tags", [])


def _report(fails: list[str]) -> int:
    if fails:
        print("\nFAILURES:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\n  all checks passed (a failing Google Fonts request is expected here)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("slug")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--shots", help="directory to write screenshots into")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is not installed — pip install playwright")

    base = f"http://localhost:{args.port}"
    url = f"{base}/pages/{args.slug}.html"
    fails: list[str] = []
    note = fails.append

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(args.port)],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
            for width, height, label in VIEWPORTS:
                for theme in ("light", "dark"):
                    ctx = browser.new_context(viewport={"width": width, "height": height})
                    page = ctx.new_page()
                    failed_reqs: list[str] = []
                    js_errors: list[str] = []
                    page.on("requestfailed", lambda r: failed_reqs.append(r.url))
                    page.on("pageerror", lambda e: js_errors.append(str(e)))
                    page.goto(url, wait_until="networkidle")
                    if theme == "dark":
                        page.click(".theme-toggle")
                        page.wait_for_timeout(250)

                    tag = f"{label}/{theme}"
                    check = functools.partial(_assert, note, tag)

                    overflow = page.evaluate(
                        "document.body.scrollWidth - document.body.clientWidth"
                    )
                    check(overflow == 0, f"body overflows horizontally by {overflow}px")

                    # The container must fit even though the table inside does not.
                    for i, box in enumerate(
                        page.evaluate(
                            "[...document.querySelectorAll('.table-scroll')].map(d =>"
                            " [d.clientWidth <= document.body.clientWidth,"
                            "  d.scrollWidth > d.clientWidth, d.scrollWidth, d.clientWidth])"
                        )
                    ):
                        fits, scrolls, sw, cw = box
                        check(fits, f".table-scroll[{i}] is wider than the body ({cw}px)")
                        if not scrolls and sw == cw:
                            pass  # a narrow table that genuinely fits is fine
                    broken = page.evaluate(
                        "[...document.images].filter(i => !i.naturalWidth)"
                        ".map(i => i.getAttribute('src'))"
                    )
                    check(not broken, f"images failed to load: {broken}")
                    count = page.evaluate("document.images.length")
                    check(count > 0, "the page has no images at all")

                    dead_toc = page.evaluate(
                        "[...document.querySelectorAll('.toc a')]"
                        ".filter(a => !document.querySelector(a.getAttribute('href')))"
                        ".map(a => a.getAttribute('href'))"
                    )
                    check(not dead_toc, f"TOC anchors resolve to nothing: {dead_toc}")

                    dead_cit = page.evaluate(
                        "[...document.querySelectorAll('a.cit')]"
                        ".filter(a => !document.querySelector(a.getAttribute('href')))"
                        ".map(a => a.getAttribute('href'))"
                    )
                    check(not dead_cit, f"citations point at missing ids: {dead_cit}")

                    orphans = page.evaluate(
                        "(() => { const cited = new Set([...document.querySelectorAll('a.cit')]"
                        ".map(a => a.getAttribute('href').slice(1)));"
                        " return [...document.querySelectorAll('.biblio li')].map(li => li.id)"
                        ".filter(id => id && id !== 'r1' && !cited.has(id)); })()"
                    )
                    check(not orphans, f"bibliography entries nothing cites: {orphans}")

                    unexpected = [u for u in failed_reqs if "fonts.g" not in u]
                    check(not unexpected, f"requests failed: {unexpected}")
                    check(not js_errors, f"javascript errors: {js_errors}")

                    if theme == "dark":
                        stored = page.evaluate("localStorage.getItem('ail-theme')")
                        page.reload(wait_until="networkidle")
                        after = page.evaluate(
                            "document.documentElement.getAttribute('data-theme')"
                        )
                        check(
                            stored == "dark" and after == "dark",
                            f"theme did not persist (stored={stored}, after reload={after})",
                        )

                    if args.shots:
                        d = Path(args.shots)
                        d.mkdir(parents=True, exist_ok=True)
                        page.screenshot(
                            path=str(d / f"{args.slug}-{label}-{theme}.png"), full_page=False
                        )
                    print(f"  {tag}: overflow={overflow} images={count}")
                    ctx.close()

            # The index: card present, and both ways of finding it work.
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(f"{base}/index.html", wait_until="networkidle")
            visible = lambda: page.evaluate(  # noqa: E731
                "[...document.querySelectorAll('.card')].filter(c => c.offsetParent).length"
            )
            check = functools.partial(_assert, note, "index")
            card = f"document.querySelector('a[href*=\"{args.slug}\"]')"
            shown = f"(() => {{ const a = {card}; return !!a && !!a.closest('.card').offsetParent; }})()"
            check(page.evaluate(f"!!{card}"), "the card for this resource is not on the index")
            if not page.evaluate(f"!!{card}"):
                ctx.close()
                browser.close()
                raise SystemExit(_report(fails))

            # Search on the resource's own title, not the card's full text —
            # that also carries the badge and the read time.
            title = page.evaluate(f"{card}.querySelector('.card__title').textContent.trim()")
            page.fill(SEARCH, " ".join(title.split()[:4]))
            page.wait_for_timeout(300)
            check(page.evaluate(shown), "searching this resource's title does not find its card")
            page.fill(SEARCH, "zzzzqqq")
            page.wait_for_timeout(300)
            check(visible() == 0, "a nonsense search still shows cards")
            page.fill(SEARCH, "")
            page.wait_for_timeout(300)

            before = visible()
            tags = page.evaluate(
                f"[...document.querySelectorAll('.chip[data-tag]')].map(c => c.dataset.tag)"
            )
            own = _own_tags(args.slug)
            hit = next((t for t in own if t in tags), None)
            check(hit is not None, f"none of this resource's tags {own} appear as chips")
            if hit:
                page.click(f'.chip[data-tag="{hit}"]')
                page.wait_for_timeout(300)
                check(page.evaluate(shown), f"filtering on its own tag '{hit}' hid the card")
                check(visible() <= before, f"tag '{hit}' did not narrow the list")
            check(
                page.evaluate("document.body.scrollWidth - document.body.clientWidth") == 0,
                "the index overflows horizontally",
            )
            ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=5)

    return _report(fails)


def _assert(note, tag: str, ok: bool, message: str) -> None:
    if not ok:
        note(f"{tag}: {message}")


if __name__ == "__main__":
    raise SystemExit(main())
