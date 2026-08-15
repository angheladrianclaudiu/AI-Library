---
name: review-resource
description: Audit a resource page already published in this AI Library against its original source and the library's writing standards, then correct what is genuinely wrong. Use whenever the user wants an existing page checked, reviewed, fact-checked, audited or critiqued — "review the page for X", "is the summary of X accurate", "check that page against the paper", "the numbers on X look wrong", "review PR #N" where the PR added a library page — and also when they ask for a second opinion on a page you or an earlier session wrote. This is the counterpart to /add-resource: that one creates a page, this one interrogates one that already exists. Handles source recovery, content-JSON reconstruction, two independent adversarial passes, adjudication and the rebuild; it does not commit until the user approves.
---

# Review a published resource page

The library's promise is one sentence: **you can read the page instead of the
source and actually understand it.** A review asks whether one page keeps that
promise, on two axes that fail independently:

- **Fidelity** — does the page say what the source says?
- **Craft** — can a newcomer actually follow it?

A page can be immaculately written and quietly wrong, or scrupulously accurate
and unreadable. That is why the two passes are separate agents with separate
theses, and why neither is allowed to see the other's report.

## Workflow

Copy this checklist and tick it off as you go:

```
- [ ] 1. Read the standards
- [ ] 2. Recover the source
- [ ] 3. Recover the content JSON and prove the round-trip
- [ ] 4. Brief two adversaries, in parallel, independent
- [ ] 5. Adjudicate every finding yourself
- [ ] 6. Fix in the JSON and rebuild
- [ ] 7. Re-verify in the browser
- [ ] 8. Record what the review taught you
- [ ] 9. Report and wait for approval
- [ ] 10. Commit in separate passes, and push
```

### 1. Read the standards

Read `CLAUDE.md`, `LEARNINGS.md`, and both references in the sibling skill:
`.claude/skills/add-resource/references/writing-guide.md` and `checklist.md`.

You are judging the page against these, so reviewing without them is just
opinion. `LEARNINGS.md` matters most — if the page came from a recorded ingest
session, that entry tells you what the extractor got wrong, what had to be
fixed by hand, and which judgement calls were deliberate. A "defect" you find
that turns out to be a decision recorded there is not a defect.

### 2. Recover the source

You cannot review fidelity without the source, and it is usually not in the
working tree: `inbox/` is gitignored and any temporary drop directory will have
been deleted once the ingest landed. **The open web is unreachable** — egress
allows GitHub, PyPI and npm only; everything else returns 403, `WebFetch`
included. Do not try to route around the proxy.

Both copies normally survive in git history. Find the commit that added them and
pull the blobs straight out, which moves a large file without it ever entering
your context:

```bash
git log --oneline --diff-filter=A --all -- '*<identifier>*'   # find the commit
git fetch --unshallow origin                                  # if the ref is missing
git show <ref>:<path>.pdf  > inbox/<identifier>.pdf
```

If history does not have it either, say so and ask the user to drop it in
`inbox/` — a fidelity review without the source is not worth running.

For a PDF, extract the text once and work from that rather than re-reading the
binary:

```python
import fitz
doc = fitz.open("inbox/<file>.pdf")
with open("inbox/<file>.txt", "w") as fh:
    for i, page in enumerate(doc):
        fh.write(f"\n=== PAGE {i + 1} ===\n{page.get_text()}")
```

The page markers are what let a finding cite a page number, so keep them. Note
where the body text ends and the bibliography begins — for a survey that can be
most of the file, and a reviewer who greps the whole thing will keep landing in
the reference list.

### 3. Recover the content JSON and prove the round-trip

`pages/*.html` and `index.html` are generated and **must never be hand-edited**.
The editable representation is the content JSON — and `.gitignore` matches
`*.content.json` repo-wide, so it is almost certainly gone.

Rebuild it from the page it produced:

```bash
python3 .claude/skills/review-resource/scripts/recover_content_json.py <slug> --verify
```

`--verify` rebuilds from the recovered JSON and diffs against the committed page,
restoring the working tree if they differ. **Do not edit a word until it reports
a byte-exact round-trip.** Reversing a generated artefact is guesswork until it
is proved, and a non-empty diff means *the JSON is wrong*, never that the page
is wrong. If the parse fails outright the template has changed since the script
was written; fix the script.

The script also warns when the "In short" block contains escaped markup — a real
defect where `<strong>` tags render as visible text, caused by a `tldr` entry
written as a bare string instead of `<p>…</p>`. It reproduces the bug so the
round-trip stays exact; wrap those entries in `<p>` as your first fix.

### 4. Brief two adversaries, in parallel, independent

Spawn both subagents **in a single message** so they run concurrently, and give
each the source paths and the page path. The briefs are templates — fill the
`{{…}}` slots and send each as the whole prompt:

- `references/fidelity-brief.md` — thesis: *this page misrepresents its source*
- `references/craft-brief.md` — thesis: *this page fails its reader*

Three things make the difference between useful reports and mush:

**Give each a thesis to prove, not a page to review.** "Review this page" returns
impressions. "Prove this page lies, and quote the page and cite the source page
number for every claim" returns findings you can act on.

**Keep them blind to each other.** Two independent passes that agree is evidence.
Two passes that have read each other is one pass with extra steps.

**Tell them what is already known not to be a defect**, or they will burn a round
rediscovering it and may "fix" a correct page. Currently: a `<table>` inside
`.table-scroll` is supposed to overflow its container, and the blocked Google
Fonts request is an environment quirk, not a page bug. Add to that list whatever
`LEARNINGS.md` records as a deliberate decision on this page.

If the page makes critical judgements about its source — that a claim is asserted
rather than measured, that an argument is a category error, that a figure
contradicts itself — name them in the fidelity brief. They are deliberate, but
they are still claims the page makes, and if one is wrong that is a serious
finding.

### 5. Adjudicate every finding yourself

**This is the step that decides whether the review is any good.** Read both
reports and verify each claimed defect against the source or the browser
*yourself* before acting on it. Do not accept either report at face value.

Adversarial agents over-report; that is the cost of the framing that makes them
useful, and it is your job to absorb it rather than pass it on.

The failure mode to watch for: **an agent quotes one passage and calls it the
source's position.** A source often states the same fact more than once, in
different words — and a page can be faithful to the primary statement while
differing from a later restatement. Before accepting a wording or unit finding,
go and look for the *primary* occurrence. A rejection like this is not a
technicality; acting on it would have introduced an error into a correct page.

Also worth pushing back on: recommendations that trade a real property for a
stylistic preference. A glossary that repeats a definition already given in the
body is not redundant — it is a random-access lookup, and that is the point.

Then say plainly, in your report to the user, **which findings you rejected and
why.** The rejections are as much a result as the fixes, and they are what tells
the user how much to trust the rest.

**One round of two adversaries is not proof the page is now correct.** Every
time this project has run a second independent round after a first round's
fixes — same page, same source, told explicitly not to trust the prior
round — it has found further real defects, including defects the first
round's own fixes introduced. Plan for at least two full cycles (brief →
adjudicate → fix → re-verify) on anything that isn't a trivial correction, and
keep going until a cycle returns nothing beyond findings already covered by
established precedent. Say in your report how many cycles it took, not just
the final state — that number is itself useful to the next session.

### 6. Fix in the JSON and rebuild

Edit `inbox/<slug>.content.json`, never the HTML. Each section's `html` field is
the body of the corresponding `<section>` minus the injected
`<span class="sec-num">` heading — the schema is in `make_page.py`'s docstring.

For anything beyond a couple of edits, apply them with a script that asserts each
replacement fired exactly once. Silent no-op edits on a 5,000-word page are very
easy to miss:

```python
def sub(sec_id, old, new, count=1):
    pat = re.compile(r"\s+".join(re.escape(t) for t in old.split()))
    hits = len(pat.findall(sections[sec_id]["html"]))
    if hits != count:
        sys.exit(f"FAIL [{sec_id}] expected {count} got {hits}: {old[:70]!r}")
    sections[sec_id]["html"] = pat.sub(lambda m: new, sections[sec_id]["html"])
```

Joining on `\s+` matters: the JSON carries the page's line wrapping, so a phrase
you copied from the rendered page will not match as a literal string.

Then rebuild — this regenerates the page, `data/library.json` and `index.html`:

```bash
python3 .claude/skills/add-resource/scripts/make_page.py inbox/<slug>.content.json
```

Word count and read time change when you add text. That is expected; the index
card updates with it.

### 7. Re-verify in the browser

```bash
NO_PROXY='*' python3 .claude/skills/review-resource/scripts/verify_page.py <slug> --shots /tmp/shots
```

It asserts no body overflow, scroll containers that fit and genuinely scroll,
images that decode, TOC and citation anchors that resolve, no dangling or unused
bibliography ids, a theme toggle that persists, and an index whose search and tag
chips both find the card — at 1280px and 390px in both themes. It exits non-zero
on failure, so it can gate the commit.

Then look at the screenshots. The script checks that things resolve, not that
they read well, and only a browser can tell you whether the page still reads.

### 8. Record what the review taught you

Append a session entry to `LEARNINGS.md` using the template at the bottom of that
file. A review session is worth recording even though nothing was extracted: what
the defects were, what *kind* of mistake produced them, and which findings you
rejected and why. The rejection is often the most reusable part.

If the review exposes a problem in the machine rather than the page, add it to
`TASKS.md` — and prefer a fix to the extractor, the templates or `make_page.py`
over a note telling the next session to be careful. `CLAUDE.md` is explicit that
changes to the machine should be justified by something that went wrong building
a page; a review is exactly that justification.

### 9. Report and wait for approval

Like `/add-resource`, this skill does not commit until the user approves. Report:

- what you found, worst first, each with the quoted page text and the source page
  number;
- what you **rejected**, and why;
- what you changed;
- the browser verification result.

If the review finds nothing worth changing, say so and change nothing. That is a
real outcome, and manufacturing a fix to justify the review makes the page worse.

### 10. Commit in separate passes, and push

Check `git status --porcelain` first — `inbox/` must not appear in it. Then keep
the content correction and the documentation in **separate commits**; the history
reads much better that way, and a later session tracing when a fact changed
should not have to step over a `LEARNINGS.md` edit.

Push to the branch named in the task with `git push -u origin <branch>`. If that
branch's pull request has already been merged, do not reuse it — a merged PR
cannot track new work. Start from the current default branch, keep the branch
name, and say plainly that the change needs a new PR.

## Where the defects actually are

From the reviews run so far, ordered by how often they turn up and how much they
cost the reader:

**Escaped markup in the "In short" block.** Invisible in the JSON, easy to miss in
a diff, and it is the first thing on the page. The recovery script now warns.

**A source sentence compressed one step too far.** The most common fidelity
failure by a distance, and it produces a false claim out of a correct number:
the source says a figure about *two* systems, the page attributes it to one.
Whenever a number is quoted, check what the subject of the source's sentence was.

**A corrupted name in the bibliography.** A plausible-looking name is
unfalsifiable by eye. Check every cited name against the source's own reference
list, which for a survey is usually right there in the same PDF.

**The most basic terms left undefined.** Not the exotic vocabulary — the terms so
fundamental the writer stopped seeing them, which the page then counts in or
hangs a headline number on. The glossary hides this by looking complete while
defining the easy ones.

**A figure that does not survive being read against the prose.** Three sources in
a row now have had a figure whose axis, ordering or plotted values contradict
what the caption claims. Treat this as the default expectation rather than bad
luck, and check the figure itself, not the caption — a caption is the authors'
claim about a figure.

**A figure crop that does not survive being checked against its own caption.**
A different failure from the one above: not the source's caption disagreeing
with the data, but *this page's* alt text and caption describing content —
a second panel, a labelled reference line, page furniture like a running head —
that simply is not in the saved image file. Invisible unless you open the crop
and read it cold, as if you had never seen the source's original figure.

**A fix introducing the same class of defect it was written to prevent.** A
sentence added specifically to close a fidelity gap can drop a hedge, add an
unearned scope word, or otherwise repeat the error one level down, precisely
because it was written under the same pressures (compress, sound confident) as
the original. A round that only diffs against the prior round's findings will
miss this; only a check against the primary source catches it.

**A claim that is true at one level of the source's own guarantees and stated
as if true at another.** The subtlest fidelity failure recorded so far: a
number or property the source proves under a specific, narrow condition,
repeated on the page as an unconditional fact. Nothing about the sentence
reads as wrong in isolation — it only surfaces when every claim about the same
property, wherever it appears on the page, is checked against each other and
not just against its own nearest source passage.
