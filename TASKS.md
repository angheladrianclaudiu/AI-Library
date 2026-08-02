# Backlog

Improvements to the `/add-resource` skill, the extractors and the generated HTML.
Ordered roughly by value. Tick items off as they land; add new ones whenever
something turns out to be worth fixing but out of scope for the ingest at hand.

Evidence for most of these is in [LEARNINGS.md](LEARNINGS.md) — check there before
picking one up, since the failure that motivated it is usually recorded with the
source that caused it.

---

## Extraction

- [ ] **Author detection fails on stacked author blocks.** `guess_authors()` looks for
      several capitalised names on one line. Papers that print one author per line with
      affiliation superscripts return an empty string, which then has to be filled in by
      hand. Fix: when the line-based pass finds nothing, collect consecutive short lines
      between the title and the abstract that parse as names, and join them.
- [ ] **Two-column layouts are untested.** Every paper processed so far is single-column.
      In a two-column layout the caption's band spans the full page width, so the artwork
      cluster above it will likely pull in the neighbouring column. Needs a column-detection
      step, or at minimum a check that the crop's width does not exceed the caption's
      column by much.
- [ ] **Subfigures share one caption.** A "Figure 3: (a) … (b) … (c) …" block currently
      yields one wide crop. Usually acceptable, sometimes not — worth detecting `(a)`
      markers and offering the panels separately as extra candidates.
- [ ] **Rotated / landscape pages** are not handled; a sideways table or figure will crop
      to nonsense. Detect page rotation and rotate the pixmap before saving.
- [ ] **Scanned PDFs** produce no text and therefore no captions and no figures. Detect an
      empty text layer and either run OCR or fail loudly with an explanation.
- [ ] **Automate the crop sanity check.** The skill tells the reader to look at each crop
      before using it. A cheap machine check would catch most bad crops: run text
      extraction over the crop region and warn when it contains more than ~200 characters
      of prose, which almost always means body text leaked in.
- [ ] **Icon-built diagrams flood the candidate list.** A figure drawn as vector art decorated
      with clipart icons emits every icon as a separate embedded candidate: the context
      engineering survey produced 40 junk candidates against 7 real figures, all of them
      256 × 256 or 768 × 512 and so comfortably past `MIN_SIDE`/`MIN_AREA`. Size filters cannot
      fix this — the discriminator is position. Fix: drop an embedded image whose rect falls
      inside a region the caption pass already rendered, which the extractor knows at that point.
- [ ] **Reported word count includes the bibliography.** For the context engineering survey this
      meant 72,963 reported against ~28,000 words of actual content, the other 58% being a
      1,400-entry reference list. Any depth-rubric decision taken from the headline number is
      wrong for survey-shaped sources. Fix: detect the `References` heading and report content
      and bibliography word counts separately.
- [ ] **`guess_authors()` can return a confidently wrong value.** Recorded in TASKS as returning
      nothing on stacked author blocks; on a 15-author paper it returned just the first author.
      A truthiness check passes it. Whatever the fix, it should signal low confidence rather
      than silently emit one name.
- [ ] **Dedupe heuristic is crude.** `drop_redundant_regions()` compares a region against
      embedded image rects by area overlap at a fixed 0.85 threshold. Fine so far; will
      misfire on a figure that is a raster with vector annotations drawn over it.

## Article branch

- [ ] **Never run end to end.** `extract_article.py` is written and its blocked-egress path
      is exercised, but no article has been ingested in full, because this environment
      cannot reach the open web. First real run should be from a machine with normal
      access — expect to find bugs in image resolution and main-content extraction.
- [ ] **Hotlinked images are a latent broken link.** When a download is blocked the figure
      is recorded with `hotlinked: true` and the page references the remote URL. Decide
      whether to allow that at all, or to always require a locally saved copy.
- [ ] **Saved-HTML path needs a real test** against a "Webpage, Complete" save, which
      rewrites image paths to a local `_files/` directory.

## Site and HTML

- [ ] **Full-text search.** The index currently searches title, authors, venue, tags and
      the card hook only. Fine at a handful of resources, weak past ~20. Bake a
      per-resource text index into `index.html` at rebuild time and search that — keeping
      it inline so the page still works over `file://`.
- [ ] **Cross-links between resources.** No way to say "this paper responds to that one".
      Add a `related` field to the content JSON, render it as a footer block, and make it
      bidirectional at rebuild time.
- [ ] **Personal notes block.** A place for your own commentary on a resource, visually
      distinct from the explanation, so the page is not purely a summary.
- [ ] **`make_page.py` does not validate citations.** It should fail when an
      `<a class="cit" href="#rN">` has no matching `<li id="rN">`, rather than leaving it
      to the checklist.
- [ ] **SlopCodeBench's bibliography is uncited.** `verify_page.py` reports all five entries
      (`r1`–`r5`) as cited by nothing: the page carries no `class="cit"` markers at all, so
      its Sources section reads as a further-reading list rather than an apparatus. Either
      wire the claims to it or rename the section to say what it is. Blocked on the
      regenerate-from-a-fresh-clone problem below — the page cannot be edited without first
      reconstructing its content JSON.
- [ ] **Read-time estimate ignores figures and tables.** 220 wpm over body words only;
      a figure-heavy page reads longer than it claims.
- [ ] **Re-ingesting a resource wipes its image folder.** `extract_pdf.py` clears
      `assets/images/<slug>/` on every run, so re-running against an existing resource
      deletes the curated figures before the page is rebuilt. Add a `--keep-images` flag
      or write candidates to a staging directory.
- [ ] **Figures sit on a white plate in dark mode.** Correct and legible, but a light
      rectangle in a dark page. Consider a per-figure `invert` opt-in for line charts
      where inversion actually works.
- [ ] **The field guide's four practice chapters have no model outputs.** Prompting,
      retrieval, tool loops and evals were written around live API calls, which a static site
      cannot make. They currently ship as prompts, criteria and commentary with nothing
      generated — honest, and weaker than the A/B contrast they were built for. The
      `.fg-tr` / `.fg-tr__body` transcript components already exist in `style.css`, unused:
      drop in real recorded outputs labelled with the model and the date they were captured.
      Never synthesise them.
- [ ] **Open Graph tags** so a shared link previews with the title and a figure.
- [ ] **Accessibility pass.** Check contrast ratios against WCAG AA in both themes,
      keyboard operation of the tag chips, and focus order through the index controls.
      Measured evidence now exists: `--ink-faint` is **4.08:1** on `--bg-raised` in light
      mode, below the 4.5:1 requirement, and it is the colour of `.card__read`,
      `.topbar__crumb`, `.hero__meta`, `.figsrc` and the figure captions' source line. Dark
      mode passes at 4.79:1. The field guide's widgets sidestepped it by using `--ink-soft`,
      but the token itself should be darkened — roughly `#6b747b` clears AA while staying
      visibly lighter than `--ink-soft`. Check every existing page after changing it.
- [ ] **Heatmap cells are mouse-only.** The attention grid in `fieldguide.js` paints
      `div.fg__cell` with a `title` attribute, so the per-pair weights are unreachable by
      keyboard and only summarised for a screen reader by the grid's `aria-label`. Either
      make each row focusable with its weights in an accessible name, or offer the matrix as
      a real `<table>` behind a toggle.
- [ ] **Widget verification lives in the scratchpad.** The field guide ships 44 behavioural
      assertions — sliders move readouts, the KV figure matches its formula, top-k
      renormalises, both themes repaint — and none of them are in the repo, so the next
      change to `fieldguide.js` has nothing to run. Promote the harness to
      `.claude/skills/review-resource/scripts/verify_widgets.py` alongside `verify_page.py`.

## Process

- [ ] **A published page cannot be regenerated from a fresh clone.** `.gitignore:9`
      matches `*.content.json` repo-wide, so the content JSON — the only editable
      representation of a page — never enters history. `pages/*.html` is generated and
      must not be hand-edited, so the moment the ingest session's `inbox/` is gone, a
      published page can only be corrected by reconstructing its JSON out of the HTML
      it produced. That is exactly what reviewing the context engineering survey cost:
      a parse of the generated page back into sections, validated by rebuilding and
      diffing to byte equality before any edit was safe. It round-tripped, but nothing
      guarantees that — a future template change would break the parse, and the
      reconstruction silently loses any field the template does not emit.
      Fix: commit the content JSON. Either narrow the ignore rule to `inbox/` and store
      them in a `content/` directory, or have `make_page.py` write a copy next to the
      page it builds. The source PDF still stays out of history; only the JSON needs to
      survive.

- [ ] **Tag vocabulary needs curating.** `data/tags.json` grows monotonically and nothing
      ever merges near-duplicates. Revisit once there are ~20 resources.
- [ ] **Batch ingest.** One resource per run is right for quality, but a queue mode for
      several PDFs at once would save repeated setup.
- [ ] **Enable GitHub Pages** — Settings → Pages → Deploy from a branch → `main` / root.
      Manual, one time, and it makes the repo and any committed PDFs public.

---

## Done

- [x] Recover vector figures by rendering the region above a caption — the embedded-image
      pass alone found zero figures in the first real paper.
- [x] Stop page logos and neighbouring captions leaking into figure crops.
- [x] Keep numeric table cells from breaking mid-value; let wide tables use the margin.
