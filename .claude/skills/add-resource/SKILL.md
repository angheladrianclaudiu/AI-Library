---
name: add-resource
description: Add a research paper, long article or blog post to this AI Library as a plain-English explanation page with the source's figures, and link it into the main menu. Use when the user wants to add, ingest, process or explain a new resource — a PDF dropped in inbox/, a paper, an arXiv link, or a long-form article URL — or says "/add-resource", "add this paper", "add this article", "explain this PDF for the library". Handles extraction, figure selection, page generation and index rebuild; it does not commit until the user approves.
---

# Add a resource to the AI Library

One resource in, one page out, linked from the main menu. The site is the
product; this skill is the machine that grows it.

The pipeline is deliberately boring — scripts do the extraction and the HTML,
so that all of *your* effort goes into the one part a script cannot do: reading
the source properly and explaining it in plain English.

## Workflow

Copy this checklist and tick it off as you go:

```
- [ ] 1. Identify the source and install dependencies
- [ ] 2. Extract text + figure candidates
- [ ] 3. Read the whole source
- [ ] 4. Decide the depth
- [ ] 5. Choose the figures and write their captions
- [ ] 6. Write the content JSON
- [ ] 7. Tags, PDF, build
- [ ] 8. Verify
- [ ] 9. Adversarial review — at least one round, adjudicated, fixed
- [ ] 10. Record what the session taught you
- [ ] 11. Report and wait for approval
```

Before step 1, read **`LEARNINGS.md`** in the repo root. It records which heuristics
have broken and on what kind of source — including things you must check by hand
because the extractor gets them wrong. It will save you rediscovering them.

### 1. Identify the source

| What the user gives you | What to run |
|---|---|
| A PDF path, or a PDF sitting in `inbox/` | `extract_pdf.py` |
| An article URL | `extract_article.py --url …` |
| A saved `.html` in `inbox/` | `extract_article.py --file … --url <original>` |
| A saved `.pdf` of an article | `extract_pdf.py` (pass `--slug`, set `"type": "article"` later) |
| Nothing | look in `inbox/`; if it holds exactly one candidate, use it, otherwise ask |

Install dependencies once per environment:

```bash
pip install -r .claude/skills/add-resource/scripts/requirements.txt
```

### 2. Extract

```bash
python3 .claude/skills/add-resource/scripts/extract_pdf.py inbox/<file>.pdf
# or
python3 .claude/skills/add-resource/scripts/extract_article.py --url <url>
```

Both write `inbox/<slug>.text.json` and `inbox/<slug>.figures.json`, and put
figure candidates in `assets/images/<slug>/`. Both print a summary telling you
the detected title, authors, year, source URL and the PDF's size.

Check the detected metadata against the source and correct it — the heuristics
are good, not infallible. If no `source_url` was found and the user hasn't
given one, ask for it: a page with no way back to the original is a dead end.

**If the URL fetch fails with a proxy 403/407**, the environment's egress policy
forbids the open web. Do not try to route around it. Tell the user to save the
page into `inbox/` (print to PDF, or Save Page As) and re-run with `--file`.

### 3. Read the whole source

Read `inbox/<slug>.text.json` end to end — every page, not the abstract and the
conclusion. This is the step that decides whether the page is worth reading.
Everything else in this skill is plumbing.

While reading, note: what problem this attacks, what was tried before and why it
fell short, what is genuinely new here, which claims are backed by the
experiments and which are asserted, and what the authors admit it can't do.

### 4. Decide the depth

The source sets the length; the rubric only sets a ceiling.

| Source | Target |
|---|---|
| Dense methods paper, or a long-form essay | 20–30 min (~5,000–8,000 words) |
| Standard 8–12 page conference paper | 12–18 min (~2,500–4,000 words) |
| Short paper, workshop paper, ordinary blog post | 5–8 min (~1,200–2,000 words) |

**Never pad to reach a number.** A thin source explained in 1,500 honest words
is a good page; the same source stretched to 6,000 is a bad one.

### 5. Choose the figures

Open `inbox/<slug>.figures.json`. It lists candidates with the caption the PDF
gave them. Typically keep **3–8**. Prefer the figure that carries the core idea
(architecture diagrams, the one plot the whole argument rests on) over decorative
or redundant ones.

- `"source": "embedded"` — the original raster at full resolution.
- `"source": "rendered-region"` — the area above a caption, rendered. This is
  how vector diagrams survive. **Look at each one you intend to use** (read the
  image file) and confirm it is cropped to the artwork, not to a slab of body
  text. If a crop is wrong, drop it.

Then **delete every candidate you did not choose** so the repo carries only what
the page shows:

```bash
# after deciding, from assets/images/<slug>/
rm fig-p04-x31.webp fig-p07-figure-9.webp   # the ones not used
```

Write your own caption for each figure you keep. A caption says **what it shows
and why it matters** — not the paper's original caption copied over. Always set
a real `alt` describing the content for someone who cannot see it, plus the
`<span class="figsrc">` line crediting the source page.

### 6. Write the content JSON

Write `inbox/<slug>.content.json`. `make_page.py`'s docstring has the full
schema; the short version:

```json
{
  "slug": "…", "title": "…", "type": "paper",
  "authors": "…", "venue": "…", "year": 2017,
  "tags": ["…"], "hook": "One or two sentences for the library card.",
  "tldr": ["<p>…</p>"],
  "source_url": "https://…",
  "pdf": "assets/pdf/<slug>.pdf",
  "sections": [{"id": "the-problem", "title": "The problem", "html": "<p>…</p>"}]
}
```

`type` is `"paper"`, `"article"` or `"guide"`. Two optional fields exist for the
third kind:

- `"scripts": ["assets/foo.js"]` — page-scoped local JS, injected after
  `app.js`. Remote URLs are rejected; the site's one external dependency is the
  Google Fonts link and it stays that way.
- `"colophon_note"` — replaces the footer's "read the original" line, which is
  false for a guide. A `guide` gets a sensible default without setting this.

Two more apply to any type, and exist because a page that **reproduces** a
source rather than explaining it makes the defaults wrong:

- `"colophon_lead"` — replaces the footer's opening "Explained and published in
  the AI Library on …". `{{ADDED}}` still resolves inside whatever you supply.
  Set it whenever "explained" would be a lie.
- `"num"` on a section — the label printed above the section title, instead of
  its ordinal position. Use it when the sections carry numbers of their own
  ("Factor 1", "Factor 2"), where an ordinal runs one ahead of the name and the
  reader ends up trusting neither.

Follow `references/writing-guide.md` — it covers the section skeleton, how to
handle equations without a maths renderer, and the available components.

### 7. Tags, PDF, build

**Tags.** Read `data/tags.json` and reuse what fits. Add a new tag only when
nothing existing covers the resource — a vocabulary of 15 useful tags beats 60
tags used once each. Three to five tags per resource.

**PDF.** The extractor reports `pdf_under_1mb`.

- Under 1 MB → `cp inbox/<file>.pdf assets/pdf/<slug>.pdf` and set `"pdf"` in
  the content JSON.
- 1 MB or more → do **not** copy it. Leave `"pdf"` out; the page links
  `source_url` instead. Say so in your report.
- Articles: never commit a scraped copy — link the original.

**Build:**

```bash
python3 .claude/skills/add-resource/scripts/make_page.py inbox/<slug>.content.json
```

This writes `pages/<slug>.html`, upserts `data/library.json`, updates
`data/tags.json` and rebuilds `index.html`.

### 8. Verify

Work through `references/checklist.md`. At minimum, serve the site and look at
the page you just made:

```bash
python3 -m http.server 8000
```

### 9. Adversarial review

**Not optional, and not satisfied by step 8.** `references/checklist.md` verifies
that the page *renders* correctly; nothing in steps 1–8 checks that it *says what
the source says*. Every recorded pre-publication review run against a freshly
built page — regardless of how carefully it was written — has found real,
distinct fidelity or craft defects. Treat "this one will be clean" as the
hypothesis under test, not the default.

Spawn a subagent (Opus if available) with a combined fidelity-plus-craft brief:
give it `references/writing-guide.md`, `inbox/<slug>.text.json` (the source,
with `=== PAGE N ===` markers so findings can cite a page), `inbox/<slug>.content.json`,
`inbox/<slug>.figures.json`, the built `pages/<slug>.html`, and the actual image
files under `assets/images/<slug>/`. Ask it to verify every claim, number, quote
and equation against the source, and — this catches a different bug than
checking the source — to check each figure's `alt` and caption against what the
**saved image file** actually shows, not against the source's original caption
text. A crop can be legible, complete-looking, and still missing a panel its own
alt text describes; that only shows up by looking at the two side by side.

**Adjudicate every finding yourself before fixing anything.** The agent
over-reports by design. Verify each one against `inbox/<slug>.text.json` (or the
image file) directly — cite the page, quote the sentence — before touching the
content JSON. Rejections are a normal, expected outcome, not a failure of the
review.

**Fix, rebuild, then do a second round — do not stop after one fix pass.**
This is the part that's easy to skip under time pressure and empirically the
part that matters most: a same-session second review, told explicitly not to
trust the first round's fixes, has repeatedly found further real defects on
pages that had already been through one full adversarial cycle — including
defects the first round's *own fixes* introduced (a hedge dropped while
rewording a sentence, a scope word that crept in while patching something
else). One clean round is not evidence the page is clean; it is evidence the
next round will find something smaller. Keep iterating until a round returns
nothing beyond findings already rejected by precedent (see `LEARNINGS.md` for
the running list — e.g. em-dash density is not a defect on its own).

Re-run `references/checklist.md` and the browser check after every fix pass —
a wording fix can reintroduce a rendering bug (an unclosed tag, an overflowing
equation) as easily as a fresh page can.

### 10. Record what the session taught you

Append a section to **`LEARNINGS.md`** following the template at the bottom of that
file: what the source looked like, what worked without intervention, what broke, and
which constant or heuristic changed as a result. Every source has a different layout,
and the next session's crops depend on this being honest — including the boring
entries where nothing went wrong, since "single-column arXiv preprints extract cleanly"
is itself worth knowing. Record the adversarial-review findings too, the same way a
`/review-resource` session would: what was found, what was rejected and why, and how
many rounds it took before one came back empty.

If you hit something worth fixing but out of scope for this ingest, add it to
**`TASKS.md`** rather than fixing it mid-page or letting it evaporate.

### 11. Report, then stop

Report: the page path, its read time and section count, which figures you kept
and why, the tags, whether the PDF was committed or linked, anything you had to
guess, and the adversarial review — how many rounds it took, what was found and
fixed, and what was found and rejected.

**Do not commit or push until the user approves.** When they do:

```bash
git add -A
git commit -m "Add resource: <title>"
git push -u origin <branch>
```

`inbox/` is git-ignored, so the working files never land in history — but check
`git status --porcelain` before committing anyway.

## Common mistakes

Skimming the source and writing a summary of the abstract. Padding a thin paper
to hit a word count. Keeping ten figures because they extracted cleanly.
Copying the paper's own captions instead of explaining what each figure shows.
Inventing a tag when a fitting one already exists. Leaving unused images in
`assets/images/`. Committing before the user has looked. Treating one
adversarial-review round as sufficient because it came back with a short list —
a short list is not a clean page, it's where the next round starts. Writing a
figure's `alt` text from the source's caption without re-opening the saved crop
to confirm it actually shows what the caption claims.

## Resources

- `references/writing-guide.md` — how to write the explanation; components available.
- `references/checklist.md` — verify before reporting.
- `scripts/extract_pdf.py` — text, metadata and figures from a PDF.
- `scripts/extract_article.py` — the same from a URL or a saved page.
- `scripts/make_page.py` — content JSON → page + library entry.
- `scripts/rebuild_index.py` — regenerate `index.html` from `data/library.json`.
