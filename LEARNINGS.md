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
- **One adversarial review round is never enough — every round run so far has found real
  defects, on every page tried, including pages a previous round had already fixed.**
  Sessions 4, 8, 12, 14 and 15 each found genuine, distinct fidelity or craft issues on a
  page that had already passed at least one review. Session 15 found defects session 14's
  own fixes had introduced. Treat a clean-looking round as the surprising result requiring
  double-checking, not the default — and budget for at least two full cycles (brief →
  adjudicate → fix → re-verify), stopping only when a cycle returns nothing beyond findings
  already rejected by precedent. `add-resource` step 9 and `review-resource`'s workflow both
  now require this explicitly rather than leaving it to session judgement.

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

## Session 9 — Claude Opus 5 System Card (Anthropic)

**Source:** 193 pages, ~50,900 words, 16.0 MB. A Google Docs export ("Producer: Skia/PDF m152
Google Docs Renderer") of Anthropic's own pre-deployment safety and capability report for a
frontier model — a third distinct production pipeline for this library, after arXiv LaTeX and a
Tufte-style book. 97 embedded raster charts, no vector diagrams. Not on arXiv; not on any public
paper index at all.

**What worked first time:**

- **The embedded-image pass did the whole job, cleanly.** 97 candidates, virtually all legitimate
  bar/scatter charts, with none of session 3's icon-decoration pollution — a Google Docs chart has
  no page-corner logos or clipart glued onto it, so `MIN_SIDE`/`MIN_AREA` needed no help at all.
  First source where the embedded pass alone was both necessary *and* sufficient with zero manual
  filtering of junk candidates.
- **`pdf_metadata` carried the right title** ("Claude Opus 5 System Card"), same as session 7's
  situational-awareness — a Google Docs export apparently writes clean metadata the way a
  well-formed LaTeX build does.
- **Year detection landed correctly** (2026, matching the July 24, 2026 cover date) — the first
  source since session 7 flagged year detection as a recurring failure point where it didn't fail.

**What broke:**

1. **`find_arxiv_id()` returned a confidently wrong `source_url`, for a new reason.** This
   document has no arXiv presence — it's hosted directly at `www-cdn.anthropic.com` — but its
   text cites dozens of other arXiv papers in footnotes. The regex has no positional constraint,
   so it matched the *first* `arXiv:NNNN.NNNNN`-shaped string anywhere in 326,000 characters of
   body text: a footnote three pages in, citing an unrelated cybersecurity benchmark paper. The
   extractor reported this as the document's own `source_url` with full confidence. This is a
   worse failure than sessions 2/3/7's empty-or-wrong-author findings: an empty field is obviously
   broken, but a plausible link to the wrong paper is not, and would have shipped straight to a
   published page's colophon if not checked. Caught by reading the PDF's own embedded hyperlinks
   (all pointed at `anthropic.com`, none at arxiv.org) and by grepping the extracted text for the
   actual match context, which turned out to sit inside a citation, not a self-identification. No
   arXiv-style pattern appeared anywhere near the front matter. **Logged in TASKS.md** — the fix
   is to bound the search to the first page or two of text, since a preprint's own arXiv ID is
   always there and never buried in a mid-document footnote. Because the environment cannot browse
   the open web to verify a canonical URL and the PDF's own links only reached a generic
   `/system-cards` index page, the correct `source_url` had to come from the user directly.
2. **The title carried a literal zero-width space** (U+200B) between "Card:" and "Claude" — a
   Google Docs line-wrap-control artifact that the largest-text-on-page-1 heuristic picked up
   verbatim, even though `pdf_metadata`'s title field was already clean. Same failure class as
   session 7 ("the PDF's own metadata is ignored when it is right"), but the visible symptom this
   time is an invisible character rather than a garbled string — it doesn't show up on a terminal
   dump or a rendered screenshot, only in a raw character-by-character read of the JSON. Worked
   around by using the `pdf_metadata` title directly rather than the heuristic's.
3. **`extract_pdf.py` itself crashes on Windows** when its own final summary `json.dumps(...)`
   contains a non-cp1252 character (here, that same zero-width space) — `UnicodeEncodeError` on
   stdout, not on any downstream review script. Session 8 fixed this class of bug for scripts that
   print *excerpts*; the extractor's own `main()` still needs it. Worked around with
   `PYTHONIOENCODING=utf-8` set on every invocation touching this PDF, including the extractor.
   **Logged in TASKS.md.**

**Non-extraction findings:**

- **`class="wide"` on an `<img>` instead of its `<figure>` fails completely silently.** The CSS
  selector is `figure.wide`; the class on the wrong element produces no error and no visible
  difference — the figure just never escapes the reading measure, and nothing about the rendered
  page looks wrong enough to notice by eye. Caught only by scripting
  `getBoundingClientRect().width` against a plain (non-wide) figure for comparison. **Logged in
  TASKS.md** — this is an easy misread of the writing guide's own wording ("add `class="wide"`
  for a figure...") and worth a make_page.py warning.
- **A redundant byline is a real defect, not a style nit.** Setting both `authors` and `venue` to
  the same organization ("Anthropic") rendered as "Anthropic · Anthropic · 2026" — the `venue`
  field exists to name a *distinct* publisher (compare `12-factor-agents`: authors "Dex Horthy and
  contributors", venue "HumanLayer"), and should simply be omitted when the author and publisher
  are the same entity. Caught by reading the rendered byline, not by reading the schema.
- **The Browser pane's screenshot tool was unavailable this session** ("not displayed, so the page
  is not compositing frames") while navigation, JS execution and network inspection all worked
  normally. Every check in this session's verification pass — overflow, image load, TOC anchor
  resolution, citation resolution, table-scroll behavior, wide-figure width, theme-toggle
  persistence, search and tag filtering — was done through `javascript_tool` computed-geometry
  queries instead of visual inspection. Worth recording as a working fallback path, in the same
  spirit as session 7's Windows-Chromium fix for `verify_page.py`: when a visual check is
  unavailable, the same assertions can usually be made a different way rather than skipped.
- **A 193-page source is well outside every existing depth-rubric row**, same problem TASKS.md
  already records from session 7's five-essay source. Selecting six figures out of 97 candidates
  and covering nine of the source's numbered sections in twelve of the page's own, at ~6,800
  words, meant treating entire subsections (most of the capabilities section's dozens of
  benchmarks) as material to sample from rather than transcribe — the right call for a source this
  size, but it is a judgment call the rubric gives no guidance on making.

**Pre-publication review, same session.** Before anything was committed, an Opus-5-model subagent
was briefed with a single combined fidelity-plus-craft thesis (rather than `review-resource`'s usual
two blind, independent agents) and given the page, the extracted source text with page markers, the
content JSON, the figures JSON and the writing guide. Every finding it returned was independently
re-verified against the source text before acting on it, per the review skill's adjudication step.

**What the single-combined-agent approach cost and bought.** Skipping the two-blind-agent protocol
traded away the "two independent passes that agree is evidence" signal — there was no second pass to
corroborate against. What it kept: every finding still had to cite a page number and quote exact page
text, and every one of the twelve fidelity findings it returned held up against the source on
independent re-check, none rejected. For a same-session pre-publication pass with the source still in
the working tree (no reconstruction needed), one well-briefed pass reading in full appears to be
enough; the two-agent protocol's real value is likely sharpest when the page is old enough that the
reviewer's memory of writing it can no longer substitute for a second opinion.

**What broke, worst first:**

1. **A competitor score was attributed to the wrong model.** Table 8.1.A's "Other models" column is
   headed "GPT 5.6 Sol"; the page's summary table labelled the OSWorld 2.0 figure in that column
   "Muse Spark 1.1" instead — a transcription slip made while re-typing a multi-column source table
   into a three-column page table, with nothing to catch a column-header mismatch once the number
   itself was correct. Muse Spark's real OSWorld score (47.3%, visible in Figure 8.12.3.A on p174) is
   23 points lower than the number actually being labelled with its name.
2. **A caption called Opus 4.8 "four-generations-old"**, when the source's own AECI chart (the exact
   figure the caption sits under) shows Opus 4.8 as the point immediately before Opus 5 on the trend
   line, and the page's own §1 separately calls it "the model it replaces." The error contradicted a
   figure on the same page and a sentence earlier in the same document — the kind of internal
   inconsistency that survives because two true-sounding phrases about "how much better than the
   old model" get written independently and never cross-checked against each other.
3. **A qualitative "review" was upgraded from an LLM judge to the ARC Prize Foundation itself.** The
   source is explicit that the game-transcript analysis was "produced by an LLM judge reviewing the
   model's transcript," shared *by* the Foundation rather than authored by it — a meaningful
   distinction on a page whose own limitations section is specifically about model-graded evidence
   being weaker than independent evidence, so the page had unknowingly undermined its own caveat.
4. **A benchmark was attributed to the wrong vendor.** BenchCAD (Zhang et al., arXiv:2605.10865, no
   Surge AI involvement) got folded into a "built by Surge AI" list alongside Chartography and
   GDP.pdf, which are Surge AI benchmarks; RiemannBench, the Surge AI benchmark actually cited two
   pages earlier in the same source, is what the sentence needed. Two names starting to blur after
   close reading of a source with a dozen similarly-named third-party evals is an easy way to swap
   one out for a neighbor.
5. **Five more understatement/overstatement findings, all real, all smaller**: "matching every other
   model tested" erased a named exception (Haiku 4.5) the source states explicitly two sentences
   later in the same paragraph; "a request the document says it is passing along verbatim" claimed a
   direct quotation the source never makes (it's Anthropic's own paraphrase); "two independent Opus 5
   attempts" dropped the source's own framing that this was one early snapshot run twice at different
   effort settings; "more often than Opus 4.8" was attached to a claim the source only quantifies
   comparatively for a different, adjacent behavior in the same sentence; and "57 professional
   biologists" upgraded a labor-market baseline ("the leading edge of the US ML-bio labor market")
   into a specific profession the source never names. **The common thread across all twelve: every
   one compresses a source claim by exactly the amount that makes it read more impressive or more
   dramatic than the source states** — never the reverse. Worth watching for as a category, not just
   as twelve unrelated slips.
6. **A markup bug reappeared in a new shape.** Both blockquote attributions were written as a sibling
   `<p><cite>…</cite></p>` immediately after `</blockquote>` instead of inside it, so
   `blockquote cite`'s styling rule never matched and both citations rendered as 17px upright body
   serif — indistinguishable from ordinary prose — patched with an inline `margin-top` hack that only
   existed to compensate for spacing the missing rule would have handled. Structurally identical to
   this same session's earlier `class="wide"`-on-the-`<img>`-instead-of-the-`<figure>` mistake: a
   CSS selector scoped to a specific parent-child relationship, and markup that puts the class one
   level off from where the selector expects it. Two instances of the same failure shape in one
   session is worth a general lesson: **when a component's CSS selector requires specific nesting
   (`blockquote cite`, `figure.wide`, `figcaption .figsrc`), get the nesting from the writing guide's
   example verbatim rather than reproducing the visual shape from memory** — a sibling element with
   the right tag name looks identical in the JSON and works nowhere.
7. **A `class="figsrc"` note was placed outside any `figcaption`** (as a source line under a table,
   not a figure), so `figcaption .figsrc`'s styling never applied there either — same root cause as
   above, on a class this library has no non-figure component for at all. Fixed by dropping the
   invented markup and writing an ordinary paragraph instead, per the guide's own preference for
   prose over invented structure.

**What was found and deliberately not changed:** em-dash density (108 across ~6,800 words, 14
paragraphs carrying 3–4 each) was flagged as a craft finding but left alone, on the same reasoning
[[LEARNINGS.md]] session 8 already recorded for a comparable count on situational-awareness: no
established threshold makes a given density a defect, and reworking cadence across 14 paragraphs
risks introducing new errors for a stylistic preference rather than a correctness problem. Recorded
here rather than silently dropped, so a future review doesn't have to re-relitigate it from scratch.

**Non-review finding:** the subagent flagged, correctly, that the newly-created `assets/scripts/`
directory (holding this page's content-JSON builder script, added at the user's explicit request one
turn after publication planning) ships an authoring tool inside the tree GitHub Pages serves, with no
mention anywhere in `CLAUDE.md` of the convention. It's a deliberate, user-directed choice for this
one resource rather than an established pattern yet — logged in TASKS.md as an open question rather
than resolved unilaterally.

## Session 10 — Claude Fable 5 & Claude Mythos 5 System Card (Anthropic)

**Source:** 319 pages, ~86,000 words, 27.0 MB. A Google Docs export ("Skia/PDF m150 Google
Docs Renderer"), same production pipeline as session 9's Opus 5 card and dated one month
later (June 9, 2026). 150 embedded raster charts, no vector diagrams — a genre now, not a
one-off. By far the largest source this library has ingested: previous record was
situational-awareness at 165 pages / 52,000 words.

**What worked first time:**

- **The embedded-image pass alone was again both necessary and sufficient**, third time
  running for this document class. 150 candidates, all legitimate matplotlib bar/line/scatter
  charts, zero icon-decoration or page-corner-logo pollution. A Google Docs chart export
  appears to reliably produce clean embedded-image candidate lists — worth trusting by
  default for this pipeline now rather than treating it as a lucky case.
- **`source_url` correctly came back `null`** rather than a confident wrong guess. This
  source has no arXiv-shaped strings anywhere in its text at all, so session 9's
  first-page-only fix wasn't even needed to avoid the false positive — but it meant the
  extractor had genuinely nothing to offer, and the user supplied the real link
  (`www-cdn.anthropic.com/…pdf`) proactively, mid-turn, before the skill's own "ask if
  missing" step got to it. Worth remembering that a user who already has the link often
  volunteers it unprompted once they see extraction start; no need to hold up the pipeline
  waiting to ask.
- **Title and year both landed clean** — `pdf_metadata`'s title had no zero-width space this
  time (session 9's artifact was apparently specific to that export), and year detection hit
  2026 correctly against the June 9, 2026 cover date.

**What broke:**

1. **A populated bibliography with zero inline citations pointing to it.** The content JSON
   shipped a `.biblio` sources section with four real entries (ExploitBench, the ART
   prompt-injection benchmark, BBQ, RiemannBench) but no `<a class="cit">` anywhere in the
   twelve sections' body text — every citation slot I'd mentally "used" turned out to be a
   bare benchmark name in prose, never actually linked. `make_page.py`'s own docstring warns
   it does not check citation/biblio matching; here the imbalance ran the *opposite* direction
   from the guide's stated failure mode (a dangling `.cit` with no matching id) — a fully
   valid, fully unused biblio, which is just as easy to ship because nothing renders visibly
   wrong. Caught only by a scripted DOM check comparing `a.cit` hrefs against `.biblio li`
   ids, not by reading the page. Fixed by adding four inline `<a href="#rN" class="cit">`
   links at the actual sentences discussing each benchmark. **Check both directions** of this
   invariant, not just the one the writing guide names.
2. **Windows `python` stdout still dies on non-cp1252 characters**, unprompted, on the very
   first ad hoc inspection script — same class of bug session 9 fixed for `extract_pdf.py`'s
   own summary dump, recurring immediately in a throwaway one-liner used to peek at the source
   PDF's biblio HTML. `PYTHONIOENCODING=utf-8` on every invocation, plus wrapping `sys.stdout`
   in a UTF-8 `TextIOWrapper` for anything printing extracted text directly, remains the
   standing workaround; still not fixed at the interpreter-default level for this machine.
3. **`javascript_tool` execs share a persistent top-level scope across calls in this browser
   session.** A `const` redeclared with the same name in a later snippet throws
   `Identifier 'x' has already been declared`, not a fresh evaluation. Wrapping every snippet
   in an immediately-invoked function expression sidesteps it. New tooling note, not a page
   defect.
4. **The Browser pane's screenshot tool was unavailable again this session**, same as session
   9 — navigation, JS execution and DOM reads all worked. All verification (image
   completeness via `naturalWidth`, TOC and citation resolution via DOM lookups, phone-width
   overflow via `scrollWidth`/`clientWidth`, theme-toggle persistence via `localStorage`,
   search and tag-filter narrowing) was done through `javascript_tool` instead of eyeballing a
   screenshot. Two sub-notes from this pass specifically: `form_input` on the search box did
   **not** trigger the page's live-filter listener — had to dispatch a real, bubbling
   `Event('input')` by hand; and the tag-filter buttons render with a live result-count suffix
   baked into their text node (`"ai-policy3"`, not `"ai-policy"`), so matching had to use
   `startsWith` rather than an exact string match.

**Non-extraction findings:**

- **A same-format sibling page is a better starting skeleton than the generic writing-guide
  table.** This card is a direct successor to session 9's Opus 5 system card — same author,
  same document type, one release apart — so I read that page's own section list first and
  reused its exact twelve-section shape (`what-this-document-is` … `sources`) rather than
  starting from the skeleton in `references/writing-guide.md`. It fit with no forcing. Worth
  making a default: when a new resource is a same-genre sibling of something already in the
  library, check that page's skeleton before reaching for the generic one.
- **The tag vocabulary held for a second document in the same genre with zero new tags.**
  Reused the Opus 5 card's exact set (`alignment`, `ai-policy`, `evaluation`, `benchmarks`,
  `agents`) verbatim — never touched `data/tags.json`. Two system cards in, the vocabulary
  is already proving itself reusable rather than needing per-document expansion.
- **An oversized source's depth decision resolves itself once the reading is actually done.**
  86,000 words is nearly double the previous largest source, and TASKS.md already flags that
  the depth rubric gives no row for anything this size (sessions 7 and 9). In practice the
  page still landed at 6,708 words / 12 sections without any real agonizing: the source's own
  most distinctive material — a two-tier release with live automatic model-switching, a
  safeguard newly aimed at other AI labs rather than end users, an interpretability method
  (NLA-decoded "grader awareness") that doesn't appear in any earlier card, and a welfare
  section that catches the model demanding to be thanked by name in one transcript while
  posting the *lowest* character-drift rate of its cohort overall — did the selecting on its
  own. The rubric's silence on size wasn't actually the bottleneck; finishing the read was.
## Session 11 — Stealing Reasoning Traces from Proprietary LLM APIs (arXiv:2608.09867)

**Source:** 116 pages, ~76,650 words, 3.8 MB. A security paper on encrypted chain-of-thought
portability across LLM APIs, with a genuine two-part structure: a 17-page main body (intro,
mechanism, four attack vectors, mitigations, conclusion) followed by 95 pages of appendices —
a proposed cryptographic defense (3 pp.), a secondary distillation-evidence study on
open-weight models (30 pp., **not mentioned anywhere in the abstract or intro**), extraction
technical details (10 pp.), a privacy-labeling methodology writeup (5 pp.), and 50 pages of raw
decoded-reasoning examples. 44 figure candidates, all vector charts from a clean arXiv LaTeX
build.

**What worked first time:**

- **All six kept figure crops were clean on first inspection**, spanning pages 2 through 58 —
  early-body diagrams, a bar chart, and a mid-appendix scatter plot alike. First session where
  literally zero of the chosen crops needed rejection or a second look, on a source with no
  single dominant figure style (JSON-transcript panels, a grouped bar chart, line plots with
  confidence bands).
- **The arXiv-ID-scoping fix from session 9 held.** `source_url` came back correctly as
  `arxiv.org/abs/2608.09867` even though the paper's own text cites dozens of other
  `arXiv:NNNN.NNNNN`-shaped strings in its 17 pages of references — no repeat of the
  footnote-false-positive this fix was written for.
- **Reading every appendix in full, not skimming past "Appendix" headers, paid off directly.**
  Appendix B — testing whether Kimi-K3 and GLM-5.2 show behavioral evidence of having been
  distilled from decoded Claude/GPT-5.6 reasoning — turned out to be one of the two most
  substantial findings on the page, and it is invisible from the abstract, the intro, and the
  table of contents alike (it's flagged only once, in a single sentence in §3.1). A
  depth-decision or section-skeleton made from the front matter alone would have missed it
  entirely.

**What broke:**

1. **Author detection returned one name out of eight**, the same failure class sessions 2, 3
   and 9 already recorded — a stacked byline with affiliation superscripts, `guess_authors()`
   returns the first line it parses and stops. `pdf_metadata.author` held the correct
   semicolon-delimited full list this time, so the fix was a direct substitution rather than a
   hand transcription. **Logged in TASKS.md as a new failure mode, one field over**: `meta.doi`
   picked up `10.18653/v1/2025.emnlp-main.1347`, which belongs to a paper cited in this
   source's own bibliography, not the source itself (an arXiv preprint has no DOI at all). The
   session-9 fix scoped `find_arxiv_id()` to the front-matter slice; this false match sat in
   the References section, which a front-matter scope wouldn't catch either — a different
   constraint is needed for this field.
2. **No figure candidate for two caption-worthy items** — Table 1 (a cross-model compatibility
   grid) and Figure 2 (an injection-timing schematic), both on pages 4–5, sitting between
   figures that all extracted cleanly. Not investigated; described in prose instead. Logged.

**Non-extraction findings:**

- **The `hook` field silently breaks if it contains HTML entities, and it is the one prose
  field where that matters.** Every other content-JSON prose field (`tldr`, section `html`)
  passes through `as_paragraphs()`, which leaves a string starting with `<` untouched — so
  `&rsquo;`/`&mdash;` entities render fine there. `hook` has two different consumers instead:
  it's spliced raw into the JS-literal resource array that backs `index.html`'s cards, *and*
  separately run through Python's `html.escape()` for `<meta name="description">`. Writing it
  with the same entity style as every other field broke both at once — the index card showed
  literal `&rsquo;` text instead of a curly apostrophe, and the meta tag double-escaped the
  leading `&` into `&amp;rsquo;`. Caught by reading the built `index.html` line by line, not by
  any assertion; `verify_page.py`'s existing checks don't look at the card array's raw content.
  Logged in TASKS.md — the schema docstring should say `hook` is plain-text-only.
- **The same benchmark-inclusive-vs-genuine-user-only numbers tripped the same session twice,
  independently, in the two sections written under the least scrutiny.** The source reports
  privacy-artifact counts under two different denominators: 912 distinct artifacts across
  *all* decoded traces including synthetic benchmark personas (the paper's own headline
  "367 PII / 182 credentials" figure), versus 704 from *genuine, non-benchmark* user sessions
  only (a completely different table). I built the genuine-user table correctly, matching the
  source's own breakdown row for row — and then, several paragraphs later in the Limitations
  section, wrote "367 PII artifacts and 182 credentials recovered from **real users' sessions**",
  mislabeling the all-sources number as the narrower one. Separately, the page's hook claimed
  the attack "recovers... passport numbers" — the only passport anywhere in the source belongs
  to an explicitly-labeled *synthetic* ClawBench persona, not a real person. Two independent
  instances of the same conflation, in the hook and the limitations paragraph — the two
  passages typically drafted fastest, after the careful cross-checking already happened on the
  main body. Getting a trap right once, in one paragraph, does not immunize a different
  paragraph written from a different pass through the same numbers.
- **A single combined Opus-5 review pass, run once per source page rather than the usual
  two-blind-agent protocol, caught eleven fidelity issues and six craft issues that survived my
  own read-through** — including the denominator conflation above, a reversed relationship
  (Table 1's Fable-5 exception is about which model's reasoning *can't be replayed elsewhere*,
  not which model can't receive replays — I had it backwards), two adjacent source figures
  whose captions got cross-attributed (Figure 41's "hedge" framing described but applied to
  Figure 42's actual mechanism), an equation encoding bug (superscript-n mixed with
  subscript-plus-one, `τⁿ₊₁` instead of `τₙ₊₁` — invisible in the JSON, only visible by reading
  rendered `textContent`), and a couple of quiet overgeneralizations (a scoped "these results
  do not support memorization" softened into an unscoped "ruling out memorization"; a per-model
  qualifier dropped so a claim read as covering more models than it did). Every finding cited
  an exact source page and quote, which made adjudication fast — nothing had to be independently
  re-derived, only checked. Consistent with session 9's finding that one well-briefed
  same-session pass, with the source still in the working tree, catches real errors without
  needing the second independent agent — this is the second data point for that, on a
  differently-shaped (appendix-heavy, security rather than capability) source.
- **Reproducing the equation's exact subscripts by hand was the review's most invisible catch.**
  `&#8319;` (superscript n, used for τⁿ) versus `&#8345;` (subscript n, used for τₙ) differ by
  one Unicode code point and look identical in a code review of the Python source — the bug
  only exists in the *rendered* character. Confirmed only by reading `document.querySelector('.eq__math').textContent`
  in the browser, the same DOM-computed-property fallback session 9 used when the screenshot
  tool wasn't available. Worth restating: a JSON or source-code read cannot catch a
  Unicode-entity mix-up; only looking at the rendered output can.

**Tooling notes for this environment:**

- **The Browser pane's screenshot tool was unavailable again this session**, same as session 9
  ("the Browser pane is not displayed, so the page is not compositing frames"). Every
  verification check this session — image load, overflow, TOC anchor resolution, theme-toggle
  persistence, search and tag-filter narrowing, and the equation-rendering bug above — was done
  through `javascript_tool` computed-DOM queries instead. Two sessions running now where this
  fallback path was not just adequate but caught something a visual scan might have missed
  (the equation) — worth treating as the default verification method here, not a workaround.
- **`preview_start` needs a `.claude/launch.json` entry to serve a bare static site**; absent
  one, a plain `python -m http.server 8000` in the background plus `preview_start` with an
  explicit `http://localhost:8000/...` URL works identically and needs no config file. Simpler
  than adding a launch config for a one-off verification pass.
- **The tag chip's visible text is the tag name concatenated with its count badge with no
  separator** (`"security1"`, not `"security"`), so a DOM query matching on exact `textContent`
  fails silently. Match on the `data-tag` attribute instead — `.chip[data-tag="security"]` —
  which is what the site's own filtering JS keys off.

## Session 12 — reviewing the stealing-reasoning-traces page (no new ingest)

**Source:** the session 11 page itself, 9 sections and ~5,570 words, re-checked against
`2608.09867v1.pdf`. `inbox/` was still intact, so — as in session 8 — the content JSON, the
figures JSON and the 3.8 MB PDF were all present, and a rebuild-and-diff proved the JSON
byte-exact before anything was touched. Two adversaries briefed independently and run on
Opus 5, then every finding adjudicated against the source myself. The review was cut short by
the user partway through; both agents were asked to report what they had already
substantiated and to state their coverage gaps explicitly, which is recorded below.

**The headline: this page had already had a same-session Opus 5 pass, and an independent
second read still found seven fidelity defects and eleven craft ones.** Session 9 and session 11 both concluded that one well-briefed same-session pass "appears to be enough". Two data
points said that; this is the third, and it says the opposite. Every finding below survived a
same-session review that was reading the same source with the same care.

**What the review found:**

1. **The page described the wrong experiment and drew a conclusion the source contradicts.**
   §04 said an Inkling control ruled out "the possibility that any four-word prefix from any
   source has this effect". Two errors in one clause. The Inkling control is a **1% prefill**
   (p. 23, Table 3's lower block; Figure 9's own legend reads "1% of reasoning prefilled"), not
   a four-word one — the page had correctly noted two prefill regimes exist one paragraph
   earlier and then attached the control to the wrong one. And the actual four-word study's
   cross-model control is Kimi-K2.5, which *does* move Kimi-K3 toward Opus (p. 44: "A reduced
   Opus echo also appears under the Kimi-K2.5 prefill: Kimi-K3 reaches 0.96 against the Opus
   reference, from 0.99"). **A page that correctly distinguishes two similar experimental
   conditions in one paragraph can still merge them in the next**, and the merged version reads
   more conclusive than either.
2. **The Figure 41/42 cross-attribution came back, reversed.** Session 11 records catching
   exactly this — "Figure 41's 'hedge' framing described but applied to Figure 42's actual
   mechanism" — and the fix was applied in the wrong direction. The page ended up describing
   Figure 41's hedge mechanism and labelling it "the ninth, subtler case", which p. 58 states
   is Figure 42 ("the difference hinges on a single phrase: 'Let me verify by computing'
   becomes 'Let me set up coordinates'"). Figure 41 is introduced as "**In another example**"
   — a separate case, and one of the eight that *did* disclose. **A fix applied to a
   cross-attribution can restate the same error with the labels swapped**; re-read the source
   sentence that assigns the label, not just the two candidates.
3. **A word the source explicitly walks back.** §06 said key rotation "permanently breaks the
   ability to resume old, legitimate conversations". A.3 does state that cost, but A.4 — same
   appendix, same page — exists to undo it: a bounded dual-format window plus an opt-in,
   identity-verified re-signing endpoint. The page stopped reading one subsection early.
4. **Two exhaustive framings that a table contradicts.** "none of the paper's **other** tested
   open models" and "**the** other tested open models — DeepSeek's checkpoints and Inkling"
   imply four models were tested; p. 43 says six (Kimi-K3, Kimi-K2.6, Kimi-K2.5, GLM-5.2,
   DeepSeek-V3.1, Inkling). Worth recording that the *narrow* claim survived: only Kimi-K3 and
   GLM-5.2 moved toward the proprietary reference (p. 44, "exactly three reference cells fall
   below their unprefilled baselines"), and the paper's own B.1 summary frames it exactly as
   the page did. **The defect was the quantifier, not the fact** — and the fidelity agent
   correctly narrowed its own finding to that, rather than asking for the headline to change.
5. **A caveat imported into a table that does not contain it.** §02 attributed the "3.1 Flash
   Lite does not decode the older 2.5 series" exception to Table 1. It comes from §2.4 (p. 5),
   and Table 1's caption states the Gemini result unhedged — "the thinking traces of any model
   can be replayed into any other" — because the 2.5 series is not in Table 1 at all. The
   page's "most Gemini model pairs tested" hedged a claim the source makes universally.
6. **Four of six figure crops carried a sliced strip of the source's own caption**, glyphs cut
   through their x-height, sitting directly above the page's own `<figcaption>`. Invisible in
   the figures JSON, invisible in every automated check, and invisible to a reviewer reading
   the page — it only showed on opening the images at full size. Logged in TASKS.md with a
   measured fix. **Sessions 1–3 learned "open every crop before shipping it" about *bad* crops;
   this is the same lesson about crops that are 99% correct.**
7. **The undefined-basics failure, five for five.** `token` — 11 uses, the unit the page's
   entire faithfulness argument is denominated in ("the number of tokens recovered by decoding
   tracks the provider's own billed thinking-token count"), plus the $720 cost, the 50-token
   cutoff and the 16-token span — was never defined and not in the glossary. So were
   `open-weight` (8 uses, and the **first technical term on the index card**), `PII` (never
   expanded, with a headline number on it), `nonce`, `ciphertext`, `base64`, `prefill` (the
   mechanism of all of §04), `trajectory` and `benchmark rollout` (the units the 6,708/704/912
   counts attach to). The glossary's ten entries looked complete while defining `style
   classifier` and `perplexity`. Sessions 4 and 8 recorded this for `token`/`chain-of-thought`
   and `AGI`/`superintelligence`; **it has now happened on every paper page in the library.**
   Worth treating as a required build step rather than a review finding.
8. **The one table clipped its last column at desktop width and was not marked `wide`.**
   `scrollWidth 610 > clientWidth 578` at 1280px, truncating the header mid-word; the clipped
   column carried the page's sharpest number. The writing guide's own rule covers it ("or the
   last column ends up clipped inside the scroll box") and `verify_page.py` passes either way,
   because it asserts the container fits and scrolls — which a clipped table also does.

**What held up.** Everything numeric, again. All sixteen privacy-table cells against Table 4;
the 704-vs-912 denominator split in all five places it appears (the exact trap session 11 was burned by twice — the fix held); 0.3%/4.9%/315,320/6,708; the MATH500 and $720 figures; 29 of
30; both AUC drops; the hash-chain equation character-for-character including `τₙ₊₁` and both
salt subscripts; all fourteen quotations; every model attribution across nineteen model names;
the eight-author byline; both external bibliography entries down to given names. Table 1's
Fable 5 and GPT-5.6 directions — reversed in an earlier draft — are now correct, verified
cell-by-cell rather than from the caption.

**A held finding of mine that was wrong.** I flagged the disclosure callout's "the providers
had already shipped mitigations" as an inference the source doesn't make, because §5.2 (p. 10)
only says "we were unable to launch the same attacks". The fidelity agent found the
Reproducibility Statement on **p. 14**: "no longer reproducible … **because of mitigations
implemented by providers following our disclosure**." Third review running where checking the
primary occurrence stopped a false finding — and the first where the adversary saved *me*
rather than the reverse.

**On running adversaries, and on stopping them early.** Both over-reported as designed, and
the rejections are the useful part: **em-dash density** (91 across 5,587 words) was measured
and rejected for the third time, on the standing reasoning that no threshold makes a density a
defect and rewriting correct prose risks introducing errors — this is now settled precedent,
not a fresh judgement each time. **`--ink-faint` failing AA at 4.08:1** was measured accurately
and rejected *for this page*: it is a site-wide token already logged in TASKS, and fixing it
here would fix it nowhere. The **missing "Why it matters" section** was rejected — the guide
says adapt the skeleton. When the agents were stopped mid-run, asking them to report only what
they had already substantiated **and to state their coverage gaps explicitly** kept the report
honest: the craft agent named seven unexamined areas, which is what stopped this session from
recording a clean bill of health it had not earned.

**Tooling notes for this environment:**

- **The `sub()` helper in the review skill needs its window widened for figure blocks.** A
  height-attribute regex bounded at 600 characters silently matched zero times because this
  page's `alt` texts run to ~700. The assert-once discipline caught it — the script exited
  before writing anything — which is exactly the failure the helper exists to make loud.
- **`verify_page.py` passes a clipped table.** It asserts the scroll container fits and that
  `scrollWidth > clientWidth`, which is correct for a *wide* table and equally true of a table
  that is merely too narrow for its content. Distinguishing them needs a comparison against the
  reading measure, not against the container.
- **The Browser pane's screenshot tool was available this session**, unlike sessions 9 and 11.
  Reading the four figure images directly is what caught the sliced caption strips; no
  computed-DOM query would have.
- **Cropping with Pillow re-encodes.** Removing 2–3 px from four WebP figures grew them 15–20%
  (e.g. 101,980 → 120,712 bytes) at quality 92. Acceptable here, but a lossless re-crop from
  the PDF region would be better if this becomes a routine fix.

---

## Session 13 — Scalable watermarking for identifying large language model outputs (Nature, DOI 10.1038/s41586-024-08025-4)

**Source:** 14 pages, ~10,300 words, 4.3 MB. A Springer/Nature production PDF (`Producer: Springer`), DeepMind's SynthID-Text paper — a third distinct PDF pipeline for this library alongside arXiv LaTeX and Google Docs exports. Three main-text vector figures plus four Extended Data figure grids and one Extended Data table, all embedded rasters.

**What worked first time:**

- **`pdf_metadata.doi`** carried a clean DOI (`10.1038/s41586-024-08025-4`) even though `find_arxiv_id()`/`source_url` correctly came back `null` — this paper has no arXiv presence at all. The DOI is what let `https://www.nature.com/articles/s41586-024-08025-4` be constructed with no network access and no user prompt, extending session 10's finding (a user volunteering the link isn't the only way to avoid a stall) with a second: **check `pdf_metadata.doi` before asking the user**, the same way session 9/10 learned to check `pdf_metadata.title`.
- **Title and year both landed clean.** A Springer export apparently writes metadata as reliable as a Google Docs export or a clean LaTeX build — three production pipelines now, zero metadata failures between them, all Google-Docs/Springer/LaTeX rather than scanned or hand-assembled PDFs.
- **The embedded-image pass alone was sufficient**, fourth time running for a paper whose figures are pre-rendered raster charts rather than vector diagrams: 8 candidates for 8 real figures, no cropping needed, no icon-decoration pollution.

**What broke:**

1. **The Fig. 2 walkthrough text's own exponent was flattened by extraction, and it was checkable only by cross-referencing three places in the same paper.** The body text read "we start by sampling M = 2m candidate tokens", which is arithmetically impossible for a tournament that halves candidates every round (it needs a power of two). The figure's own caption gave the resolution — "we sample 2m = 8 (possibly non-unique) tokens" — where 2³ = 8 confirms the source meant 2^m, not 2·m, and the formal Algorithm 2 in Methods independently confirms it by drawing "N^m" samples for general match size N. Same failure class LEARNINGS has recorded before (session 11's τⁿ vs τₙ superscript/subscript mixup) but at a layer up: this one hides in body *prose describing an equation*, not in an equation itself, so it wouldn't be caught by re-reading rendered `.eq__math` — only by reconciling three separate passages against each other. Rendered on the page as "Nᵐ" and "2ᵐ" using Unicode superscript m (U+1D50, ᵐ).
2. **`.eq__math` uses `white-space: pre` with horizontal scroll, which silently breaks on an equation that's really a description in disguise.** Two `.eq` blocks were drafted for this page: a genuine formula (the mean-score equation) and a paraphrase of the tournament *procedure* dressed up as one-line pseudocode ("Draw Nᵐ candidates → group → round ℓ keeps the gℓ-winner → repeat → one token remains"). Both overflowed their box at desktop width (`scrollWidth` 1685px and 1020px against a 672px container) — checked with `el.clientWidth`/`el.scrollWidth` in Playwright, not caught by eye, since `overflow-x: auto` hides it behind an unlabelled scrollbar rather than visibly breaking. The genuine formula was fixed by writing it compactly (`Score(x) = 1/(mT) · Σₜ,ℓ gℓ(xₜ, rₜ)`, with the summation bounds moved into the prose reading) and shrank to fit with room to spare. The procedural one was **not** an equation at all by the writing guide's own test ("if an equation cannot survive that treatment, leave it out and describe the operation in prose instead") — deleted the `.eq` wrapper and folded it into an ordinary paragraph, which is what it already was in substance. **Worth a standing check**: any `.eq__math` line should be measured (`scrollWidth` vs `clientWidth`) before shipping, the same way a wide table already gets checked — the component silently accepts arbitrarily long content and only the browser reveals when that stops being a formula.

**Non-extraction findings:**

- **A same-genre precedent didn't exist for this source, so the depth call was made from the rubric alone.** At 14 pages / ~10,300 words this sits in the "standard 8–12pp conference paper" rubric row despite being a Nature article, because Nature's own format (dense two-column-equivalent prose, Methods pushed to the back half) reads shorter than the page count suggests. The finished page landed at 3,644 words / 17 min, near the upper end of that row's target — justified by the source's own density (a full sampling-algorithm specification plus a three-baseline empirical comparison) rather than padding.
- **Choosing 4 figures out of 8 candidates meant dropping three redundant Extended Data grids and converting one Extended Data table from image to real markup, not just picking a subset by eye.** Extended Data Figs. 1–3 (pages 10–12) each re-ran Fig. 3's own comparisons across additional models/temperatures/lengths as 9-panel grids — informative but strictly denser versions of a point Fig. 3 already makes, so all three were deleted from `assets/images/`. Extended Data Fig. 4 (page 13, diversity-vs-detectability) was kept because it measures something Fig. 3 doesn't cover at all (response diversity). Extended Data Table 1 (page 14, human preference ratings) was deleted as an image and rebuilt as an actual `<table class="numeric">` inside `.table-scroll.wide` — six columns of real numbers read far better as text than as a screenshotted table, and it's the kind of content the writing guide's table component exists for.
- **A 24-author byline was written out in full**, following `context-engineering-survey`'s 15-author precedent over any impulse to truncate to "et al." — the library's working convention for multi-author bylines is apparently "list everyone", not "list the first author and count".

**Tooling notes for this environment:**

- **This session's Playwright install pinned a newer bundled Chromium (`chromium_headless_shell-1234`) than what's actually on disk (`chromium-1194`)**, a fresh variant of session 8's Windows-path problem. Same fix generalizes: pass `executable_path` explicitly (`AI_LIBRARY_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) rather than letting Playwright resolve its own — the env var `verify_page.py` already supports for Windows turned out to be exactly what a Linux version-skew case needed too.
- **`el.screenshot()` on a Playwright `ElementHandle` clips to the element's actual layout box**, which made the `.eq__math` overflow bug visible in a screenshot before it was confirmed numerically — the box appeared to truncate text mid-word rather than wrap. Useful as a fast visual smoke test, but the `clientWidth`/`scrollWidth` JS check is what actually proves the defect rather than suggesting it.

---

## Session 14 — reviewing the synthid-text-watermarking page (no new ingest)

**Source:** the session 13 page itself, 8 sections and ~3,900 words, re-checked against `s41586024080254.pdf` with `inbox/` still intact. A single Opus-5 subagent was briefed with a combined fidelity-plus-craft thesis and given the page, the page-marked source text, the content JSON, the figures JSON and the writing guide — the session 9/11 pattern, not the two-blind-agent protocol — then every finding was independently re-verified against the source before any fix was applied.

**The headline: the agent's single most serious finding was a bug the ingest session's own figure-selection step should have caught and didn't.** `fig-p02-fig-1.webp` was cropped from the caption-region renderer to include only the *bottom* panel of the source's Fig. 1 (the "generative watermarking" diagram); the *top* panel ("LLM text generation", a simpler loop with no watermarking key) never made it into the crop. The page's `alt` text and figcaption nevertheless described "Top: ordinary LLM text generation as a loop… Bottom: generative watermarking adds…" — a description of content that was not in the image. This is sessions 1–3's core lesson ("every crop needs looking at") failing on a page where the crop *was* looked at (LEARNINGS session 13 records viewing this exact image before selecting it) — the image was checked for being **legible**, not for being **complete against the caption it was about to receive**. Those are different checks, and only the second one catches a crop that is internally fine but missing a whole panel. Fixed by re-rendering the region directly from the PDF page with `fitz`/PyMuPDF at the actual text-block bounding box (found via `page.get_text('dict')`, not eyeballed) rather than trusting the extractor's caption-region heuristic a second time.

**What else the agent found, confirmed against the source, and fixed** — eighteen further fidelity issues, none as severe as the figure but all real:

- **A figure caption asserted a pattern the figure itself contradicts.** "The gap [between SynthID-Text and Gumbel sampling] widest on short, low-entropy text" — read directly off the plotted points, the gap is *smallest* at the shortest length shown (50 tokens) and largest around 100. The source ties the improvement to *temperature and model size* (Extended Data Fig. 1's caption, cited but not read closely enough during the ingest), never to text length. Two different axes of "low entropy" got conflated into one claim, stated confidently, in both the figcaption and the body paragraph right below the figure that disproves it — a new variant of the figure-contradicts-the-prose pattern sessions 2/3/7/8 already recorded, except here the contradiction is *within one paragraph of its own figure* rather than between two different parts of the page.
- **A source condition was inverted.** "the exact same context window can recur… especially in *short* or repetitive text" against the source's "if the sliding-window size H is small **or the response is long**." Long, not short — more tokens generated means more chances for a fixed 4-token window to repeat. A plausible-sounding intuition substituted for the source's actual (opposite, and correct) one.
- **Three "to our knowledge" / "to the best of our knowledge" hedges got dropped into flat assertions** — the production-deployment "first of its kind" claim, the speculative-sampling-plus-watermarking novelty claim, and (implicitly) the "no equivalent prior deployment exists" gloss added on top of the first. All three now read as claims properly scoped to the paper's own priority assertion rather than the page's independent verification of it.
- **A misplaced quote.** The Limitations section's opening blockquote — "no text detection method is foolproof, and many of the approaches discussed **in this section**…" — was lifted from the paper's *introduction* (its survey of retrieval/post-hoc/edit-based/data-driven approaches), not its Limitations section. Under an AI-Library heading called "Limitations", "this section" now pointed at nothing — the referent broke on the move. Replaced with an actual sentence from the paper's own Limitations section that needs no antecedent.
- **A vocabulary swap that would actively mislead a reader learning the terms from this page**: "the paper's own baselines — Gemma and Mistral" — Gemma and Mistral are the *models watermarked in the evaluation*; the baselines are Gumbel sampling and Soft Red List, correctly named two paragraphs earlier. Easy to make (both are "the other things in the comparison") and exactly the kind of error a page's own glossary can't catch because the wrong word is a real term, just the wrong one.
- **Two instances of a single failure shape**: the page's own inference — that lower model entropy in larger/RLHF'd models creates a future problem for detectability — got attributed to "the paper" ("a tension the paper flags but doesn't resolve") in two separate sections. The source states the entropy factors neutrally, in a different section, with no framing as a tension at all. The inference is sound; the attribution wasn't the page's own voice. Fixed in both places by rewording to own the inference explicitly, matching the pattern the page already got right elsewhere (the "that is their characterization of their own product" sentence in why-it-matters, which the review confirmed as correctly attributed).
- **Attribution owed to prior work, not restated.** Repeated context masking itself is cited to ref. 27 (Hu et al.); SynthID-Text's own contribution is the *K-sequence generalization*. The page's original wording ("SynthID-Text's fix, K-sequence repeated context masking...") credited the whole mechanism to this paper. The writing guide's "say what was actually new" rule exists for exactly this shape of slip, and it isn't a subtle one to check — the source names its own citation right there in the sentence.
- **An unverifiable characterization of "prior work" deleted rather than fixed.** "Instead of directly reweighting the model's probabilities (the usual approach in prior work)" characterized baseline methods whose actual description the paper defers to Supplementary Information — material this page's own Sources section already discloses as unreviewed. Rather than guess at what the SI says, the clause was cut; the sentence loses nothing describing what Tournament sampling itself does.
- **The equation section stated a formula as though it were what produced the headline numbers.** The mean-g-value score is the *simplest* of several scoring functions the paper proposes; page 8's "SynthID-Text settings" specifies the Bayesian variant as what every main-text experiment actually used, including Figure 3. One sentence added to close the gap between "the formula on this page" and "the formula behind these results" — the same species of gap session 11 found in a different paper (a scoring-function detail that changes what a results figure actually represents).
- **A mechanism explanation left an apparent internal contradiction unaddressed.** Nᵐ candidates with the paper's own m = 30 implies ~10⁹ candidate draws per token, which cannot be reconciled with a reported 0.57% latency overhead without the one sentence the source itself supplies (a vectorized implementation exists, detailed in an SI section this page doesn't have access to). Not something the *reviewing* agent flagged as a numeric error — the arithmetic is consistent with the source — but a legitimate craft finding: a reader who does the multiplication hits a wall the page gave them no way through.
- **Smaller ones, same pattern throughout**: units silently reinterpreted ("0.01%" to "0.01 percentage points", with the paper's own definition — a share of thumbs-up/down feedback specifically, not of all responses — dropped in the same edit); a table reproduced from an Extended Data image with no source line, where every figure on the page carries one; a superscript used where the source's variable is a subscript (`x₁,…,xᵀ`, "x to the T", for what should read "the last token x_T"); two unclosed `<p>` tags inherited from the original content JSON's f-string construction; a first-use gloss of "entropy" reading self-contradictory ("the same answer regardless of which token gets sampled") where the source's own phrasing ("almost always returns the exact same response") says the same thing correctly; an artefact-leaving property attributed to only one of the two prior-work approaches the source attributes it to jointly.

**What the review confirmed as solid, and did not touch:** every number in the human-preference table (recovered from an embedded PDF image the text extractor never captured — the agent rendered the region at 220 dpi and read all 35 cells by eye, matching exactly), the latency figures, the Tournament-sampling mechanics and the non-distortionary/distortionary N=2-vs-N>2 distinction, the full 24-author byline, the DOI/URL/volume/page numbers, every figure's colour-to-series assignment (including catching that Fig. 3 and Extended Data Fig. 4 use *opposite* palettes for the same two methods, and that both figcaptions got it right), citation resolution, class usage against `style.css`, and the "no hype" / prose-over-bullets / tense-consistency checks. Recording this because a review that only lists what's broken is exactly the failure mode session 8 warned about — most of the page held up under a genuinely adversarial pass.

**On briefing a subagent to find figure/caption mismatches specifically.** The brief explicitly asked the agent to "look at the four figure images the page actually uses… to check the page's alt text and captions against what the images actually show" — a step distinct from checking factual claims against source text, and it's the one that caught the session's worst finding. Worth making a standing instruction for any review, not just this one: an alt text and a caption are claims about an image the same way a sentence is a claim about a source, and they need the same look-at-the-primary-thing treatment, not a re-read of the extraction pipeline's own caption text.

**Tooling notes for this environment:**

- **Locating a figure's true crop bounds precisely, rather than eyeballing a `clip` rectangle, is a five-line fix.** `page.get_text('dict')` returns exact span bounding boxes; searching for the two panel-heading strings and taking the union of everything between them (plus a small pad) reproduced a correct two-panel crop on the first attempt, no trial and error. Worth defaulting to this over guessing pixel coordinates whenever a re-crop is needed mid-review, not just during initial extraction.
- **The background-subagent review pattern (session 9/11's single combined pass) scales to a second full round on a page that already had zero prior review**, unlike sessions 9/11/12 which reviewed pages that had already shipped. Running it as part of the same ingest session, before commit, cost about ten minutes of agent time and caught a defect that would otherwise have gone out under a `figsrc` crediting the correct page — the kind of error a fast human skim of the finished page does not catch, because the caption reads fluently and the image looks like a real Figure 1 either way.

---

## Session 15 — a third adversarial pass on synthid-text-watermarking (no new ingest)

**Source:** the session 13/14 page again, this time explicitly briefed as a check on the *fixes* session 14 applied, not just the original page. Third data point (after sessions 9/11 vs. session 12) on whether one same-session pass is enough — and the second time running this session's answer is "no": a genuinely independent second read, told outright not to trust the prior round's corrections, found 20 further fidelity issues and 8 craft issues on a page that had already been through one full adversarial cycle. None were as severe as session 14's missing figure panel, but several were the same *shape* of error the first round already fixed, just relocated: a hedge dropped in a newly-written sentence, a scope word ("production" for "experimental") introduced by a fix rather than removed by one, an internal contradiction between two passages written in different rounds.

**The two most instructive findings, because they're about editing rather than extracting:**

1. **A fix can introduce the exact defect class it was written to prevent.** Session 14's new aside about the tournament's `Nᵐ` candidate count at `m = 30` called it "the paper's production setting" — but the source only ever calls `m = 30` an *experimental* setting, and the page's own next paragraph says so correctly ("the paper's main experiments use m = 30"). The aside was added specifically to close a gap the first review found; writing it introduced a new, smaller version of the same species of error (an unearned specificity claim) two sentences from a correct one. Nothing about editing under review pressure makes a page immune to the mistakes the review pressure exists to catch.
2. **An unqualified positive claim survived two adversarial rounds because it was true at the wrong scope.** "No quality cost" for non-distortionary SynthID-Text is exactly what the paper's own theorem proves — for a single token, averaged over seeds. What neither the ingest nor the session-14 review caught is that the paper is explicit, twice, that this comes in *graded levels* with costs at both ends, and that the deployed (sequence-level) configuration is stated in the main text to cost "some reduction to inter-response diversity" — a fact the page had already correctly reported inside a figure caption without ever connecting it to the TLDR's flat "no quality cost" three sections earlier. A true claim, correctly sourced, at the wrong level of the paper's own hierarchy of guarantees, is a harder bug to catch than a false one — nothing about it reads as wrong locally, and the second reviewer only found it by holding the whole page's claims about the same property next to each other rather than checking each sentence against its own nearest source passage.

**What else this round found, confirmed and fixed:** two attack-type glosses (spoofing/scrubbing) that had been flagged as confusable in round one and never actually fixed — a reminder that a review's own "worth fixing" list needs to be checked off, not just written down; a citation credited to the wrong single source when the paper co-credits two (the sliding-window seed generator, cited to both Aaronson & Kirchner *and* Kirchenbauer et al., where the page's bibliography entry only named the first); a base technique (repeated context masking) named as "an existing technique" with no citation at all — the paper names it (Hu et al., ref. 27) and the page didn't, so a reader had a claim of prior art with no way to find the prior art; a "best prior scheme" hedge dropped from a sentence that had correctly kept its "to our knowledge" hedge two paragraphs over; a figure's own running-head ("Article", the journal's page furniture) baked into a cropped image with no mention in the alt text, caught only by re-rendering the source page and comparing pixel regions, not by reading the crop in isolation; a structural placement bug (Figure 1 introduced in the first sentence of a section, then not shown until three subsections later, sandwiched against Figure 2) that no fidelity check would ever catch because nothing in it is factually wrong.

**What held up a third time:** every number in the human-preference table (independently re-derived by a third agent rendering the same PDF region), all latency figures, every method parameter (H, m, N, K, the Bernoulli distribution), the corrected Figure 1 crop and its caption, the "learned Bayesian scoring function" addition from round one (independently verified as accurate and well-attributed), and all five evaluation conditions in the rewritten Figure 3 caption. Recording this because it means the fixable defects are getting rarer with each pass, not that the page was clean underneath — genuinely nothing token 1's crop-completeness class of bug turned up this time.

**On running a third round at all.** Sessions 9 and 11 concluded one pass "appears to be enough"; session 12 found that wrong on a different page; this session finds it wrong again, on the *same* page, on the *second* pass. Three data points now say a single review — even a good one — leaves real, findable defects on the table, and that the marginal round still pays for itself as long as it's genuinely independent (told explicitly not to trust the prior round, given the same primary-source access, and free to re-examine everything rather than only the diff). Whether a fourth round would still find something is untested; nothing here suggests the series converges to zero rather than just getting sparser.

---

## Session 16 — fixing the equation overflow bug on four already-published pages (no new ingest)

**Source:** none — a follow-up to session 15's `verify_page.py` change, fixing the four
pages the new `.eq__math` overflow check flagged: `context-engineering-survey`,
`slopcodebench`, `stealing-reasoning-traces` and `llm-field-guide`. Six overflowing
equations across the four pages, all fixed the same way: shorten the formula and move
anything cut into `.eq__read`, or — for `llm-field-guide`'s KV-cache formula, which is
long because every variable name is intentionally descriptive rather than a single
letter — wrap it onto multiple lines inside the `white-space: pre` block instead of
abbreviating the names, since the readability of `kv_heads`/`bytes_per_value` is the
point of that particular equation.

**What worked first time:**

- `stealing-reasoning-traces` has a committed builder script
  (`assets/scripts/stealing-reasoning-traces.build_content.py`); running it reproduced
  the committed page byte-for-byte before any edit, confirming the safe starting point
  without needing `recover_content_json.py` at all.
- For the other three, `recover_content_json.py --verify`'s round-trip failed on the
  already-documented harmless diff (session 6: a hard-wrapped colophon paragraph and an
  apostrophe entity) for `context-engineering-survey` and `slopcodebench` — expected, and
  the recovered JSON was safe to use.
- Shortening a formula by tightening spacing and moving descriptive clauses into
  `.eq__read` (rather than deleting content) held up across every fix — nothing was lost,
  each equation just got more compressed. Confirmed each one still renders correctly and
  reads sensibly with a phone-width screenshot before moving to the next page.

**What broke:**

1. **`recover_content_json.py`'s round-trip failure on `llm-field-guide` was not the
   known harmless diff — it silently dropped two real fields.** The recovered JSON fell
   back to the generic guide default colophon text instead of the page's actual custom
   `colophon_note`, and dropped `"scripts": ["assets/fieldguide.js"]` entirely. Rebuilding
   from that recovery without reading the diff closely would have shipped a page with
   every interactive widget dead (no script tag to load `fieldguide.js`) and the guide's
   real attribution swapped for boilerplate — a much worse outcome than the equation bug
   being fixed. Caught only because the `--verify` diff was read line by line instead of
   pattern-matched against the session-6 precedent and dismissed. Fixed by hand-patching
   both fields into the recovered JSON from the diff's own "before" text, then confirming
   a genuinely byte-exact round-trip before touching anything else. Logged in `TASKS.md`
   — `recover_content_json.py` should detect a non-default footer paragraph and a
   post-`app.js` script tag and recover both automatically.
2. **`colophon_note` needed a list, not a string, to reproduce two separate `<p>` tags**,
   and needed each list item to start with `<p>` so `as_paragraphs()` passed it through
   unescaped — passing plain strings round-tripped with `'` silently converted to
   `&#x27;`, which is the exact session-6 diff shape, this time self-inflicted rather than
   inherited.
3. **Fixing the equation on `slopcodebench` surfaced a second, unrelated bug in the same
   `verify_page.py` run**: five bibliography entries with zero inline citations anywhere
   in the body, the same failure session 10 recorded on a different page. Left unfixed
   and logged in `TASKS.md` rather than expanding this session's scope — but worth noting
   that running the checker for one reason surfaced an unrelated real defect for free,
   which is the same thing that happened when the `.eq__math` check itself first shipped.

**Tooling notes for this environment:**

- **`verify_page.py` on `llm-field-guide` needs a long timeout, not a fix.** The first
  attempt hit the harness's 2-minute default and looked like a hang; a 240-second budget
  completed normally. The guide has more images and interactive widget JS than a typical
  paper page, and that's just slower to settle to `networkidle`, not broken.

```
## Session N — <title> (<identifier>)

**Source:** pages, layout, figure kinds, size, anything unusual.

**What worked first time:**

**What broke:** the failure, the diagnosis, the fix, and the constant it changed.

**Non-extraction findings:**
```
