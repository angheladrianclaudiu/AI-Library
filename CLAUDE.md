# AI Library — working notes for Claude

A static, GitHub Pages-hosted library of AI research papers and long-form articles.
Each resource gets one page: a plain-English explanation written from the source,
with the source's own figures extracted and captioned. `index.html` is the menu.

**The site is the product; `.claude/skills/add-resource/` is the machine that grows it.**
Changes to the machine should be justified by something that went wrong building a page.

## Companion files — read these

- **[TASKS.md](TASKS.md)** — the backlog of improvements to the skill, the extractors
  and the generated HTML. Check it before proposing new work; add to it whenever you
  hit something worth fixing but out of scope for the task at hand.
- **[LEARNINGS.md](LEARNINGS.md)** — what previous extraction sessions actually taught
  us: which heuristics held, which broke, and on what kind of source. **Read it before
  touching `extract_pdf.py`** — most of the tuning constants there exist because of a
  specific failure recorded in that file. Append a new section after every ingest.

## Adding a resource

Use the `/add-resource` skill rather than doing it by hand — it carries the depth
rubric, the figure-selection discipline and the writing rules. Its `SKILL.md` is the
process of record; this file does not repeat it.

```bash
pip install -r .claude/skills/add-resource/scripts/requirements.txt   # once
python3 .claude/skills/add-resource/scripts/extract_pdf.py inbox/paper.pdf --slug my-slug
python3 .claude/skills/add-resource/scripts/make_page.py inbox/my-slug.content.json
```

`make_page.py` rebuilds `index.html` on its own. `rebuild_index.py` regenerates it
standalone and is idempotent.

## Conventions that matter

- **Never hand-edit `index.html` or `pages/*.html`.** Both are generated. Edit the
  content JSON or the templates in `.claude/skills/add-resource/assets/` and rebuild.
- **`data/library.json` is the source of truth** for what is in the library.
  `index.html` bakes it in as an inline array — never `fetch`es it, so the page works
  identically over `file://` and over Pages.
- **One slug per resource**, kebab-case, keep it short. It names the page, the image
  folder, the PDF and the library entry.
- **`inbox/` is git-ignored.** Source PDFs and extractor working files live there and
  must never be committed.
- **Source PDFs under 1 MB** go to `assets/pdf/<slug>.pdf` and get linked. At 1 MB or
  over, do not commit — link `source_url` instead.
- **Delete unused figure candidates.** The extractor produces a menu; only what the
  page actually shows belongs in the repo.
- **All colour lives in `:root` tokens in `assets/style.css`.** Both themes must work —
  check dark mode explicitly, it is where contrast bugs hide.
- **One external dependency, ever: the Google Fonts `<link>`.** No CDN scripts, no
  remote images, no maths renderer. Equations are Unicode plus a prose reading.

## Verifying a change

The layout either reads well or it does not, and only a browser can tell you.

```bash
python3 -m http.server 8000        # then drive Chromium via Playwright
```

Chromium is at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; pass
`NO_PROXY='*'` so localhost is not sent through the egress proxy. Screenshot the
index and one resource page in **both** themes, at desktop and phone width, and
assert behaviour rather than eyeballing: TOC anchors resolve, images load, search and
tag filters narrow, the theme toggle flips and persists, no horizontal overflow.

Two environment quirks, neither a page defect: Google Fonts is blocked here, so
screenshots render in fallback faces; and a full-page screenshot of a long page needs
`device_scale_factor=1` and a raised timeout or it will time out encoding.

## Network

This environment's egress policy allows GitHub, PyPI and npm — nothing else. The open
web returns 403, `WebFetch` included. The PDF path needs no network and works fine.
For an article, fetching only works when the skill is run from a machine with normal
access; here, save the page and drop it in `inbox/`. Do not try to route around the
proxy.

## Git

Work on the branch named in the task. `inbox/` stays out of history — check
`git status --porcelain` before committing. Keep tooling fixes and content additions
in separate commits; the history reads much better that way.
