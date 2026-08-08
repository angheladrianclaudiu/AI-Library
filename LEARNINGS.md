# Learnings

What extraction sessions have actually taught us. Most of the tuning constants in
`extract_pdf.py` exist because of a specific failure recorded here — **read this before
changing them**, and add a section after every ingest.

Record what the source looked like, what broke, and what the fix was. A learning
without the source that produced it is not much use to the next session.

---

## The short version

- **Embedded-image extraction alone is not enough.** In the first real paper it found
  **zero** figures. Academic charts and architecture diagrams are vector art — PDF path
  operators — and `page.get_images()` cannot see them at all. The caption-region renderer
  is not a fallback; for ML papers it is the primary path.
- **Cropping is the hard part, and it fails in both directions.** Too tight and you slice
  off the legend; too loose and you get a slab of body text. Both failures happened, one
  after the other, on the same paper.
- **Every crop needs looking at.** Both bad crops were invisible in the JSON metadata and
  obvious the moment the image was opened.
- **Metadata heuristics fail quietly.** An empty `authors` field is easy to miss and ends
  up as a page with no byline.

---

## Session 1 — synthetic test PDF (scaffold)

**Source:** a generated three-page "paper" with a vector diagram, an embedded raster, a
tiny logo and a table caption. Built specifically to exercise both extraction passes.

**What it taught:**

- The two passes are genuinely complementary: the vector diagram existed only as paths,
  the heatmap only as an embedded raster. Either pass alone would have found half.
- **A `Table N:` caption must not trigger a figure crop.** Tables extract as text and
  render as a garbled image. Captions are matched but filtered on `is_table`.
- **Small images pollute the artwork union.** A 48 × 48 logo in the page corner sat inside
  the search band, so unioning every image in the band stretched the crop from the logo
  down to the real figure, swallowing a heading and a paragraph on the way. Fixed by
  discarding marks under `MIN_ART_SIDE` (28 pt) and by clustering what remains vertically,
  keeping only the cluster nearest the caption.
- **Both passes find a raster figure**, producing a duplicate. The embedded copy is the
  original at full resolution, so the rendered region is dropped when an image covers more
  than 85% of it.
- A decorative PDF with no `Figure N:` captions and no rasters correctly yields **zero**
  candidates. Worth keeping: no false positives is as important as no misses.

**Caveat on this session:** a synthetic PDF is a weak test. Every bug in session 2 was in
code this session had "passed".

---

## Session 2 — SlopCodeBench (arXiv:2603.24755)

**Source:** 26 pages, single-column, ~12k words. Six figures, all matplotlib or TikZ.
663 KB. A dense methods paper with four separate result threads.

**What worked first time:**

- Title, via the largest-text-on-page-1 heuristic — including skipping the arXiv stamp
  printed sideways down the left margin, which is why that check exists.
- arXiv ID recovered from the paper's own text, giving a correct `source_url` with no
  input. This is the reliable path for arXiv preprints; expect to supply the URL by hand
  for anything else.
- Year detection, `Table N:` filtering, and the size/aspect filters.

**What broke:**

1. **All six figures were vector.** The embedded pass returned nothing. If the region
   renderer had not existed, this page would have had no figures at all — and the
   extractor would have reported success.

2. **Sub-labels sliced off.** Figure 1's crop ended exactly at the artwork's bounding box,
   cutting the "Solution 1 / Good Quality" row of labels beneath it. Text absorption only
   considered blocks that *intersected* the artwork, and these sat in the gap below it.
   Fixed with `TEXT_REACH` (14 pt) — text within that distance is absorbed.

3. **That reach then over-absorbed.** On Figure 2, an axis title reached up to the caption
   of the table above it; the second absorption pass then took the whole caption, and the
   crop acquired three lines of prose and a table row. Two fixes, kept together:
   - `MAX_TEXT_GROWTH` (34 pt) caps total expansion beyond the artwork.
   - `MAX_LABEL_CHARS` (120) excludes long blocks entirely. **This is the load-bearing
     one.** A figure's own text — axis titles, legends, node labels, "Solution 1" — is
     always short; a caption or paragraph is not. Length discriminates better than
     geometry does.

4. **Author detection returned an empty string.** Nine authors printed one per line with
   affiliation superscripts. `guess_authors()` wants several capitalised names on a single
   line and found none. Filled in by hand from page 1. Logged in
   [TASKS.md](TASKS.md); until it is fixed, **check the `authors` field on every ingest.**

**Non-extraction findings from the same session:**

- **Numeric table cells break mid-value.** `0.68 ± 0.20` wrapping after the `±` is
  unreadable. `table.numeric` sets `white-space: nowrap`; prose tables leave it off.
- **A wide results table clips inside `.table-scroll`.** Six columns exceeded the reading
  measure, so the last column was cut off with no visible scroll affordance —
  indistinguishable from a rendering bug. `.table-scroll.wide` lets it use the right
  margin, reusing `figure.wide`'s escape.
- **The paper contradicted its own figure.** The body text and Figure 6's caption both say
  error-handling tests drive the decline in pass rates; as plotted, the error line is the
  highest of the three and falls least. Flagged on the page in a caveat box. Worth
  reading figures against the prose rather than trusting captions — a caption is the
  authors' claim about a figure, not the figure.

**Tooling notes for this environment:**

- A full-page Playwright screenshot of a 23-minute page times out at
  `device_scale_factor=2`. Use 1 for full-page shots, keep 2 for close-ups, and raise the
  screenshot timeout.
- Close-ups scrolled to a specific selector are far more useful for judging a page than a
  full-page capture, which compresses to an unreadable strip.
- Google Fonts is blocked by the egress policy, so screenshots here render in fallback
  faces. Not a page defect — but it means local screenshots cannot verify typography.
- Browser assertions caught a layout bug that eyeballing missed: `figure.wide` never
  escaped the reading measure, because the figure sits inside `<section>` and so was never
  a grid item of the page grid. Fixed with `section:has(> figure.wide)`.

---

## Session 3 — A Survey of Context Engineering for LLMs (arXiv:2507.13334)

**Source:** 166 pages, single-column, 72,963 words — by far the largest source so far. Seven
figures, all vector diagrams built from clipart icons, plus eight tables. 3.6 MB.

**What worked first time:**

- **Title, arXiv ID and `source_url`.** Third paper in a row where the arXiv ID was recovered
  from the paper's own text. This path is reliable; keep trusting it for preprints.
- **All seven region crops were clean on first inspection.** No slicing, no absorbed body
  text. The constants tuned in session 2 (`TEXT_REACH`, `MAX_TEXT_GROWTH`, `MAX_LABEL_CHARS`)
  held on a completely different figure style — icon-heavy TikZ rather than matplotlib. First
  time the crop logic has needed no intervention at all.
- **`drop_redundant_regions()` correctly kept all seven.** Pages 13, 31, 38 and 42 each carried
  a dozen embedded icons *inside* the figure region, and the 0.85 area-overlap threshold did not
  fire. The crude heuristic flagged in TASKS.md survived a case that could plausibly have broken it.

**What broke:**

1. **The embedded pass produced 40 candidates and every one was junk.** This paper's figures are
   vector diagrams decorated with clipart icons, and each icon is an embedded raster of
   256 × 256 or 768 × 512. Those clear `MIN_SIDE` (120) and `MIN_AREA` (25,000) comfortably, so
   all 40 were emitted as figure candidates with the caption of whatever figure they sat inside.
   Ratio of noise to signal was 40:7. **New failure mode**, distinct from session 1's single
   stray logo: there the icons polluted a *crop*, here they pollute the *candidate list*.
   Logged in TASKS.md — the fix is probably to drop embedded images whose rect falls inside an
   already-rendered figure region, which is information the extractor already has.

2. **`guess_authors()` returned `"Lingrui Mei"` — the first of fifteen.** Session 2 recorded this
   function returning an empty string on a stacked author block; here it returned a *plausible
   but wrong* value, which is worse, because an empty field is obviously broken and a
   single-author string is not. Anything that only checks for truthiness will pass it.
   **Check the author field by eye, not by `if authors:`.**

3. **The extractor's word count is misleading for a survey.** It reported 72,963 words, which
   implies something around a 5½-hour read. In fact pages 1–59 hold ~28,000 words of content and
   pages 59–166 are a 1,400-entry bibliography — 58% of the reported words are references. Any
   depth decision made from the headline number would have been badly wrong. Logged in TASKS.md.

**Non-extraction findings:**

- **The figure contradicted itself again, in a new way.** Figure 2's timeline axis runs
  2020, 2021, 2023, 2024, 2025, 2025.07 — **2022 is missing**, though branches clearly pass
  through it. As in session 2, the caption does not mention it. Two for two on figures that do
  not survive being read against the prose; treat this as the default expectation, not bad luck.
- **The paper's own reasoning has a soft spot worth flagging on the page.** It attributes LLMs'
  weak self-validation to "fundamental limits identified in Gödel's incompleteness theorems",
  which is a category error — incompleteness is about provability in formal arithmetic systems,
  not about whether a network can check its own output. Flagged in a caveat.
- **A survey needs claims separated from evidence more aggressively than a methods paper.**
  Every number in this source is quoted from another paper under that paper's conditions, and
  the headline finding (the comprehension–generation asymmetry) is an impression formed from
  reading rather than anything measured. Both facts needed saying explicitly, twice, or the page
  would have read as though the survey had established them.
- **Forcing the standard methods-paper skeleton onto a survey worked better than expected.**
  `results` became "what the synthesis establishes, and how firmly", which turned out to be the
  most useful section on the page precisely because it forced the claim/evidence split. The
  writing guide's own advice to adapt the skeleton was not needed here.

**Tooling notes for this environment:**

- **arXiv is blocked** — `curl` on both the PDF and the HTML returns `CONNECT tunnel failed, 403`,
  and `WebFetch` on the abs page returns 403. The route that worked was the user pushing both
  sources into the repo and this session pulling them with `git show <ref>:<path> > inbox/…`,
  which moves a 3.6 MB blob without it ever entering the model's context.
- **`WebFetch` reaches `raw.githubusercontent.com`** even though the open web is blocked. Useful
  for reading metadata out of a large file already in the repo without loading it.
- **A blocked-request console message does not contain the URL.** Filtering console text for
  "fonts.googleapis" therefore never matches; listen to the `requestfailed` event and inspect
  `request.url` instead. Cost a debugging round.
- **A table inside `.table-scroll` is *supposed* to be wider than the viewport.** An assertion
  that no element exceeds the phone width will fail on a correct page. Assert instead that the
  *scroll container* fits and that `scrollWidth > clientWidth`. Nearly "fixed" a non-bug.

---

## Session 4 — reviewing the context engineering page (no new ingest)

**Source:** the session 3 page itself, 8 sections and ~5,200 words, re-checked against
`2507.13334.pdf` recovered from git history. No extraction ran. Two adversarial subagents
were briefed independently — one on fidelity to the source, one on craft against the
writing guide — and their reports reconciled against the PDF before anything was changed.

**What the review found:**

1. **The `tldr` field silently ate its own markup.** The "In short" block — the first thing
   on the page — rendered `<strong>context engineering</strong>` and `<em>understanding</em>`
   as visible text. `as_paragraphs()` passes an item through untouched only when it starts
   with `<`; anything else is escaped and wrapped in `<p>`. The tldr entries were bare
   sentences carrying inline tags, so they took the escaping path. **Wrap every tldr entry
   in its own `<p>`.** Worth noting how this survived session 3: the defect is invisible in
   the content JSON, invisible in a diff of the generated HTML unless you know to look, and
   the checklist has no line for it.
2. **Four factual slips, all of the same species: a source sentence compressed one step too
   far.** The worst was "WebArena | Web tasks across 137 sites" — p.48 reads "WebArena *and
   Mind2Web* … spanning 137 websites", a joint figure narrowed onto one benchmark, where it
   is simply false. Also `c_instr` gaining "persona" (p.9 says "System instructions and
   rules"), MCP described as standardising "agent-to-tool access" (p.42: "agent-environment
   interactions"), and a component-vs-system-level comparison attributed to the survey that
   §6.1.1 and §6.1.2 never draw. **A quoted number carries its scope with it; check what the
   subject of the source's sentence actually was.**
3. **A corrupted author name in the bibliography.** "Guangzhi Xiao" for Guangxuan Xiao. The
   other ten entries verified exactly. A plausible-looking name is unfalsifiable by eye —
   check every cited name against the source's own reference list, which for a survey is
   right there.
4. **The page counted tokens 19 times without ever saying what one is**, and carried
   chain-of-thought through three results including 17.7% → 78.7% without defining it. Both
   are so basic they read as already-defined. **The terms that go unglossed are not the
   exotic ones — they are the ones so fundamental the writer stops seeing them.** The
   glossary made this worse by looking complete: twelve entries, ten of which restated a
   definition the prose had already given, while token and chain-of-thought had none.

**What held up.** Every deliberate critical judgement survived independent checking: the
comprehension–generation asymmetry really is never quantified (§7.1.2 leaves the cause open
between architecture, training and computational limits); the Gödel quotation on p.24 is
verbatim, and the paper pins *statelessness* on incompleteness too, so the page understated
it; and Figure 2's axis really does read 2020, 2021, 2023, 2024, 2025, 2025.07. All four
equations, the six components, the 15-author list, the abstract blockquote and roughly
twenty quoted numbers checked out. **The page was accurate; it was the compressions and the
undefined basics that failed.**

**On running adversaries.** Briefing both agents to prove a thesis rather than "review this"
produced specific, quotable findings — but both over-reported, and one finding had to be
rejected outright: the fidelity agent read §6.3.2's "approximately 20% improvement" and
called the page's "20 percentage points" a unit error, missing §4.2.2 (p.18), which says
"20% **absolute** performance improvement" — which is percentage points. **A subagent quoting
one passage has not shown the paper says it only once.** Verify each finding at its primary
occurrence before acting. The craft agent's recommendation to delete the redundant glossary
entries was also rejected: a glossary is a random-access lookup, so restating a body
definition is the point.

**Tooling notes for this environment:**

- **The content JSON was gone and had to be reconstructed from the generated HTML** —
  `.gitignore` matches `*.content.json` repo-wide. Parsing `<section>` bodies back out and
  rebuilding to a byte-identical page is what made editing safe, and it is pure luck that the
  round-trip was exact. Logged in TASKS.md; this is the review's most important finding about
  the machine rather than the page.
- **Recovering a deleted 3.6 MB source from history costs nothing in context:**
  `git show <ref>:<path> > inbox/…` after `git fetch --unshallow`. Session 3's route in still
  works as a route back.
- **Rebuild-and-diff is the reconstruction test.** Before changing a word, rebuild from the
  reconstructed JSON and diff against the committed page. Anything other than an empty diff
  means the JSON is wrong, not the page.

---

## Session 5 — The Machinery of Language Models (llm-field-guide)

**Source:** no source. The first `type: "guide"` resource — original material written for this
library rather than explained from an outside document. It arrived as a 1,322-line
self-contained HTML file with its own design system, twelve chapters and eight interactive
widgets, after two rounds of review against an earlier React version. No PDF, no extractor,
no figures. 6,691 words, 30-minute read.

**What worked first time:**

- The whole extraction half of the pipeline was simply not used. `make_page.py` took the
  content JSON and produced a correct page on the first run; the template's `sec-num`,
  `details.toc` and progress bar meant the incoming file's bespoke masthead, chapter rail and
  TOC could all be deleted rather than ported.
- `a.cit` + `ol.biblio` needed no adaptation at all — the incoming file had already adopted
  the house citation pattern, so ten references dropped straight in and `verify_page.py`
  confirmed no dangling or unused ids.
- Writing the content JSON from a Python builder script rather than by hand. 14 sections of
  HTML with quoted attributes inside JSON strings would have been miserable to author
  directly; a script with triple-quoted blocks and `json.dump` made it readable and let the
  whole thing be regenerated after every fix.

**What broke:**

- **`verify_page.py` failed a figureless page.** `check(count > 0, "the page has no images at
  all")` is right for a paper — zero images means the figure pass silently produced nothing —
  and wrong for a guide, which can legitimately carry none. Now conditioned on the page
  declaring `<figure>` elements, so it still catches the real failure.
- **The demo vocabulary did not contain the demo sentences' words.** The stand-in merge table
  shattered "board" into `b|o|a|rd` and "Routing decides" into `R|out|ing|d|e|c|i|d|es`. That
  is a fair illustration of what happens to a rare word, and it destroyed the two chapters
  built on it — attention and routing are about relationships between *words*, and single
  letters have none. Nine words added to `VOCAB`; the orphan-absorbing guard in `tokenize()`
  then merges the trailing fragment, so adding "approve" yields "approved" whole. Caught by
  screenshot, not by any assertion — the widget tests all passed while the heatmap was
  labelled with single letters.
- **Two cost curves on one scale invented a fact.** The prefill/decode chart normalised both
  series against prefill's maximum, so they crossed at 1024K and invited the reading that
  prefill starts costing more than decode there. That crossing is an artifact of the units:
  prefill FLOPs and decode FLOPs are not the same quantity. Each series is now scaled to its
  own maximum, so the chart claims only curvature. The stacked-bar version this replaced had
  a second bug — at the long end the two bars wanted 189% of a fixed-height flex column and
  got shrunk, flattening the curve exactly where the argument needed it steepest.
- **`--ink-faint` fails WCAG AA in light mode.** 4.08:1 on `--bg-raised`, against a 4.5:1
  requirement, and it was the natural token for every small mono label in the widgets. Five
  widget rules moved to `--ink-soft` (8.06:1). The token itself is untouched — it is used
  across the existing pages and fixing it site-wide is the open accessibility item in TASKS.

**Non-extraction findings:**

- **A contrast script that walks up for a background must match the browser's string.** The
  first version compared against `'rgba(0,0,0,0)'` while `getComputedStyle` returns
  `'rgba(0, 0, 0, 0)'` with spaces, so the walk never ran and everything was measured against
  black. It reported the badge at 2.17:1 when the real figure was 7.87:1, and it reported dark
  mode as passing for the wrong reason. A measurement harness that cannot be wrong is worth
  more than one that is merely convenient.
- **Widget assertions and screenshots catch disjoint sets of bugs.** 44 behavioural checks —
  probabilities summing to 100%, the cache matching its formula, entropy rising with
  temperature, top-k renormalising — all passed on a page whose heatmap axes read
  `b o a rd`. Conversely the screenshots would never have caught the LoRA 7/4 matrix ratio.
  Both passes are needed; neither substitutes.
- **Theme repainting needs a MutationObserver, not a media query.** The toggle sets
  `data-theme` on `<html>`, which fires no `matchMedia` event. Watching the attribute *and*
  the OS preference covers both routes, and re-reading the palette on each is enough — no
  widget caches a colour beyond one render.
- **A `guide` needed three small machine changes, all of which generalise:** a third `type`,
  an `{{EXTRA_SCRIPTS}}` hook so a page can carry local JS without anyone hand-editing
  generated HTML, and a `colophon_note` because the footer's standing "read the original for
  the authors' own words" promise is simply false for original material.

**Post-publication audit — two things the build passed and the page still got wrong:**

- **A de-citing pass leaves a hole, and nothing warns you.** Stripping the unsourced claims out
  of the context-engineering chapter took it from four assertions to none and left it the
  thinnest substantive chapter on the page — 331 words against 656–912 for its neighbours.
  Every check passed; word count per section is not something anything measures. The review
  that removed the claims had already identified the replacement — a survey *already published
  in this library* — and the port simply lost the note. Worth a habit: after removing a claim,
  record what should go in its place, in the same pass.
- **The demo corpus asserted invented commercial terms under a real company's byline.** The
  retrieval widget shipped five policy documents opening "Sarmisoft accepts returns within 21
  days of delivery…" — a 15% restocking fee, 400 RON free-shipping threshold, 24-month
  warranty, bulk tiers — all invented, on a page bylined Sarmisoft, with the chapter saying
  "nothing in any model's training data contains this company's restocking fee." The word
  "stand-in" appeared once on the whole page and it was about the tokenizer. Fixed at source by
  renaming the vendor to a plainly fictitious one rather than by disclosure alone: a caveat a
  reader might skip is weaker than a name that cannot be mistaken. **Demo data that looks like
  real business data needs a fictitious name, not a footnote** — especially when the byline
  makes the attribution plausible.
- **Interviewing the author beat guessing at their experience.** Four questions established
  that nothing here is in production: no live prompts, no real corpus, no agents, no formal
  eval set. That single answer determined which chapters could claim anything and turned a
  vague worry about tone into a specific, fixable fidelity bug. It also ruled out an option
  that seemed obviously good — publishing "we run no evals yet" as an honest note — because
  the maturity of a company's internal practice is theirs to disclose, not the writer's.

---

## Session 6 — 12-Factor Agents (github.com/humanlayer/12-factor-agents)

**The article branch's first real end-to-end run**, and the first page that reproduces a
source instead of explaining it. Both firsts produced findings.

**Source:** a self-contained offline render of a GitHub repo's markdown — README, a history
essay, twelve factor files and an appendix — concatenated into 15 `<section class="doc">`
blocks with custom CSS, a sidebar, a progress bar and copy buttons. 128 KB, ~8,400 words
including code. Pinned by its own footer to commit `d20c728`. **Every one of its 71 images
was a remote hotlink**; the "offline edition" claim in its masthead covers the text only.

**What worked first time:**

- `trafilatura` handled the custom single-`<main>` layout without help — 52 KB of clean
  text, complete through factor 13, no navigation leakage. The `--file` path had never been
  run against a real saved page (`TASKS.md`) and it works.
- `--no-images` plus a hand-written fetch list. Worth doing deliberately every time an
  article's images are worth having: see the cap below.
- The whole mechanical transform. Converting the render's chrome (`.codeblock` wrappers,
  `<details>`, badge rows) into library markup with BeautifulSoup was reliable; the failures
  were all in *my* traversal, not in the parsing.

**What broke:**

- **`extract_article.py:178` caps downloads at `candidates[:40]`, and the cap is a
  truncation, not a filter.** The first ~40 unique URLs here were 5 shields.io badges, 12
  visual-nav thumbnails and 14 contributor avatars — so the cap would have spent itself
  entirely on junk and silently dropped the factor 9–12 diagrams. Nothing would have
  reported the loss. Logged in `TASKS.md`.
- **Pillow saves frame 0 of an animated GIF, which for a build-up animation is a near-empty
  title frame.** Five of this source's load-bearing figures are GIFs. **Taking the *last*
  frame gives the complete diagram** — verified by eye on all four kept ones, and it worked
  every time. Use `img.seek(img.n_frames - 1)`. Two of the five had explicit static
  counterparts in the repo (`190-…-static.png`, `029-…-high-level.png`); prefer those.
- **I assumed the numbered images (`110`…`1c0`) were decorative title cards and planned to
  drop all twelve. They are not.** Each is a substantive diagram — factor 3's is the
  standard-vs-custom context comparison, factor 8's is the switch-statement control flow.
  They double as nav thumbnails, which is what misled me. *Open the image before deciding
  it is decoration* — the same lesson sessions 1–3 learned about crops, in a new disguise.
- **A `<p>` holding two images loses the second** if you replace the whole paragraph on the
  first one. Replace the `<p>` only when it wraps exactly one image. Cost: one figure,
  caught only by diffing the manifest against the images actually referenced.
- **`clean()` returns a soup whose only child is the `<section>` wrapper.** Iterating the
  soup's children therefore yields one node, not the body nodes — so a "slice between two
  headings" helper silently returned the entire section. Symptom was five duplicated
  figures, not an error. The same wrapper then survived into the output as a nested
  `<section>` with a stripped id; the browser check caught it as blank ids in the section
  list.
- **Not every `![…](…)` in this render is a defect to strip.** Eight sat inside `<details>`
  blocks (genuinely broken markdown), but one was inside an **HTML comment** — the author
  had deliberately commented factor 3's header diagram out. Honour the comment-out; strip
  comments rather than pattern-matching the markdown.
- **`as_paragraphs()` escapes any string that does not start with `<`.** A `colophon_note`
  written as prose-with-a-link printed its own `<a href=…>` markup on the page. Open such
  fields with a tag.

**Non-extraction findings:**

- **`python3` does not exist on Windows**, only `python`. Every command in `CLAUDE.md` and
  `SKILL.md` is written `python3`. Nothing is broken, but the copy-paste fails.
- **`recover_content_json.py --verify` fails on all three pre-existing pages at HEAD**, and
  the script itself says why: the recovered JSON is wrong, not the page. The committed HTML
  has a hard-wrapped colophon paragraph and an unescaped apostrophe that a rebuild
  normalises. Worth knowing before using it as a regression gate — diff against the *HEAD
  baseline diff*, not against zero.
- **Reproducing a CC BY-SA source changes what the page owes.** An explanation written from
  a source is a new work; a faithful copy is a redistribution, so share-alike actually
  binds. That is why this page carries the licence in three places (an opening callout, all
  32 `figsrc` credits, and the sources section) rather than the usual single source link.
- **Two colophon defaults were false for a reproduction**, and both were hardcoded:
  "Explained and published in the AI Library" in the template, and the ordinal section
  number, which ran one ahead of section titles that carry their own numbers ("13" above
  "Factor 12"). Added `colophon_lead` and per-section `num`; both default to the previous
  behaviour, verified byte-identical against a rebuild of `slopcodebench`.
- **`--ink-faint` fails AA in light mode, measured.** `.figsrc` and `.callout__label` come
  out at **4.08:1**, exactly the figure `writing-guide.md:184` warns about. Dark mode is
  fine (4.79:1). This is every page, not this one; the new `.doc h4` uses `--ink-soft`
  (7.73 light, 8.77 dark) on that advice.

---

## Session 7 — Situational Awareness: The Decade Ahead (situational-awareness.ai)

**Source:** 165 pages, ~52,000 words, 21.4 MB. A **Tufte-style LaTeX book**
(`tufte-book`: narrow main text column, wide side margin carrying captions and
footnotes), five essays plus an appendix. 39 figures, **almost all embedded rasters**
— matplotlib plots exported to PNG, two photographs, one DALL-E illustration.
Also the first *forecast* in the library rather than a technique or a result, and the
first source old enough (June 2024) to be scored against what actually happened.

**What worked first time:**

- **The embedded pass did the whole job.** 42 candidates for 39 figures, essentially
  1:1, at full resolution, every one cropped correctly because there was no cropping
  to do. The exact inverse of session 3, where 40 embedded candidates were all junk.
  The discriminator is how the figures were *made*: session 3's were vector diagrams
  decorated with icons, these are pre-rendered rasters dropped into the document.
- **`MIN_SIDE`/`MIN_AREA` produced no false positives**, despite the margin layout
  giving plenty of opportunity for stray rules and glyph runs.
- **The two rendered-region crops were both clean**, and one of them —
  `fig-p39-figure-19` — was *better* than the embedded halves, capturing both panels
  of a two-panel figure as one image where the embedded pass gave two separate files.
  Worth checking for: when a figure has stacked panels, the region render may be the
  right choice even when embedded copies exist.

**What broke:**

1. **Every caption came back empty.** Not one of the 42 candidates had a caption,
   because this class sets captions in the *side margin*, level with the artwork, not
   in the band beneath it. The region pass matched only 2 of 39. Recovering the
   figure-number-to-page mapping meant reading the body text and matching each
   `Figure N:` marker to a page myself. **New failure mode**, and a common layout.
   Logged in `TASKS.md`.
2. **All three metadata heuristics failed at once, and the PDF already held the right
   answers.** `pdf_metadata` in the text JSON carried the correct title, the correct
   single author and a `creationDate` of `D:20240606`. The heuristics returned
   `"S I T U AT I O N A L AWA R E N E S S"` (letter-spaced display type reported with
   literal spaces between glyphs), an empty `authors`, and **year 2027** — scraped from
   the essay's own argument, not from the document. Sessions 2 and 3 recorded author
   detection failing quietly; this adds a *year* that is confidently wrong and
   plausible-looking, on a page where the year is the whole point. **Check the year by
   eye too, not just the author.**
3. **The word count over-reported by roughly a third.** 52,173 counted, but this book's
   margins carry very extensive footnotes — some pages are more footnote than body. Same
   species as session 3's bibliography problem, different cause, and it pushes the
   depth decision the same wrong way.

**Non-extraction findings:**

- **The figure-contradicts-the-prose pattern held for the fourth source in a row, and
  this time it mattered.** Figure 16 (METR agentic tasks) is the essay's single best
  piece of *evidence*, and the prose describes it as "5% → 20% → nearly 40%" via better
  scaffolding. The plot shows AutoGPT at ~15% and the chat harness at ~21% — both
  *below* the plainly-prompted `basic gpt-4-0613` at ~30%. The envelope does rise, but
  the tidy monotone story is not what was measured. Four for four now: **read every
  figure against the sentence that cites it, as a matter of course.**
- **A figure can also contradict itself.** Figure 19's top panel is labelled "GPT-2
  (2019) to GPT-4 (**2024**)" while its lower panel's window is "**2023**–2027" — the
  same model dated two different years inside one image, and the body text uses 2023
  throughout.
- **A dated forecast wants a scorecard section, and it is the most valuable thing on
  the page.** Everything else on this page a reader could get from the original; "here
  is what has and has not happened" they cannot. It also disciplined the writing:
  scoring the predictions forced me to notice that I had explained the buildout chapter
  *without* its revenue arithmetic, while the scorecard was scoring the revenue
  prediction — a coherence hole that only appeared because the two sections had to agree.
- **A forecast needs the author's position disclosed, not just their argument.** This
  document contains explicit investment advice, mentions being "all-in leveraged long
  Nvidia", and its author launched a fund on the thesis afterwards. None of that makes
  the arithmetic wrong and none of it belongs in a hit piece; it belongs in one sentence
  where the reader can weigh it.
- **Where the essay was right and wrong falls into a clean pattern worth stating on the
  page:** mechanisms (test-time compute, verifiable-reward RL, electricity as the
  binding constraint) did well; institutions did worse in both directions; competitors
  did worst, and failed by underestimating them. Sorting the misses by *kind* said more
  than listing them.
- **Five new tags at once.** The vocabulary was entirely LLM-engineering
  (`agents`, `rag`, `prompting`…) and nothing covered a forecasting/strategy essay.
  13 → 18. First sign the library has more than one subject.

**Tooling notes for this environment:**

- **`verify_page.py` cannot run on Windows** — its Chromium path is a hardcoded Linux
  location. Re-implemented the same assertions in the scratchpad to get them run; all
  passed (no overflow, 8/8 images decode, anchors resolve, toggle flips and persists,
  search and the tag chip both narrow to one card, 4/4 tables scroll on phone). Logged.
- **Playwright is installed and works on Windows** at
  `%LOCALAPPDATA%\ms-playwright\chromium-1208`; omitting `executable_path` finds it.
- **Google Fonts is *not* blocked here**, unlike sessions 2–4. Screenshots render in the
  real faces, so local screenshots can verify typography on this machine.
- **`ElementHandle.screenshot()` times out on a tall element** ("waiting for element to
  be stable") — the scorecard table hit the 30s default. Scroll with an absolute
  `window.scrollTo` and take a *viewport* shot instead.
- **A screenshot taken mid-smooth-scroll looks like a sticky-header bug.** One capture
  put the header at y≈590 with dead space above it. It is a capture artifact: inject
  `* { scroll-behavior: auto !important }`, jump, wait, then assert
  `header.getBoundingClientRect().top === 0` before believing a layout defect. Nearly
  chased a non-bug for the second time in the project's history.

---

## Session 8 — reviewing the situational awareness page (no new ingest)

**Source:** the session 7 page itself, 14 sections and ~9,900 words, re-checked against
`situationalawareness.pdf`. Unlike session 4 the ingest's `inbox/` was still intact, so the
content JSON, the figures JSON and the 21 MB PDF were all present — no recovery needed, and
a rebuild-and-diff proved the JSON byte-exact before anything was touched. Two adversaries
briefed independently, then every finding adjudicated against the source or the browser.

**What the review found:**

1. **The page's sharpest criticism of the source was false, and it was false in the caption
   of the figure that disproves it.** The Figure 19 caption said unhobbling is entered as a
   question mark "yet the headline claim adds all three columns together", and `limitations`
   repeated it as "Summing a question mark". The essay does no such thing: the figure brackets
   compute and algorithmic efficiency alone as "base scaleup", p.38 says "4.5–6 OOM base
   effective compute scaleup … **plus** major 'unhobbling' gains", and Figure 1's own caption
   (p.8) reads "this graph shows only the scaleup in base models; 'unhobblings' are not
   pictured." The essay is *scrupulous* about the thing the page accused it of. **A critical
   judgement is a claim, and it decays the same way a number does** — the page's §02 and §03
   prose stated the relationship correctly, so the defect was a compression that survived in
   the two places written last and read first.
2. **Three reversals of the source's position, each contradicted by the page's own prose
   elsewhere.** `limitations` said the essay "argues for maximum speed" when it argues for a
   lead precisely so that part of it can be spent on caution (p.137–138, "cash in parts of the
   lead", "delaying by 6 months in the middle of the intelligence explosion") — and §09 says so
   correctly. The scorecard scored "Superalignment receives a far more concerted effort" as a
   failed prediction when p.125 makes it a *demand* and predicts the default will hold, so the
   essay was marked down for an outcome it forecast. And the China row's word "**remain**"
   turned a June-2024 snapshot into a forecast, when the essay's actual forecast (p.134, "They
   will be a formidable adversary") has aged well. **When a page contradicts itself, the
   summary/verdict end is the wrong one** — the body was right all three times.
3. **The recurring undefined-basics failure, in its purest form yet.** `artificial general
   intelligence` appeared **zero** times on a page that used "AGI" sixteen times, put it in the
   hook, the meta description and a section title, and glossed it only at ~8,600 words inside a
   table cell. Same for "superintelligence" (13 uses, no definition), "inference" (used for a
   headline 3-OOM number, absent from the glossary), and RLHF (expanded in the glossary, never
   in the body). Session 4 recorded this for `token` and `chain-of-thought`; it is now four for
   four. **The glossary is what hides it** — nineteen entries looked thorough while the page's
   single most-used acronym had none.
4. **A figure undercount the page could see.** The Figure 16 caveat said "Two of the named
   agent harnesses score below the plainly-prompted model"; LangChain ReAct is a third, plainly
   visible in the image directly above the sentence. Both adversaries and I read that image;
   only the craft agent counted.
5. **Invented essay ordinals.** The page opened "165 pages, in five parts" (correct: I, II,
   III, IV, V) and then numbered chapters "the third essay" … "the sixth essay", which are
   really IIIa–IIId, sub-chapters of the third part — while its own scorecard column used the
   correct IIIa/IIIb/IIIc/IIId labels and never explained them. Three notations, no key. Found
   independently by me and by the craft agent, which is the strongest signal the review produced.

**What held up.** Everything numeric. Gulf War casualties, Table 4 and Table 5 cell by cell,
the Marcellus gas arithmetic, the test-time compute table, the growth-modes table, all fifteen
bibliography entries, every `figsrc` page number, all eight `alt` texts, and roughly forty
quoted figures. Both of session 7's deliberate critical readings survived independent checking
against the images: Figure 16 really does put AutoGPT and the chat harness below the
plainly-prompted model, and Figure 19 really does date GPT-4 to 2024 in one panel and open at
2023 in the other. **The page was accurate about its source's numbers and wrong about its
source's argument** — the exact inverse of session 4, where the numbers slipped and the
judgements held.

**On running adversaries, again.** Both over-reported, as designed, and the rejections were
instructive. The craft agent's counts — 37 "not X but Y" constructions, 26 authorial
superlatives, 101 em-dashes in 9,897 words — are real measurements and were still rejected:
rewriting a 10,000-word page for cadence risks introducing errors into prose that is otherwise
correct, and the guide's "device used twice is voice" line does not obviously make ten per
thousand a defect. Also rejected: the "In short" block duplicating §1 (a summary block is
allowed to restate, same reasoning as session 4's glossary rejection) and callout density
(in line with `llm-field-guide`). **I nearly filed a false finding of my own** — the page says
"the 40 rigs already running in the Marcellus", which reads like an error until you find the
source's parenthetical "(the current rig count in the Marcellus)" on p.84. Checking the primary
occurrence saved it, for the second review running.

**Tooling notes for this environment:**

- **`verify_page.py` now runs on Windows.** Fixed rather than worked around: `executable_path`
  is passed only when `AI_LIBRARY_CHROMIUM` is set, so Playwright resolves its own bundled
  Chromium. Session 7 re-implemented the harness in a scratchpad to get the checks run and
  logged the fix; doing the fix took about a minute and retires the workaround permanently.
- **An intact `inbox/` makes a review dramatically cheaper.** No `recover_content_json.py`, no
  `git show` of a large blob, no round-trip guesswork — just rebuild and diff. Worth asking the
  ingest session to leave `inbox/` in place when a review is expected to follow.
- **Extracting the PDF text once, with `=== PAGE N ===` markers, is what makes findings
  actionable.** Every accepted fidelity finding cites a page number from those markers; the two
  rejected ones could not.
- **Windows `python` writing source excerpts to stdout dies on `cp1252`.** Wrap stdout in a
  UTF-8 `TextIOWrapper` with `errors='replace'` before printing anything pulled out of a PDF.

---

## Session template

```
## Session N — <title> (<identifier>)

**Source:** pages, layout, figure kinds, size, anything unusual.

**What worked first time:**

**What broke:** the failure, the diagnosis, the fix, and the constant it changed.

**Non-extraction findings:**
```
