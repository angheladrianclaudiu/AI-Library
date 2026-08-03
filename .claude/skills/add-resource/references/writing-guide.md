# Writing the explanation

The promise of this library is one sentence: **you can read the page instead of
the paper and actually understand the idea.** Everything below serves that.

## The standard skeleton

Adapt it to the source — a survey and a methods paper do not want the same
shape — but start here.

| Section | `id` | What goes in it |
|---|---|---|
| The problem | `the-problem` | What was broken or missing, and why it mattered. What people did before, and where that ran out. |
| The core idea | `the-core-idea` | The one insight, stated in a paragraph a non-specialist can follow. If you can't, you haven't understood it yet. |
| How it works | `how-it-works` | Step by step. Use sub-headings. This is where the figures and equations live. |
| What the results show | `results` | What was measured, against what baseline, and how much of the gain is the idea versus more compute or data. |
| Why it matters | `why-it-matters` | What it changed. Where you meet it today. Be concrete — name systems that use it. |
| Limitations | `limitations` | What the authors admit; what reviewers and later work pushed back on; what it does *not* do. |
| Glossary | `glossary` | Every term a newcomer would stumble on. Usually 5–12 entries. |
| Sources | `sources` | The original, plus anything you cite. |

Give an article-derived page whatever sections its argument actually has —
don't force a blog post into a paper's shape.

## Rules

**Define every term the first time it appears.** "Logits", "ablation",
"perplexity", "KV cache" — one clause is enough, but it has to be there.

**Explain every equation in words.** There is no maths renderer. Show the
formula as Unicode in an `.eq` block and follow it with a plain reading of what
each symbol means and what the line *does*. If an equation cannot survive that
treatment, leave it out and describe the operation in prose instead.

**Say what was actually new.** Papers are written to sound novel. Separate the
genuinely new contribution from the parts assembled out of prior work — the
reader learns more from that distinction than from the result table.

**Separate claims from evidence.** "The authors report X" and "the experiments
show X" are different sentences. Use whichever is true. If a claim rests on one
benchmark, say so.

**Prose over bullet lists.** Lists are for things that are genuinely a list —
steps, options, criteria. An argument in bullets is an argument with the
reasoning removed.

**Use concrete analogies, then drop them.** An analogy that carries one idea is
worth a paragraph; one stretched across a whole page starts lying.

**Write in the past tense about what the paper did**, present about what is
true now. Don't call a 2017 paper "recent".

**No hype.** No "revolutionary", "groundbreaking", "paradigm shift". If the
work mattered, say what changed because of it and let that do the work.

Optional last pass: run the `humanizer` skill over your draft to strip AI
writing tells before building the page.

## Components

The content JSON's `html` fields take raw HTML. These classes exist in
`assets/style.css` — use them rather than inventing markup.

### Text

```html
<p class="lead">An opening paragraph, set slightly larger.</p>
<p>Ordinary body text.</p>
<h3>A sub-heading inside a section</h3>
<blockquote><p>Quoted words.</p><cite>Author, 2017</cite></blockquote>
```

### Figures

Paths are relative to `pages/`, so they start with `../assets/`.

```html
<figure>
  <img src="../assets/images/<slug>/fig-p03-figure-2.webp"
       alt="What the image shows, for someone who cannot see it."
       width="1200" height="800">
  <figcaption>
    <span class="figlabel">Figure 2</span>What it shows and, more importantly,
    why it matters to the argument.
    <span class="figsrc">Extracted from page 3 of the source PDF.</span>
  </figcaption>
</figure>
```

Add `class="wide"` for a figure that needs the extra width — a wide
architecture diagram. It then spans into the right margin on large screens.
Always set `width`/`height` from the figures JSON so the page doesn't jump
while images load.

### Equations

```html
<div class="eq">
  <div class="eq__math">Attention(Q, K, V) = softmax( Q·Kᵀ / √d_k ) · V</div>
  <div class="eq__read"><strong>In words</strong>Compare every query against
  every key with a dot product; divide by √d_k so softmax isn't saturated;
  turn the scores into weights that sum to one; average the values with them.
  </div>
</div>
```

Useful Unicode: `× · ÷ ± ≈ ≠ ≤ ≥ √ ∑ ∏ ∫ ∂ ∇ ∈ ∞ α β γ δ ε θ λ μ σ τ φ ω Δ Σ Ω`,
superscripts `⁰¹²³ⁿᵀ`, subscripts `₀₁₂ₙᵢⱼₖ`, arrows `→ ← ↦ ⇒`.

### Callouts

```html
<div class="callout callout--intuition">
  <span class="callout__label">Intuition</span>
  <p>The plain-language version of what just happened.</p>
</div>
```

`--intuition` for the "what this really means" aside, `--caveat` for a
limitation or contested claim, `--note` for everything else. Three or four per
page; more and they stop standing out.

### Code, tables, glossary, citations

```html
<pre><code>for layer in stack:
    h = h + attention(norm(h))</code></pre>

<div class="table-scroll"><table>…</table></div>

<dl class="glossary"><dt>Term</dt><dd>Definition.</dd></dl>

<p>As shown in the original paper<a href="#r1" class="cit">1</a>.</p>
<ol class="biblio"><li id="r1">Author et al. <em>Title</em>. Venue, 2017.</li></ol>
```

Tables always go inside `.table-scroll` — otherwise a wide table pushes the
whole page sideways on a phone. Two modifiers matter for results tables:

```html
<div class="table-scroll wide"><table class="numeric">…</table></div>
```

`class="numeric"` on the table stops cells breaking mid-value, so `0.68 ± 0.20`
stays on one line — leave it off for tables whose cells hold prose. `wide` on the
wrapper lets the table use the right margin on large screens, the same escape
`figure.wide` gets; use it when a results table has more than about four columns,
or the last column ends up clipped inside the scroll box.

Every `class="cit"` needs a matching `id` in the bibliography; `make_page.py`
does not check this for you, so check it.

### Interactive instruments (`type: "guide"` only)

A guide can carry widgets driven by `assets/fieldguide.js`, listed in the
content JSON's `scripts` array. The markup is plain HTML with agreed ids; the
script wires the behaviour and bails out when a widget's root is absent.

```html
<div class="fg" id="fg-kv">
  <div class="fg__label"><span>KV cache calculator</span><em id="fg-kv-headline">—</em></div>
  <div class="fg__cols">
    <div class="fg__ctl">
      <label for="fg-kv-c"><span>context length</span><b id="fg-kv-c-v">128K tokens</b></label>
      <input type="range" id="fg-kv-c" min="8" max="1024" step="8" value="128">
    </div>
  </div>
  <p class="fg__note">A sentence about how to read it.</p>
  <div class="fg__readout"><div><b>KV cache</b><span id="fg-kv-total">—</span></div></div>
</div>
```

Two rules, both learned the hard way:

**No colour literals anywhere.** Everything paintable is a `--fg-*` custom
property in `style.css`, which the script re-reads on every theme change. A
colour hard-coded in JS survives into dark mode and blinds someone.

**Every control needs a real label.** `<label for>` on sliders, `<button>` with
`aria-pressed` for toggles, `role="img"` plus a live `aria-label` on anything
drawn as a grid. A `<span onclick>` is not a control.

Prefer `--ink-soft` over `--ink-faint` for anything under about 12px:
`--ink-faint` measures 4.08:1 on `--bg-raised` in light mode and fails AA.
