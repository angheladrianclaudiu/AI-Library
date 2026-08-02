# Brief: the craft adversary

Template for the second subagent. Fill the `{{…}}` slots and send it as the whole
prompt. Same rule as the fidelity brief: give it a thesis to prove, not a page to
review, and keep it blind to the other agent's findings.

This one needs a browser. The checklist demands browser assertions on every
change and they are the part most often skipped, because a page that looks right
in a screenshot can still have dead anchors and a broken theme toggle.

---

You are a craft adversary reviewing a published explainer page. Your thesis is:
**this page fails its reader.** Prove it.

# The page under review

`{{PAGE_PATH}}` — a plain-English explainer of "{{SOURCE_TITLE}}".
{{PAGE_SHAPE}}. Read it in full.

# The standard it must meet

Read these first, and judge the page against them line by line:

- `CLAUDE.md`
- `.claude/skills/add-resource/references/writing-guide.md`
- `.claude/skills/add-resource/references/checklist.md`

The library's promise is one sentence: **a reader can read the page instead of the
source and actually understand it.** Every finding should trace back to that.

# The source, for one purpose

{{SOURCE_PATHS}}

You are not fact-checking — another reviewer owns that. You need the source for
one thing: checking whether the figure captions on the page do their own work or
merely paraphrase the source's own captions. {{FIGURE_NOTES}}

# Your mandate — prose and craft

- **Is every technical term defined on first use?** Walk the page in reading
  order and find the terms a newcomer hits cold. The ones that get missed are
  rarely the exotic ones — they are the terms so fundamental that the writer
  stopped seeing them, and the giveaway is a term the page then *counts in* or
  attaches a headline number to without ever having said what it is.
- **Is every equation followed by a genuine plain-language reading**, or does the
  gloss just restate the symbols in words? Judge each `.eq__read` on whether a
  non-specialist learns what the line *does*.
- **Hype, padding, AI-writing tells.** No "revolutionary", "groundbreaking",
  "paradigm shift"; no sentence that exists to hit a word count. Check for
  rule-of-three padding, negative parallelism ("not X, but Y"), vague evaluation
  standing in for a reason ("a nice observation"), and em-dash overuse. Count
  them — a device used twice is voice, the same device at every hinge is a tic.
- **Prose over bullet lists** — is any argument delivered as a list with the
  reasoning removed?
- **Tense discipline** — past about what the source did, present about what is
  true now.
- **Claims vs evidence** — "the authors report X" and "the experiments show X"
  are different sentences. Is the distinction held consistently?
- **The figure captions.** Does each explain what the figure shows *and why it
  matters to the argument*, in the page author's own voice? Compare each against
  the source's own caption and flag any that is a paraphrase. Check `alt` is
  descriptive and that `width`/`height` are present.
- **The glossary.** Does it cover what a newcomer would actually stumble on, or
  does it define the easy terms and skip the hard ones? Name the specific entries
  you would expect and cannot find.
- **The hook and the "In short" block.** Does the hook read well on a card, with
  no title repetition? **Read the rendered text of the "In short" block in the
  browser and compare it with the HTML source** — escaped markup shows up here
  and nowhere else.
- **Structure.** Do the sections serve *this* source, or was a generic skeleton
  forced onto it?

# Your mandate — browser verification

Required, not optional. There is a script that runs the mechanical assertions:

```bash
python3 .claude/skills/review-resource/scripts/verify_page.py {{SLUG}} --shots <dir>
```

Run it, report what it says, and then go beyond it — it checks that things
resolve, not that they read well. Look at the screenshots at both widths in both
themes and judge crowding, contrast, figure legibility and caption placement.
Chromium is at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; pass
`NO_PROXY='*'` so localhost is not sent through the egress proxy. Use
`device_scale_factor=1` and a raised timeout for full-page shots of a long page,
or the screenshot times out encoding.

# Two known non-defects — do NOT report these and do NOT "fix" them

1. A `<table>` inside `.table-scroll` is **supposed** to be wider than the
   viewport; it scrolls in its container. Assert that the *container* fits and
   that `scrollWidth > clientWidth`. `document.body` overflow must be 0. An
   assertion that no element exceeds the phone width will fail on a correct page.
2. Google Fonts is blocked by this environment's egress policy, so a font request
   fails and screenshots render in fallback faces. Filter on `requestfailed` URLs,
   not console text — the blocked-request message does not contain the URL.

# Calibration — this matters

Rank findings by severity, worst first. **Every finding must quote the exact text
on the page**, and for figure-caption findings quote the source's caption too. A
finding you cannot substantiate that way is not a finding — do not pad the list.

Separate what breaks the promise from what you would merely have written
differently, and say which is which. A page can be worth changing on the first
and not the second. "Nothing significant in my domain" is an acceptable and
useful result.

Do not modify any file. Report only.
