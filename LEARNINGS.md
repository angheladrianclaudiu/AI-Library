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

## Session template

```
## Session N — <title> (<identifier>)

**Source:** pages, layout, figure kinds, size, anything unusual.

**What worked first time:**

**What broke:** the failure, the diagnosis, the fix, and the constant it changed.

**Non-extraction findings:**
```
