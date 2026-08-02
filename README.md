# Open Math Problems Lab

A funnel from mathematics preprints to a short list of open problems worth
attacking — specifically, problems where progress can be shown by **constructing
an explicit example**.

It reads the LaTeX source of papers from arXiv, pulls out the open problems
stated in them, and judges each one on whether there's a concrete finite object
someone could go looking for. The output is a handful of problems with a written
case for each, not a catalogue of thousands.

## Why this exists

Language models have started settling real combinatorial conjectures by finding
explicit counterexamples. Two of the first twenty `math.CO` papers this project
sampled involved LLM-found results — including
[arXiv:2607.21508](https://arxiv.org/abs/2607.21508), which refutes conjectures
of Stanley (1995) and Monical (2018) using explicit 12-vertex graphs found in
under 90 minutes.

So the hard part is no longer the search. It's knowing **which problem to point a
search at**: one with a finite object to look for, a frontier close enough to
reach, and not so heavily worked that the reachable ground is already covered.
That triage is what this repo automates.

---

## Onboarding

### 1. Setup (1 minute)

```sh
python3 -m venv .venv
.venv/bin/pip install anthropic pyyaml
```

That's all. **No Anthropic developer-platform account is needed** — the scripts
run through the authenticated Claude Code CLI by default. If you have a platform
API key, add `--backend api` for cheaper runs with stricter output validation.

### 2. Look at real output — free, instant

The repo ships a small curated set of real pipeline output in
[`examples/`](examples/), so you can see what the system produces before
generating anything:

```sh
.venv/bin/python scripts/statements.py --open      # open problems it found
.venv/bin/python scripts/rank.py --why             # assessed problems, ranked
```

Neither calls a model. Both read `cache/` if you have one and fall back to
`examples/` otherwise, so this works on a fresh clone. Seven files covering a
rich paper, a paper with no open problems at all, a survey, a Gate pass, a Gate
rejection, and both calibration cases — see [`examples/README.md`](examples/README.md)
for what each demonstrates.

### 3. Prove it still works — ~$0.30, 4 minutes

Two tests where the correct answer is already known, so you can grade the output:

```sh
# the rubric, on two conjectures refuted in July 2026 -- reconstructed as they
# stood BEFORE their refutation. Must print "2 matched, 0 mismatched".
.venv/bin/python scripts/try_assess.py judgment/backtest/*.json

# extraction, on a paper whose ground truth was derived by hand.
# Must give 5 statements (3 open) on the first, and 0 on the second.
.venv/bin/python scripts/try_extract.py 2607.21508v1 2607.21222v1 --show
```

Both use cached papers, so no network calls to arXiv.

### 4. Then read, in this order

1. **[`CONTEXT.md`](CONTEXT.md)** — the vocabulary. Everything else assumes it.
   *Statement* vs *Conjecture*, *Gate*, *Finite Witness*, the six *Axes*.
2. **[`docs/reading-an-assessment.md`](docs/reading-an-assessment.md)** — how to
   read the output, and which fields deserve less trust than they look like they
   do.
3. **[`docs/end-to-end-walkthrough.md`](docs/end-to-end-walkthrough.md)** — the
   full guided run, ordered so known-answer tests come before unknowns.
4. **[`docs/adr/`](docs/adr/)** — nine short records of *why* the design is the
   way it is. Read these before changing anything structural; several document
   approaches that look obvious and were measured to be wrong.

---

## How it works

```
arXiv LaTeX ──▶ Statement ──▶ [screen] ──▶ Assessment ──▶ ranked list
              extract        gate only    gate + 6 axes
              (Haiku)        (Haiku)      (Opus)
                             optional
```

The screen is **optional**. Gate logic lives in `assess.md`, so `extract → assess`
produces identical verdicts — the screen just answers the yes/no part on a model
20x cheaper first, so the expensive six-axis pass runs on survivors only. On the
sample measured it only ever *leaks* (passes things Opus later rejects), never
drops something Opus would have kept, so it costs no recall.

**Stage 1 — extraction.** Reads the full source of every paper, with no keyword
prefilter. That's deliberate: on a measured sample only 25% of papers put their
open problems in a `conjecture` environment, and the most attackable ones are
routinely prose buried inside a `remark`
([ADR-0004](docs/adr/0004-no-keyword-prefilter-before-extraction.md)). Each
Statement records the problem verbatim, where it sat, and who the paper credits
it to — read from the paper's own citation text, never guessed.

**Stage 2 — assessment.** Each problem faces one binary **Gate**: *is there a
finite object whose construction would be genuine progress?* Whatever passes is
rated on six independent axes — Frontier, Machinery Depth, Quantifier Form,
Prior Computation, Attention, Venue — which are deliberately **never combined
into a single score**
([ADR-0005](docs/adr/0005-hard-gate-and-independent-axes-with-no-score.md)).

Frontier is the most decisive axis and the one a model is least able to judge
honestly, so every frontier claim must **quote the paper** or be recorded as
`unknown`. An unknown frontier is useful information; an invented one sends
someone to search ground that was cleared a decade ago.

## The scripts

| Script | Does | Model? | Cost |
|---|---|---|---|
| `scripts/try_extract.py` | Stage 1. Papers → problems | Haiku | ~$0.07/paper |
| `scripts/screen.py` | Optional. Cheap gate-only pre-filter | Haiku | ~$0.005/problem |
| `scripts/try_assess.py` | Stage 2. Problems → gate + axes | Opus | ~$0.10/problem |
| `scripts/statements.py` | Browse/filter every extracted problem | no | free |
| `scripts/rank.py` | Order assessed problems by readiness | no | free |

They chain through files in `cache/`, so each can run independently:

```sh
.venv/bin/python scripts/try_extract.py --recent 5 --category math.CO
.venv/bin/python scripts/try_assess.py --from-extraction cache/extractions/*.json
.venv/bin/python scripts/rank.py --why
```

At scale, put the screen in between — same results, roughly a third off:

```sh
.venv/bin/python scripts/try_extract.py --harvest 2026-07-20:2026-07-24 --extract-all
.venv/bin/python scripts/screen.py --all                    # ~$0.005 each
.venv/bin/python scripts/try_assess.py --screened --max-cost 20
.venv/bin/python scripts/rank.py --why
```

Every long-running command is **resumable** (re-run to continue), **capped**
(`--max-cost`), and **single-instance** (a second concurrent run is refused,
because the cap is per process and would silently double).

⚠️ That middle command assesses **every** open problem found — check the count
with `scripts/statements.py --open` first, at ~$0.10 each.

For bulk work there's `--harvest 2026-06-01:2026-06-30`, which lists a whole
date range before extracting anything. Full reference:
[`useful_commands.md`](useful_commands.md).

---

## What's trustworthy, and what isn't

Read this before relying on any output.

### Validated

- **Extraction recall.** 5/5 against a hand-derived ground truth, 0 false
  positives, and 0 statements on a control paper that name-drops a famous
  conjecture without ever stating it.
- **The Gate.** Passes 6 of 9 on a real survey paper. All three rejections were
  problems asking to prove an *asymptotic* bound, where no finite object can
  settle anything. It discriminates on real mathematical structure.
- **Frontier honesty.** This was the failure mode we most feared: a model
  inventing a plausible bound like "verified to n = 10" and sending someone to
  search cleared ground. Given a context with no numeric range, it instead
  reports the *structural* boundary the paper does state and notes explicitly
  that "no vertex-count verification range appears anywhere in the supplied
  text". It declines to make a number up.
- **The Attention rule** ([ADR-0008](docs/adr/0008-attention-requires-evidence-not-reputation.md)).
  Written after the rubric was wrong four times in a row in the pessimistic
  direction, then confirmed on nine problems it had never seen.

### Not validated

- **The ranking is weak, and we measured it.** Across 8 candidates,
  `machinery_depth` decides 14 of 28 pairwise comparisons while
  `quantifier_form` and `attention` decide 1 each. It is effectively a one-axis
  ranker — and that axis is the *least* evidence-backed one, since unlike
  Frontier it never has to quote anything.
- **A likely missing axis.** 4 of 8 arguments named *cost of checking a single
  candidate* as the biggest risk — *"the Schur expansion of a degree-12 CSF is
  not cheap"*, *"computing $X_G$ is #P-hard"*. That isn't an axis, so the most
  frequently cited obstacle is invisible to the ranking.
- **Nothing has been attacked.** No human has tried to solve a problem this
  system recommended. So there is **no evidence about how often it's right** —
  only that it describes problems coherently. Treat the ranking as a reading
  order, not a prediction.
- **The calibration set is mostly stubs.** 8 of 10 cases are `verified: false`
  placeholders, and per
  [ADR-0007](docs/adr/0007-human-assessment-is-an-affordance-and-scope-ends-at-one-pilot-attack.md)
  that file carries the entire calibration load.

---

## Layout

| Path | |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | The vocabulary. Read first. |
| `prompts/` | The two prompts and their output schemas — **the actual product** |
| `judgment/` | Hand-authored: verdicts, calibration set, backtest fixtures |
| `scripts/` | Development harnesses. Not a pipeline yet |
| `schema/schema.sql` | Database shape (nothing populates it yet) |
| `docs/`, `docs/adr/` | Guides and design decisions |
| `tests/` | `test_json_repair.py` — run it after touching the backends |
| `cache/` | Papers, extractions, assessments (gitignored) |

`prompts/` and `judgment/` are hand-written source and version controlled.
Anything under `cache/`, and any database, is a build artifact — rebuildable for
a few dollars, and deliberately not committed
([ADR-0006](docs/adr/0006-sqlite-is-a-build-artifact-judgment-is-source.md)).

The most important files in the repo are `prompts/extract.md` and
`prompts/assess.md`. The scripts are scaffolding around them; the prompts are
where the behaviour lives, and where changes should usually go.

## Where to take it next

In rough order of value:

1. **Attack one problem.** Nothing else validates the premise. `rank.py`'s top
   entries are specified well enough to start on. Record the outcome in
   `judgment/calibration.yaml` — an attack that isn't written down evaporates.
2. **Verify the calibration stubs** — 8 of the 10 cases are unchecked placeholders,
   so the file that carries all the calibration load carries almost nothing.
3. **Add a verification-cost axis**, which the evidence above already justifies.
4. **Build the real pipeline** — dedup, database load, digest generation.
   Deliberately last: the prompts were the risk and they're now tested.

Note the ordering. Step 1 is a human sitting down with a maths problem for two
days, and it gates everything else — until it happens, we know the system
describes problems well and nothing about whether it picks good ones.
