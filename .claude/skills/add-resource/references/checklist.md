# Verify before reporting

## Content

- [ ] The source was read end to end, not just its abstract and conclusion.
- [ ] Length matches what the source earns — nothing padded to hit a number.
- [ ] Every technical term is defined the first time it appears.
- [ ] Every equation is followed by a plain-English reading in its `.eq__read`.
- [ ] What was genuinely new is distinguished from what came from prior work.
- [ ] Claims are attributed ("the authors report") where the evidence is thin.
- [ ] Limitations section is real, not an apology.
- [ ] The `hook` reads well on a card: one or two sentences, no title repetition.

## Figures

- [ ] Each figure kept was actually looked at, and is cropped to the artwork —
      no slabs of body text, no clipped edges.
- [ ] Every figure has your own caption saying what it shows *and why it matters*.
- [ ] Every `<img>` has a descriptive `alt`, plus `width` and `height`.
- [ ] Unused candidates deleted from `assets/images/<slug>/`.
- [ ] `ls assets/images/<slug>/` matches exactly the images the page references.

## Technical

- [ ] `python3 -m json.tool data/library.json` and `data/tags.json` parse.
- [ ] Every `class="cit"` has a matching `id="rN"` in the bibliography.
- [ ] Every wide table is wrapped in `.table-scroll`.
- [ ] Page opens with no console errors; all images load.
- [ ] Reads correctly in **both** light and dark, at desktop and phone width.
- [ ] TOC anchors all resolve; "Back to the library" works.
- [ ] The new card appears on `index.html`, and search and its tags find it.
- [ ] No absolute URLs except the Google Fonts link and deliberate source links.

## Delivery

- [ ] PDF under 1 MB → committed to `assets/pdf/` and linked; 1 MB or over →
      not committed, `source_url` linked instead.
- [ ] `git status --porcelain` shows only intended files — no `inbox/` leakage,
      no stray `.webp` candidates.
- [ ] Reported to the user, and **waiting for approval** before committing.
