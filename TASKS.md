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
- [ ] **Margin captions defeat the caption matcher entirely.** Session 7's source is a
      Tufte-style LaTeX book, which sets `Figure N:` captions in a wide side margin rather
      than beneath the artwork. Every one of the 42 candidates came back with an empty
      `caption`, and the region pass matched only 2 of the source's 39 figures. The
      figure-number-to-page mapping had to be rebuilt by hand by reading the body text. The
      layout is common — `tufte-book`, `tufte-handout`, and most O'Reilly-style trade
      typesetting. Fix: detect a persistent narrow text column offset from the main block
      and search it for caption patterns before falling back to the below-artwork band.
- [ ] **The PDF's own metadata is ignored when it is right.** Session 7's `pdf_metadata`
      block carried `title: "Situational Awareness"`, `author: "Leopold Aschenbrenner"` and
      `creationDate: D:20240606` — all correct — while the heuristics returned the
      letter-spaced `"S I T U AT I O N A L AWA R E N E S S"`, an empty author string, and
      the year **2027** (a year scraped from the argument, not the document). The extractor
      already reads and stores `doc.metadata`; it just does not consult it. Fix: prefer a
      non-empty, plausible `doc.metadata` field over the heuristic, and report when the two
      disagree so the mismatch is visible rather than silent.
- [ ] **Letter-spaced display type breaks the title heuristic.** LaTeX title pages often
      set the title with wide tracking, which PyMuPDF reports as literal spaces between
      glyphs. Cheap fix: when the largest-text candidate is mostly single-character tokens,
      collapse the intra-word spacing before accepting it.
- [x] **`find_arxiv_id()` could confidently identify the wrong paper.** It searched the
      *entire* document text for an `arXiv:NNNN.NNNNN` pattern and returned the first match,
      with no check that the match was near the front matter where a paper's own
      self-identification lives. On the Claude Opus 5 System Card — a corporate PDF with no
      arXiv presence at all — it matched a footnote three pages in, citing an unrelated paper
      ("Lee, S., & Brumley, D. (2026). ExploitBench... arXiv:2605.14153"), and confidently set
      `source_url` to that paper's abstract page. Worse than session 2/3/7's
      empty-or-wrong-author findings, because a plausible wrong URL reads as more trustworthy
      than an honestly empty field. **Fixed session 9**: `extract_pdf.py` now calls
      `find_arxiv_id(head)` (the same first-4000-characters front-matter slice already used
      for `find_year`) instead of `find_arxiv_id(full_text)`. Regression-tested against the
      same source: `source_url` now comes back `null` instead of the wrong paper's link.
- [x] **`extract_pdf.py`'s own summary print crashed on Windows cp1252 when extracted text
      contained a non-cp1252 character** (a literal zero-width space, U+200B, inside a title,
      surfaced this in session 9). Session 8 fixed this for *review* scripts printing
      excerpts; the extractor's own `main()` still wrote its final `json.dumps(...)` straight
      to stdout with no UTF-8 wrapper. **Fixed session 9**: `main()` now calls
      `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` before anything is printed.
      Regression-tested: the same PDF now extracts cleanly with no `PYTHONIOENCODING` env var
      set.

## Article branch

- [x] **Never run end to end.** Done in session 6 (12-factor-agents), from a saved `.html`
      with `--url`. `trafilatura` handled a custom single-`<main>` layout cleanly and the
      text came across complete; the bugs were all in the image path, below.
- [ ] **The 40-image cap is a truncation, not a filter.** `extract_article.py:178` takes
      `candidates[:40]`. On the 12-factor source the first 40 unique URLs were shields.io
      badges, nav thumbnails and contributor avatars, so the cap would have spent itself on
      junk and silently dropped the real diagrams. Filter first — drop known badge hosts
      (`shields.io`), tracking pixels (`scarf.sh`), avatars (`avatars.githubusercontent.com`)
      and anything below `MIN_IMAGE_SIDE` — *then* apply a cap, and report what the cap cut.
- [ ] **Animated GIFs need a policy.** Pillow saves frame 0, which for a build-up animation
      is a near-empty title frame. Session 6 found the *last* frame is reliably the complete
      diagram, and that repos often ship an explicit `-static.png` counterpart. Encode both:
      prefer a static sibling, else `seek(n_frames - 1)`, and record `frames` in the figures
      JSON so the skill knows to look.
- [ ] **Hotlinked images are a latent broken link.** When a download is blocked the figure
      is recorded with `hotlinked: true` and the page references the remote URL. Decide
      whether to allow that at all, or to always require a locally saved copy. Session 6
      argues for never: `CLAUDE.md` permits exactly one external dependency.
- [ ] **Saved-HTML path needs a real test** against a "Webpage, Complete" save, which
      rewrites image paths to a local `_files/` directory. Session 6 used a single-file
      render with absolute remote URLs, so this variant is still untested.
- [ ] **Nothing warns when a downloaded figure goes unused.** Session 6 caught three only by
      diffing the manifest against the images the page actually referenced, and caught a
      *lost* figure the same way. `make_page.py` could compare `assets/images/<slug>/`
      against the `src`s in the built page and print both lists.

## Site and HTML

- [ ] **Full-text search.** The index currently searches title, authors, venue, tags and
      the card hook only. Fine at a handful of resources, weak past ~20. Bake a
      per-resource text index into `index.html` at rebuild time and search that — keeping
      it inline so the page still works over `file://`.
- [ ] **Cross-links between resources.** No way to say "this paper responds to that one".
      Add a `related` field to the content JSON, render it as a footer block, and make it
      bidirectional at rebuild time. The field guide now links to the context engineering
      survey by hand, from prose and from its bibliography entry — which works, and is
      invisible from the survey's side. A `related` field would make the link bidirectional
      and would have prompted the connection rather than leaving it to be spotted in an audit.
- [ ] **Nothing checks that a page cites anything.** `verify_page.py` catches dangling and
      unused bibliography ids but not a section that makes sourceable claims and cites
      nothing. The field guide's context-engineering chapter shipped in exactly that state
      after unsourced claims were stripped and no replacement was added. A cheap heuristic:
      warn when a section is over ~300 words, contains no `class="cit"`, and is not the
      glossary or the sources list. **Second justification, session 8:** the situational
      awareness page's `scorecard` is ~700 words, carries every claim the page makes about
      what happened *after* the source was written, and cites nothing — the one section a
      reader most needs to check is the one with no apparatus. The heuristic would have fired.
- [ ] **A page that scores a dated source needs a second kind of citation.** The retrospective
      section of a forecast page makes claims about the world, not about the source, so the
      bibliography — which lists what the *source* leaned on — cannot support them and
      `verify_page.py`'s dangling/unused checks pass trivially. Session 8 found four
      outside-the-document claims sitting in prose that reads as sourced (the author's age,
      his dismissal, Ilya Sutskever's departure, the fund launched afterwards), one of which
      was simply wrong. Options: a distinct `biblio` block for post-publication sources, or a
      convention that such claims are marked in the text. Either way the writing guide should
      say that a scorecard's evidence is the page's own responsibility.
- [ ] **Personal notes block.** A place for your own commentary on a resource, visually
      distinct from the explanation, so the page is not purely a summary.
- [ ] **`make_page.py` does not validate citations.** It should fail when an
      `<a class="cit" href="#rN">` has no matching `<li id="rN">`, rather than leaving it
      to the checklist.
- [ ] **A class one level off from the CSS selector's expected nesting fails completely
      silently — three instances in one session.** `figure.wide` on the `<img>` inside a
      figure instead of the `<figure>` itself; `blockquote cite` written as a sibling
      `<p><cite>…</cite></p>` right after `</blockquote>` instead of inside it; `.figsrc`
      used on a `<p>` under a table instead of inside a `<figcaption>`. All three produce no
      error, no visual difference an author would flag from memory, and no console warning —
      only a computed-style/geometry check (`getBoundingClientRect().width`,
      `getComputedStyle(...).fontSize`) catches them, because the wrong nesting still parses
      as valid HTML and just never matches the selector. Worth a real fix rather than three
      more entries here: either have `make_page.py` walk the generated HTML and warn on
      `img.wide`, `cite` not inside `blockquote`, and `.figsrc`/`.figlabel` outside
      `figcaption`, or add a `verify_page.py` assertion that checks computed styles for every
      instance of each scoped class against a plain control element, the way session 9's
      review caught these.
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
      `.topbar__crumb`, `.hero__meta`, `.figsrc`, `.callout__label` and the figure captions'
      source line. Dark mode passes at 4.79:1. Re-measured independently in session 6 on a
      fourth page, same numbers. The field guide's widgets sidestepped it by using `--ink-soft`,
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

- [x] **`assets/scripts/` is now a documented convention.** Session 9 committed
      `assets/scripts/claude-opus-5-system-card.build_content.py` — a per-resource Python
      script that regenerates the gitignored content JSON, so the page can be reproduced
      without the source PDF. Formalized in `CLAUDE.md`'s "Conventions that matter" rather
      than left as a one-off; it's still an authoring tool inside the tree GitHub Pages
      serves (a partial answer to the item below, not a full one — the content JSON itself
      still doesn't survive in history, only the means to regenerate it).
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

- [ ] **`recover_content_json.py --verify` fails on every existing page.** Not a page
      defect — the script says so itself — but it means the one tool offered as a
      pre-edit safety gate reports failure by default, which trains you to ignore it. Two
      causes, both cosmetic: the committed HTML hard-wraps the colophon paragraph where a
      rebuild emits one line, and it carries a literal `'` where a rebuild escapes `&#x27;`.
      Either normalise the committed pages once, or have the verifier compare on normalised
      whitespace and entities.
- [ ] **`python3` does not exist on Windows.** Every command in `CLAUDE.md`, `SKILL.md` and
      the script docstrings is written `python3`; on Windows only `python` resolves, and the
      shim prints a Microsoft Store advert instead of failing usefully. Either write plain
      `python`, or say once at the top that Windows users should substitute it.
- [x] **`verify_page.py` cannot run on Windows.** It hardcoded
      `CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"` and passed it as
      `executable_path`, so the repo's only browser-assertion harness failed immediately on
      a Windows checkout, where Playwright installs under `%LOCALAPPDATA%\ms-playwright`.
      Session 7 re-implemented the same checks in a scratchpad script to get them run; session
      8 fixed the script instead. `executable_path` is now only passed when the
      `AI_LIBRARY_CHROMIUM` env var is set, so Playwright resolves its own bundled browser by
      default and the pinned-path case the constant was written for still works.
- [ ] **The depth rubric has no row for a multi-part source.** `SKILL.md` tops out at
      "20–30 min (~5,000–8,000 words)" for "a dense methods paper, or a long-form essay".
      Session 7's source is *five* essays totalling ~52,000 words across 165 pages; covering
      each argument, plus a retrospective, came to ~9,900 words / 45 min. Compressing to the
      ceiling would have meant dropping a source chapter or reducing arguments to assertions,
      which the writing guide forbids elsewhere. Add a row for a book-length or multi-part
      source, or say explicitly that the ceiling is per-argument rather than per-page.
- [ ] **Tag vocabulary needs curating.** `data/tags.json` grows monotonically and nothing
      ever merges near-duplicates. Revisit once there are ~20 resources. Session 6 added
      `prompting` and `production`, taking it to 13; session 7 added `scaling`, `compute`,
      `forecasting`, `alignment` and `ai-policy`, taking it to 18. That jump is the vocabulary
      meeting its first resource that is not about building with LLMs — worth checking at the
      next non-technical ingest whether `scaling`/`compute` should merge.
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
