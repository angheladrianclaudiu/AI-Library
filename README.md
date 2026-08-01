# AI Library

A personal library of AI research papers and long-form articles, each read end
to end and rewritten as a plain-English explanation page — with the figures from
the source that actually explain the idea.

Browse it at **`index.html`**: search, filter by tag, sort. Once GitHub Pages is
enabled (below) it is a live site; it also works opened straight from disk.

## Adding a resource

1. Drop the PDF into `inbox/` (git-ignored, so nothing leaks into history).
2. Run the skill in Claude Code:

   ```
   /add-resource inbox/my-paper.pdf
   ```

   It also takes an article URL — `/add-resource https://…` — or nothing at all,
   in which case it looks in `inbox/`.

3. It reads the source, extracts the figures, writes the page and rebuilds the
   menu, then **shows you what it made and waits** before committing.

Source PDFs under 1 MB are committed to `assets/pdf/` and linked from the page.
Anything larger is left out and the page links the original instead.

### If the environment can't reach the web

Claude Code on the web runs behind an egress proxy that allows GitHub and the
package registries but not the open web, so fetching an article URL there fails
with a 403. Save the page yourself — print to PDF, or Save Page As — drop it in
`inbox/`, and run:

```
/add-resource inbox/saved-article.pdf
```

Run from Claude Code on your own machine, URL fetching works normally.

## Layout

```
index.html              generated menu — do not hand-edit
pages/<slug>.html       one page per resource, also generated
assets/style.css        the whole design system, light + dark
assets/app.js           search, filters, theme toggle, TOC, progress bar
assets/images/<slug>/   figures extracted from that resource
assets/pdf/<slug>.pdf   source PDFs, only when under 1 MB
data/library.json       metadata for every resource — the source of truth
data/tags.json          the tag vocabulary
inbox/                  drop folder (git-ignored)
.claude/skills/add-resource/   the skill and its scripts

CLAUDE.md               conventions and gotchas, for working on this repo
TASKS.md                backlog for the skill, the extractors and the HTML
LEARNINGS.md            what each extraction session taught us
```

`index.html` is regenerated from `data/library.json`. Edit the JSON (or better,
re-run the skill) and rebuild:

```bash
python3 .claude/skills/add-resource/scripts/rebuild_index.py
```

The library data is baked into `index.html` as an inline array rather than
fetched, so the page behaves identically over `file://` and over HTTP.

## Running it locally

```bash
python3 -m http.server 8000     # then open http://localhost:8000
```

Extractor dependencies, needed only when adding a resource:

```bash
pip install -r .claude/skills/add-resource/scripts/requirements.txt
```

## Publishing

Enable GitHub Pages once, by hand: **Settings → Pages → Deploy from a branch →
`main` / `/ (root)`**. `.nojekyll` is already present so Pages serves the files
as they are. Every path in the site is relative, so nothing needs configuring
for the site's URL.

Note that publishing makes the repo's contents public, including any source PDFs
committed under `assets/pdf/`.

## A note on the explanations

Every page is a plain-English retelling written from the source, not a
substitute for it. For the authors' own words, the exact numbers and the full
method, follow the source link at the top of each page.
