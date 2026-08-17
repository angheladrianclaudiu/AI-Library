#!/usr/bin/env python3
"""Regenerate inbox/deputydev-productivity-study.content.json from scratch.

The content JSON itself is gitignored (`.gitignore` matches `*.content.json`
repo-wide), so this script is what actually survives in history — run it from
the repo root, then `make_page.py` on its output, to reproduce the page
without needing the original 16-page PDF.

    python3 assets/scripts/deputydev-productivity-study.build_content.py
    python3 .claude/skills/add-resource/scripts/make_page.py \\
        inbox/deputydev-productivity-study.content.json
"""
import json

SLUG = "deputydev-productivity-study"

hook = (
    "300 engineers at the Indian healthtech company 1mg used an in-house AI coding "
    "platform for a year, and the team that built it measured what happened: a 31.8% "
    "drop in PR review cycle time, adoption that spent months near 60% before jumping to "
    "an 83% peak in the study's final month, and a productivity gain that tracked usage "
    "intensity almost exactly — engineers who barely touched the tool shipped less code, "
    "not more."
)

tldr = [
    "<p>Most evidence for AI coding tools comes from controlled benchmarks or short "
    "pilot studies. This paper, from engineers at the Indian online-pharmacy company "
    "1mg (part of the Tata Group), reports on a full year of production use instead: "
    "300 engineers using an in-house platform called DeputyDev, which pairs a "
    "multi-agent pull-request reviewer with a VS Code coding assistant, from September "
    "2024 to August 2025.</p>",
    "<p>The headline numbers are a 31.8% reduction in PR review cycle time across the "
    "whole engineering org, adoption that climbed from 4% of engineers in month one to "
    "an 83% peak in the study's final month, and a code-acceptance rate that "
    "grew from 4.7% to 38.0% as the tool matured. The more interesting result is what "
    "happened when the authors split engineers by how much they actually used the tool: "
    "the top 30 adopters shipped 61% more code after adoption, while the bottom 30 "
    "shipped 11% less — the same tool, opposite outcomes, depending entirely on "
    "engagement.</p>",
    "<p>Because the authors are also the platform's own builders, this reads as much as "
    "an engineering postmortem as a research paper: cost breakdowns down to the dollar, "
    "a list of what failed (automatic code acceptance, generic one-size-fits-all "
    "models) alongside what worked, and survey data on developer trust. The paper is "
    "also, in a few places, at odds with its own numbers — including cohort definitions "
    "that contradict themselves and a conclusion that restates an earlier result "
    "incorrectly.</p>",
]

# ---------------------------------------------------------------------------
sec_problem = """
<p class="lead">Most published evidence that AI coding assistants help comes from one of two
places: a controlled benchmark like HumanEval or SWE-bench, or a short-lived pilot. Both are
useful, and both leave out most of what makes real software engineering hard — large,
inconsistent codebases, teams with their own conventions, tools that have to fit into an
existing pipeline, and engineers who may or may not trust a new system enough to actually use
it. The paper's own framing is that benchmark performance and "comprehensive production
utility across the full development lifecycle" are two different things, and that the gap
between them was, at the time of writing, largely unmeasured. That evidence is also mixed
rather than uniformly positive — the paper's own related-work section cites a separate 2025
study that found AI tools increasing completion time by 19% for experienced open-source
developers, the opposite of the result this paper goes on to report.</p>

<p>This paper is an attempt to close that gap with one long, real deployment rather than a
short experiment. Over a full year — September 2024 through August 2025 — 300 software
engineers at 1mg, an Indian online pharmacy and healthtech company owned by the Tata Group,
used an in-house AI platform called <strong>DeputyDev</strong>. It combines two things: an
automated pull-request reviewer, live for the whole year, and a code-generation assistant
built into VS Code, added six months in. The authors set out to answer four questions: does
AI-assisted coding measurably help productivity outside a benchmark, how good is AI code
review at catching real problems, what human and organisational factors shape adoption, and
what does the tool actually cost against what it returns.</p>

<p>It is worth naming upfront who is asking these questions. This is not a benchmark study or
a customer case study written by a vendor — it is 1mg's own engineering team evaluating a
tool their own team built, using their own company's production data. That is a real source
of production-scale evidence unavailable to outside researchers, and it is also a conflict of
interest the paper itself never states in those terms, even though its own limitations
section comes close (see <a href="#limitations">Limitations</a>). It is also the second paper
this team has published about DeputyDev: an earlier, smaller study of just the review
feature — a controlled A/B test across over 200 engineers — reported a 23.09% cut in PR
review duration<a href="#r2" class="cit">2</a>. This paper is the follow-up at full scale, with
the code-generation half of the tool added in.</p>
"""

# ---------------------------------------------------------------------------
sec_system = """
<p>DeputyDev has two halves that launched on different schedules: a PR review system, live
for the entire study, and a code-generation assistant, added in March 2025 partway through the
year.</p>

<h3>Reviewing pull requests</h3>

<p>The review side hooks into Bitbucket and GitHub and fires automatically on every pull
request. Under the hood it runs what the paper calls a multi-agent system — separate model
calls, each looking at the PR from one angle, running in parallel and powered by Claude Sonnet
3.7 and 4.0. The paper's prose and Figure 3's own caption both say "six specialized agents,"
and Figure 3 itself (below) draws exactly six boxes — but the table describing them (reproduced
below) lists seven, and its own caption calls all seven "specialized agents" too: a Summary
agent alongside Security, Documentation, Code Maintainability, Error Detection, Performance
Optimization and Business Validation. The diagram's omission of Summary is consistent with
reading "six specialized agents" as the six that produce line-level review comments, with
Summary running as a separate pass — a plausible reconciliation, though the paper never states
it, and the table's own caption cuts against it. Three of the seven —
Summary, Security, Documentation — work from the base model alone; the other four are given a
small toolkit: a file reader capped at 100 lines per request, a fuzzy path searcher, a
ripgrep-backed grep tool, and a "planner" for breaking a review into multiple reasoning
steps.</p>

<div class="table-scroll">
<table>
<thead><tr><th>Agent</th><th>Focus</th><th>Tools available</th></tr></thead>
<tbody>
<tr><td>Summary</td><td>Comprehensive summary</td><td>Base LLM only</td></tr>
<tr><td>Security</td><td>Vulnerability detection</td><td>Base LLM only</td></tr>
<tr><td>Documentation</td><td>Code documentation</td><td>Base LLM only</td></tr>
<tr><td>Code Maintainability</td><td>Code quality</td><td>File Reader, Path Searcher, Grep, Planner</td></tr>
<tr><td>Error Detection</td><td>Bug identification</td><td>File Reader, Path Searcher, Grep, Planner</td></tr>
<tr><td>Performance Optimization</td><td>Code efficiency</td><td>File Reader, Path Searcher, Grep, Planner</td></tr>
<tr><td>Business Validation</td><td>Logic verification</td><td>File Reader, Path Searcher, Grep, Planner</td></tr>
</tbody>
</table>
</div>

<figure class="wide">
  <img src="../assets/images/deputydev-productivity-study/fig-p04-x474.webp"
       alt="Flowchart: DeputyDev Automated Code Review System feeds a Multi-dimensional Analysis
       stage that fans out to six labelled boxes (Security, Error, Code Maintainability,
       Performance Optimization, Documentation, Business Validation), which all feed into a
       Comment Blending Engine, then a Human Reviewer Decision diamond branching to PR Merge
       or Feedback."
       width="1400" height="910">
  <figcaption>
    <span class="figlabel">Figure 3</span>The review pipeline. Each agent's findings pass
    through a blending engine that removes duplicate comments, filters out invalid
    suggestions, and merges overlapping feedback on the same line before a human ever sees it —
    with each surviving comment still tagged with which agent raised it.
    <span class="figsrc">Extracted from page 4 of the source PDF.</span>
  </figcaption>
</figure>

<p>That blending step is doing real work: six independent reviewers each producing comments
on the same diff would otherwise mean six times the noise. The paper doesn't quantify how
much the blending engine filters out, but does say every comment that survives keeps its
originating agent attached, for both transparency and debugging.</p>

<h3>Generating code</h3>

<p>The second half is a VS Code extension for writing code, not just reviewing it. It indexes
a repository into a Weaviate vector database, chunked by module, class and function rather
than by raw file, so a search can return a semantically relevant function even if it doesn't
share vocabulary with the query. On top of that search it layers language-server integration
for syntax and type checking, and MCP (Model Context Protocol) support for pulling in external
context.</p>

<figure>
  <img src="../assets/images/deputydev-productivity-study/fig-p06-x476.webp"
       alt="Flowchart: a Software Engineer box feeds into DeputyDev Code Generation Engine,
       which outputs to Code Suggestions and Recommendations, then an Engineer Acceptance
       Decision diamond that branches to Pull Request Creation on Accept or loops back to the
       generation engine on Reject."
       width="1400" height="3274">
  <figcaption>
    <span class="figlabel">Figure 5</span>The code-generation loop. Suggestions the engineer
    rejects go straight back into the generation engine rather than ending the interaction —
    the tool treats a rejection as a cue to retry, not a dead end.
    <span class="figsrc">Extracted from page 6 of the source PDF.</span>
  </figcaption>
</figure>

<p>The extension offers two modes: <strong>Chat mode</strong>, for talking through an approach
before writing anything, and <strong>Act mode</strong>, which edits files directly, subject to
the engineer reviewing and accepting the diff. Both matter later — the paper reads its own
usage data as a drift from Chat toward Act over time, and then reports a directly-surveyed
preference that runs the other way (see <a href="#developer-trust">Developer trust</a>).</p>
"""

# ---------------------------------------------------------------------------
sec_methodology = """
<p>A randomized controlled trial — some engineers get the tool, some don't, compare outcomes —
was not realistic here; you cannot split a production engineering org into a treatment and
control group without disrupting the teams themselves. Instead the paper leans on what it
calls a <strong>quasi-experimental design</strong>: a study that compares groups or time
periods it didn't get to randomly assign, using statistical controls to approximate what
randomization would have given it for free.</p>

<p>Concretely, that means two comparisons layered on top of each other. The
<strong>within-subjects</strong> comparison treats every engineer as their own control,
measuring their productivity in a six-month baseline before code generation launched against
their own performance six months after. The <strong>between-subjects</strong> comparison
instead groups engineers by how heavily they actually used the tool — a high-adoption cohort,
a low-adoption cohort, and everyone in between — and compares those groups to each other. Five
confounding variables are named as controlled for: seniority level, project complexity,
team-level effects, month-to-month organisational changes, and each engineer's own
pre-deployment baseline (folded in as a covariate via ANCOVA, a standard technique for
adjusting an outcome for a starting-point difference between groups).</p>

<p>The quantitative telemetry — commit and PR metrics from version-control webhooks, tool
usage from DeputyDev's own instrumentation — is cross-checked against three other sources: a
228-engineer survey (a 76% response rate), qualitative interviews with 125 engineers, and
manager assessments of team-level output. The paper is also candid about what this design
can't rule out. It names selection bias (addressed partly through matching high- and
low-adoption engineers on their pre-deployment baselines), the Hawthorne effect — people
behaving differently because they know they're being observed — and maturation effects like
engineers simply getting more experienced over the year regardless of the tool. On the
Hawthorne point specifically, the paper states that engineers were not told they were part of
a study; that heads off the Hawthorne effect as a confound, but the paper never discusses
whether — or how — that non-disclosure was reconciled with informing the engineers whose work
was being measured.</p>
"""

# ---------------------------------------------------------------------------
sec_adoption = """
<p>Code review launched first, in September 2024, and was applied automatically to every pull
request across the org — roughly 3,000 PRs a month with no opt-in required. Code generation
launched six months later, in March 2025, as an opt-in VS Code extension, which is why its
adoption has its own separate curve.</p>

<figure>
  <img src="../assets/images/deputydev-productivity-study/fig-p07-x477.webp"
       alt="Dual-axis line chart, March to August 2025. Monthly active users jumps from 10 to
       181 between March and April, plateaus around 168-197 from April to July, then rises to
       250 in August (left axis). Monthly requests climb steadily from about 1,000 to 377,000,
       accelerating most between June and August (right axis)."
       width="1400" height="981">
  <figcaption>
    <span class="figlabel">Figure 6</span>Monthly active users and request volume for the
    code-generation extension. Requests grew about 260-fold over the tool's first six months
    (1,445 to 376,943, per the source's own figures) while active users grew 25-fold — each
    engineer who stuck with the tool was sending it far more requests by August than an early
    adopter was in March.
    <span class="figsrc">Extracted from page 7 of the source PDF.</span>
  </figcaption>
</figure>

<p>Only 4% of engineers used the code-generation tool in its first month. The text describes
what happened next as adoption that "accelerated in months 2-3, reaching peak engagement of
83% by month 6," then "stabilising at around 60% for the remainder of the study period" — but
Figure 6, which the text cites for this claim, doesn't support the shape of that description.
Month 2 (April) jumped straight to 60% (181 of 300 engineers), and month 3 (May) <em>fell</em>
to 56% (168) — hard to square with a description of continuous acceleration. And the chart
only covers six months total, with
its own last data point <em>at</em> month six, the 83% peak; there is no "remainder" left in the
data for adoption to stabilize into afterward. If anything, the ~60% plateau the text describes
happened <em>before</em> the peak (April through July), and the jump to 83% happened in the
final month shown. Of the traffic that did stick around, usage concentrated heavily in three
categories: UI/frontend work (25.2% of requests), bug fixing and debugging (21.8%), and
backend code generation (21.1%) — together nearly 70% of everything the tool was asked to do.
Documentation, project management and security-related requests each stayed under 2%, which
the paper reads as headroom for future expansion rather than a sign those use cases don't fit
the tool.</p>
"""

# ---------------------------------------------------------------------------
sec_results = """
<p>The paper's central productivity claim is a 31.8% reduction in PR review cycle time. It
compares the first six months of the study (September 2024 to February 2025) against the
second six (March to August 2025). Two separate timers moved: mean <strong>cycle time</strong>
fell from 150.5 hours to 99.6 hours (a 33.8% drop, statistically significant at
p&nbsp;=&nbsp;0.0018), and mean <strong>review time</strong> specifically fell from 128.8 hours
to 90.5 hours (29.8%, p&nbsp;=&nbsp;0.0076). The paper never defines either term, and its own
Figure 1 shows why a reader shouldn't guess: in September 2024, plotted review time (148h)
is <em>higher</em> than plotted cycle time (146.2h) — the reverse of what "cycle time contains
review time" would predict, and the only month where that happens. The paper's headline
"31.8%" figure is the average of the two percentage drops above.</p>

<div class="callout callout--caveat">
  <span class="callout__label">Caveat</span>
  <p>Two things complicate reading this as a clean before/after AI comparison. First, the PR
  review system was live for <em>both</em> halves of this split — it launched in September
  2024, the very start of the "baseline" period — so this isn't a with-tool/without-tool
  comparison for the half of DeputyDev that most plausibly affects review time. Second, the
  paper itself attributes the improvement to something else: both times it reports these
  numbers (once describing the whole-population split above, once describing the top-30
  adopters below), it credits the gain to "process optimization interventions" that coincided
  with the study period, without ever specifying what those interventions were or how much of
  the effect is theirs versus DeputyDev's.</p>
</div>

<figure class="wide">
  <img src="../assets/images/deputydev-productivity-study/fig-p01-x85.webp"
       alt="Line chart, September 2024 to August 2025, showing PR Review Time and PR Cycle Time
       in hours, both trending down from around 148 and 146 hours to 55 and 58 hours. A
       statistics summary box in the lower left reads: PR Cycle Time mean 125.0h, PR Review
       Time mean 109.7h, and 'Improvement: 60.1% cycle time reduction'."
       width="1400" height="689">
  <figcaption>
    <span class="figlabel">Figure 1</span>The month-by-month version of the headline result.
    Averaging the first six plotted points against the last six reproduces the 33.8%/29.8%
    figures the text reports — but the chart's own summary box instead states "Improvement:
    60.1% cycle time reduction," a third number matching neither. That third number checks out
    too, just against a different comparison the box never names: September 2024's cycle time
    (146.2h) against August 2025's (58.4h) — the single first and last points on the line,
    rather than six-month averages — comes to a 60.1% drop.
    <span class="figsrc">Extracted from page 1 of the source PDF.</span>
  </figcaption>
</figure>

<div class="callout callout--caveat">
  <span class="callout__label">Caveat</span>
  <p>Figure 1 is the first thing a reader sees, on page 1, and its summary box reports a
  bigger, differently-computed number than the 31.8% the rest of the paper uses — without
  saying so. Endpoint-to-endpoint and six-month-average-to-six-month-average are both
  legitimate ways to describe the same trend line, but they answer different questions, and a
  reader who takes the box at face value walks away with a number the paper's own text never
  uses anywhere else.</p>
</div>

<p>The more interesting comparison splits engineers by how much they actually used the tool,
rather than by calendar time. The top 30 adopters by usage shipped 61.3% more code after
adoption (168,676 → 272,191 lines); separately, the paper reports roughly 150,000 lines of
AI-generated code merged to production over the same period, without stating whether that
figure is a subset of the 272,191 or counted alongside it. The bottom 30 — engineers who
engaged only sporadically — shipped 11.4% <em>less</em> code than before (253,332 → 224,282
lines), and merged fewer than 200 AI-generated lines the entire period. The paper calls the
72.7-percentage-point gap between those two changes (61.3% vs. −11.4%) a "robust treatment
effect," in the style of a <strong>difference-in-differences</strong> analysis — comparing how
much each group changed, rather than just comparing their end states — attributable to
engagement rather than to who was already a stronger engineer, since the two groups were
matched on pre-deployment baseline performance. That matching claim is worth checking against
the same numbers: the two 30-engineer cohorts' own pre-adoption baselines were 168,676 and
253,332 lines shipped — the low-adoption group's baseline was 50% higher than the
high-adoption group's, which sits uneasily next to "matched." One further number is worth
holding more loosely than the rest: the top-30 group's 61.3% increase is reported at
p&nbsp;&lt;&nbsp;0.001, a strong result, but the bottom-30 group's 11.4% decline sits at
p&nbsp;=&nbsp;0.08 — short of the conventional 0.05 threshold below which every other
significance claim on this page falls, though the paper narrates it with the same confidence
as the significant numbers around it.</p>

<p>Worth naming why this page calls them "top 30" and "bottom 30" rather than the paper's own
"Cohort 1"/"Cohort 2": those exact labels get reused, a page earlier (§5.2.1), for the
unrelated <em>whole-population</em> before/after comparison above — different engineers,
different metric, different numbers, same name. This page describes each comparison by what
it actually measures instead of reusing a label the paper itself overloads.</p>

<figure class="wide">
  <img src="../assets/images/deputydev-productivity-study/fig-p08-x482.webp"
       alt="Grouped bar chart comparing Cohort 1 (top 30 DeputyDev users) and Cohort 2 (bottom
       30 DeputyDev users) on code shipped before DD, code shipped after DD, and lines of code
       accepted. Cohort 1 rises from 168,676 to 272,191 with 149,819 LOC accepted; Cohort 2
       falls from 253,332 to 224,282, with LOC accepted labelled 200 but no visible bar height
       at that scale."
       width="1400" height="834">
  <figcaption>
    <span class="figlabel">Figure 9</span>Shipped code, before and after adoption, split by
    usage intensity rather than by calendar date. The low-adoption group's AI-generated line
    count doesn't clear the chart's scale at all — it shows only as a "200" label with no bar
    — next to the ~150,000 lines the high-adoption group merged.
    <span class="figsrc">Extracted from page 8 of the source PDF.</span>
  </figcaption>
</figure>

<p>A further breakdown, by seniority, shows the gain concentrated at the junior end: junior
engineers (SDE1) shipped 77.0% more code after adoption, against 44.6% for both the mid-level
(SDE2) and senior (SDE3) bands, for an "Overall" 60.1% increase — the paper's own word. That
word invites reading this as the whole 300-engineer org, but the table's own total of 167,047
lines shipped "before" is smaller than the 253,332 lines the low-adoption 30-engineer group
alone shipped before adoption in the comparison above — so it can't be everyone. It's much
closer to being the high-adoption group specifically: 167,047 and 267,509 sit within 2% of
that group's own 168,676 and 272,191 from Figure 9 above — though the two tables' AI-generated
line counts don't match nearly as closely (141,873 accepted here against roughly 150,000
merged in Figure 9, a 5% gap). The paper never says so, but this table reads as close to the
same 30 engineers, sliced by seniority rather than relabelled as "Overall," even if it isn't
an exact reproduction.</p>

<p>The paper separately reports that production code volume grew 28% over the study, and that
roughly 40% of all code shipped to production in August 2025 was AI-generated — two more
headline figures that, like "Overall" above, don't state what population or baseline they're
measured against.</p>

<div class="table-scroll wide">
<table class="numeric">
<thead><tr><th>Level</th><th>Before</th><th>After</th><th>Change</th><th>AI-generated</th><th>Accepted</th><th>Accept rate</th></tr></thead>
<tbody>
<tr><td>SDE1 (junior)</td><td>80,492</td><td>142,354</td><td>+77.0%</td><td>158,063</td><td>45,849</td><td>29.0%</td></tr>
<tr><td>SDE2 (mid)</td><td>79,065</td><td>114,327</td><td>+44.6%</td><td>278,369</td><td>92,127</td><td>33.1%</td></tr>
<tr><td>SDE3 (senior)</td><td>7,490</td><td>10,828</td><td>+44.6%</td><td>11,351</td><td>3,897</td><td>34.3%</td></tr>
<tr><td><strong>Total</strong></td><td><strong>167,047</strong></td><td><strong>267,509</strong></td><td><strong>+60.1%</strong></td><td><strong>447,783</strong></td><td><strong>141,873</strong></td><td><strong>31.7%</strong></td></tr>
</tbody>
</table>
</div>

<p>The SDE3 row is worth reading carefully: its lines-of-code totals are an order of magnitude
smaller than SDE1 or SDE2's. If this table is indeed the 30-engineer high-adoption group, that
would mean very few senior engineers were among the top adopters — but the paper doesn't say,
and doesn't explain the gap either way. Either way, the 77% figure for junior engineers rests
on a much larger base than the matching 44.6% for seniors.</p>
"""

# ---------------------------------------------------------------------------
sec_trust = """
<p>Acceptance of AI-generated code climbed steadily as the tool matured: from 4.7% in the
first month to 38.0% by the sixth, while a separate "copy rate" — code copied out without
using the direct-accept action — fell from an early spike of 21% to a stable 10–12%.</p>

<figure>
  <img src="../assets/images/deputydev-productivity-study/fig-p08-x480.webp"
       alt="Line chart, March to August 2025, of three percentages: Code Acceptance Rate rising
       from 4.7% to 38.0%, Code Copy Rate falling from 14% (with a spike to 21% in May) to
       10%, and Total Utilization Rate rising from 19% to about 48%."
       width="1400" height="981">
  <figcaption>
    <span class="figlabel">Figure 7</span>Acceptance climbing while copying declines is read by
    the paper as engineers shifting from Chat mode (draft, then copy manually) to Act mode
    (apply directly) as trust in the tool grew — an inference from behavior, not something
    engineers were asked about directly.
    <span class="figsrc">Extracted from page 8 of the source PDF.</span>
  </figcaption>
</figure>

<div class="callout callout--caveat">
  <span class="callout__label">Caveat</span>
  <p>When engineers <em>were</em> asked directly, the answer ran the other way: the July 2025
  survey found 76% of respondents preferred Chat mode over Act mode. The paper never reconciles
  its own inferred behavioral trend with its own directly-surveyed preference — the inference
  is on page 8 (and again on page 5), the survey result on page 11, three pages apart, without
  either one referencing the other.</p>
</div>

<p>The same July survey (228 respondents, 76% response rate, weighted toward backend engineers
at 64% of the sample) found strong but uneven satisfaction between the two halves of the tool.
85% of respondents wanted DeputyDev to keep reviewing their pull requests, against only 62%
who wanted to keep the code-generation assistant — a gap the paper attributes to infrastructure
stability problems with the generation feature, which it says were later fixed, though that
explanation isn't independently verified. Other survey findings: 71% agreed the PR reviews
were genuinely helpful, engineers estimated saving about 20 minutes a day on average, and the
single most-cited value ("identifying issues/bugs in code," 151 mentions) was squarely the
review feature's job, not the generation assistant's. 93% of respondents said they wanted to
keep using DeputyDev, with no feature breakdown given for that particular number. The paper's
conclusion, two pages later, restates the code-generation figure as "57% satisfaction" — but
57% isn't the 62% just described; it's the same survey's answer to a different question
("Perceived plug-in helpfulness | 57% say Yes"), relabelled in the conclusion as if it were
the continuation figure.</p>

<p>A separate Net Promoter Score survey (125 respondents, also July 2025) put DeputyDev at an
NPS of 34 — 44% promoters, 46.4% passives, 9.6% detractors, which checks out arithmetically
(44 − 9.6 = 34.4, closely matching the reported score). The paper reads that as "moderate"
satisfaction: enough goodwill to keep using the tool, not enough to generate active advocates,
with almost no one actively unhappy.</p>
"""

# ---------------------------------------------------------------------------
sec_roi = """
<p>Over the five months the paper has detailed cost data for (April–August 2025), DeputyDev
cost $46,833 total by the paper's own tally, of which 91.5% ($42,938) went to LLM API calls.
Within that, AWS Bedrock — primarily used to serve the Claude Sonnet models — alone accounted
for 81.0% of every dollar spent ($37,935). Infrastructure (compute, database, and an
Elasticache instance) held flat at $979 a month regardless of usage growth, which the paper
reads as evidence the platform can absorb substantially more load without its fixed costs
scaling with it.</p>

<div class="callout callout--note">
  <span class="callout__label">Note</span>
  <p>The cost table's own rows don't quite add up. Every month's LLM-plus-infrastructure
  columns sum to that month's printed total except July: $6,938 + $1,167 + $173 + $979 =
  $9,257, but the table prints $8,257 — a $1,000 shortfall. The same $1,000 is missing from the
  grand total: the printed column totals ($42,938 LLM + $4,895 infrastructure) add to $47,833,
  not the $46,833 the paper reports, and the gap matches July's error exactly. The paper's own
  prose compounds it, claiming "July showed the lowest at $8,257.00" — but April's printed
  total, $5,864, is lower than either the printed or the corrected July figure; April is the
  cheapest month in the paper's own table, not July.</p>
</div>

<p>Costs otherwise moved a lot month to month, and the split between the two features flipped
entirely over the period. In April, review calls cost more than twice what generation calls
did ($1,419 vs. $636); by August that had reversed to roughly ten to one in generation's favor
($7,980 vs. $757), tracking the adoption shift documented above. Against roughly 300
engineers, the paper reports a per-engineer cost of $30–34 a month <em>in August</em>
specifically — not the peak month for total spend, which was May at $12,061 (about $40 per
engineer at the same headcount). The five-month total annualizes to about $112,000 for the
whole org — the paper frames this as 1–2% on top of typical engineering costs, well below the
price of an additional hire or most commercial per-seat licensing.</p>
"""

# ---------------------------------------------------------------------------
sec_lessons = """
<p>The paper's "lessons learned" section reads less like a research finding and more like an
engineering retro, which is itself informative about what a year of real deployment actually
involves. On the technical side: initial response latency of 2–3 seconds was too slow for
interactive use and had to be optimised down to sub-500ms; large codebases routinely exceeded
the model's context window, forcing the team to build context-selection logic rather than
just feeding in more text; and integrating with the existing toolchain took substantially more
engineering effort than anticipated. On the human side: developer trust took time and
consistent good experiences to build, training took more investment than planned, and teams
had to actively adapt their workflows rather than the tool simply slotting into existing ones.</p>

<p>Three things the team tried and abandoned stand out. <strong>Automatic acceptance</strong> —
letting AI suggestions apply themselves without a human sign-off — caused quality problems and
was disabled quickly. A <strong>one-size-fits-all</strong> generic model, without
domain-specific tuning, underperformed on the company's more specialised codebases. And
attempts at <strong>over-automation</strong> — pushing the tool to handle more of the
development process than engineers wanted handed over — met resistance and reportedly reduced
engineers' sense of agency over their own work. What worked, by contrast, was social rather
than technical: a phased rollout, "champion" engineers seeding adoption within their own teams,
and prioritising smooth integration into existing workflows over adding more features.</p>
"""

# ---------------------------------------------------------------------------
sec_why = """
<p>Large-scale, longitudinal evidence about AI coding tools in real production use is
genuinely rare, regardless of who publishes it — most of what circulates is either a
vendor-run RCT (GitHub's own Copilot studies), a customer case study (Anthropic's published
customer stories), or a benchmark score. This paper is not independent of the tool it evaluates
either (see <a href="#limitations">Limitations</a>), but it is a different kind of evidence
from any of those three: a full year, one real organisation, with adoption allowed to vary
naturally rather than being assigned — the kind of dataset that's expensive for anyone but a
company measuring its own tool to produce. The finding that productivity gains track engagement
almost exactly — not just "the tool helps" but "the tool helps in proportion to how much
someone actually uses it" — is the kind of result that a benchmark, which measures the tool in
isolation from any particular team's adoption curve, structurally cannot produce.</p>

<p>It also documents something the field talks about less than raw capability numbers: what it
actually costs, in dollars and in deployment friction, to run an AI coding platform at
enterprise scale for a year. $46,833 over five months and a laundry list of what broke along
the way (latency, context limits, integration effort, developer trust) is a more concrete
picture of "total cost of ownership" than most public discussion of AI coding tools offers.</p>
"""

# ---------------------------------------------------------------------------
sec_limitations = """
<p>The paper names several of its own limitations directly: it's a single-organisation study,
which limits how far the findings generalise; DeputyDev is an in-house system that may not
resemble commercially available tools like Copilot or Cursor; a one-year window may not
capture longer-term adoption dynamics; and Hawthorne effects "may have influenced developer
behaviour," even though — per §4.6 — engineers were not told they were part of a study, which
addresses the Hawthorne effect as a confound but leaves the underlying research-ethics question
of consent unaddressed.</p>

<p>Beyond what the paper states outright, four things are worth weighing independently.
First, this is the tool's own engineering team evaluating a tool they built, using their own
company's data and their own instrumentation — not disclosed as a conflict of interest in
those terms anywhere in the paper, even though the "in-house system" limitation gestures at
something adjacent. Second, the paper's own internal consistency has real gaps, of varying
size: a $1,000 arithmetic error in the cost table that also throws off its own grand total
(see <a href="#roi">What it cost</a>), a conclusion that relabels a different survey question
as the code-generation satisfaction figure (see <a href="#developer-trust">Developer
trust</a>), Figure 1's summary box computing its headline statistic a different way from the
rest of the text without saying so (see <a href="#results">What the results show</a>), and the
"Cohort 1/Cohort 2" labels reused for two different comparisons with different numbers behind
them. Third, and more serious than any of those: the two adoption cohorts that carry the
paper's central causal claim are defined by criteria that contradict themselves. The
high-adoption group is specified as engineers with a "Review interaction rate: &gt;80% of PRs
engaged with AI feedback" — and the low-adoption group, defined by "minimal engagement," is
given the identical bullet, word for word: "Review interaction rate: &gt;80% of PRs engaged
with AI feedback." A group whose entire definition is minimal engagement cannot also be
required to have over 80% engagement with the tool; one of the two definitions is wrong, and
the paper never says which. The same section also states the two cohorts were "matched" on
pre-deployment baseline performance, yet their own baselines (168,676 and 253,332 lines
shipped) differ by 50% — either the matching didn't work as described, or "matched" means
something looser than equal starting points. None of these individually undermines the
underlying data, but together they suggest a paper that moved fast and wasn't checked as
carefully as its statistical apparatus (p-values, Cohen's d, ANCOVA) might suggest at a
glance. Fourth, one of the two adoption-cohort results — the
11.4% productivity decline among low adopters — falls short of conventional statistical
significance (p&nbsp;=&nbsp;0.08), a caveat the paper reports honestly in the numbers but
doesn't carry into the confidence of its surrounding prose.</p>

<p>None of this means the core finding is wrong. The within-subjects before/after comparison,
the adoption-cohort split, and the SDE-level breakdown all point the same direction and are
individually well-powered where it matters most (the headline cycle-time and top-adopter
results are both comfortably significant). But a reader should treat this as one organisation's
carefully-instrumented but self-reported account of its own tool, not as an independently
audited or externally replicated result.</p>
"""

# ---------------------------------------------------------------------------
glossary = """
<dl class="glossary">
<dt>DeputyDev</dt><dd>1mg's in-house AI development platform, combining an automated
pull-request reviewer with a VS Code code-generation extension — the subject of this paper.</dd>
<dt>Pull request (PR)</dt><dd>A proposed set of code changes submitted for review before being
merged into a shared codebase. "Cycle time" and "review time," this paper's core productivity
metrics, are both measured against a PR's lifecycle.</dd>
<dt>Cohort</dt><dd>A group of engineers analysed together because they share some defining
trait — here, either a time period (before/after a launch) or a level of tool usage
(high/low adoption).</dd>
<dt>Quasi-experimental design</dt><dd>A study that compares groups or time periods without
being able to randomly assign who's in which — the fallback when a true randomized controlled
trial isn't feasible, as it wasn't for reshuffling a production engineering org.</dd>
<dt>ANCOVA (Analysis of Covariance)</dt><dd>A statistical technique for comparing groups on an
outcome while adjusting for a measured starting-point difference between them — used here to
control for each engineer's pre-deployment productivity.</dd>
<dt>Cohen's d</dt><dd>A standardised measure of how large a difference between two groups is,
independent of the units being measured. Values above roughly 0.8 are conventionally
considered large; this paper reports 1.42 for its strongest result.</dd>
<dt>p-value</dt><dd>The probability of seeing a result at least this extreme if there were
actually no real effect. Conventionally, p&nbsp;&lt;&nbsp;0.05 is treated as "statistically
significant"; this paper's low-adopter decline, at p&nbsp;=&nbsp;0.08, falls just short of that
bar.</dd>
<dt>Net Promoter Score (NPS)</dt><dd>A survey metric from −100 to 100, computed as the share of
respondents who are enthusiastic "promoters" minus the share who are critical "detractors."</dd>
<dt>Hawthorne effect</dt><dd>The tendency for people to change their behaviour simply because
they know they're being observed, independent of any actual intervention.</dd>
<dt>Vector database</dt><dd>A database that stores content as numerical embeddings and
retrieves entries by semantic similarity rather than exact keyword match — used here (Weaviate)
to let the code-generation tool find relevant code by meaning, not just matching text.</dd>
</dl>
"""

sources = """
<ol class="biblio">
<li id="r1">Kumar, A., Khare, V., Sharma, D., Kumar, S., Saini, V., Yadav, A., Jain, S., Rana,
A., Verma, P., Meena, V., &amp; Edubilli, A. (2025). <em>Intuition to Evidence: Measuring AI's
True Impact on Developer Productivity</em>. arXiv:2509.19708.</li>
<li id="r2">Khare, V., Saini, V., Sharma, D., Kumar, A., Rana, A., &amp; Yadav, A. (2025).
<em>DeputyDev &mdash; AI Powered Developer Assistant: Breaking the Code Review Logjam through
Contextual AI to Boost Developer Productivity</em>. arXiv:2508.09676 &mdash; the same team's
earlier, smaller controlled study of DeputyDev's review feature alone, referenced above.</li>
</ol>
"""

sections = [
    {"id": "the-problem", "title": "The problem", "html": sec_problem},
    {"id": "what-deputydev-is", "title": "What DeputyDev is", "html": sec_system},
    {"id": "how-they-measured-it", "title": "How they measured it", "html": sec_methodology},
    {"id": "adoption", "title": "Adoption", "html": sec_adoption},
    {"id": "results", "title": "What the results show", "html": sec_results},
    {"id": "developer-trust", "title": "Developer trust", "html": sec_trust},
    {"id": "roi", "title": "What it cost", "html": sec_roi},
    {"id": "lessons-learned", "title": "Lessons learned", "html": sec_lessons},
    {"id": "why-it-matters", "title": "Why it matters", "html": sec_why},
    {"id": "limitations", "title": "Limitations", "html": sec_limitations},
    {"id": "glossary", "title": "Glossary", "html": glossary},
    {"id": "sources", "title": "Sources", "html": sources},
]

content = {
    "slug": SLUG,
    "title": "Intuition to Evidence: Measuring AI's True Impact on Developer Productivity",
    "type": "paper",
    "authors": (
        "Anand Kumar, Vishal Khare, Deepak Sharma, Satyam Kumar, Vijay Saini, Anshul Yadav, "
        "Sachendra Jain, Ankit Rana, Pratham Verma, Vaibhav Meena, and Avinash Edubilli"
    ),
    "venue": "arXiv preprint",
    "year": 2025,
    "tags": ["coding-agents", "code-quality", "production", "evaluation"],
    "hook": hook,
    "tldr": tldr,
    "source_url": "https://arxiv.org/abs/2509.19708",
    "sections": sections,
}

if __name__ == "__main__":
    out_path = f"inbox/{SLUG}.content.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")
