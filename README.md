# Open Math Problems Lab

A funnel from mathematics preprints to a short list of open problems worth
attacking — specifically, problems where progress can be demonstrated by
**constructing an explicit example**.

It reads the LaTeX source of every paper in a slice of arXiv, extracts the open
problems stated in them, and judges each one against a hard gate and six
independent axes. The output is a ranked digest of a handful of problems, not a
catalogue of thousands.

## Why

Language models have started settling real combinatorial conjectures by finding
explicit counterexamples. Two of the twenty `math.CO` papers in the first sample
this project looked at involved LLM-found results — including
[arXiv:2607.21508](https://arxiv.org/abs/2607.21508), which refutes conjectures
of Stanley (1995) and Monical (2018) with explicit 12-vertex graphs found in
under 90 minutes.

The bottleneck is no longer the search. It is knowing **which problem to point a
search at**: one with a finite object to look for, a frontier close enough to
reach, and not so heavily worked that the reachable region is already cleared.
That triage is what this repository automates.

## How it works

```
arXiv LaTeX  ──▶  Statement  ──▶  Conjecture  ──▶  Assessment  ──▶  Digest
              extract          dedup           gate + 6 axes
              (Haiku)                          (Opus)
```

**Stage 1 — extraction.** Reads the full source of every paper; no keyword
prefilter. On a measured sample only 25% of papers put their open problems in a
`conjecture` environment, and the best problems are routinely prose buried in a
`remark` ([ADR-0004](docs/adr/0004-no-keyword-prefilter-before-extraction.md)).
Each Statement records the problem verbatim with its provenance, plus who the
paper credits it to — read from the paper's own citation text, never inferred.

**Stage 2 — assessment.** Every Conjecture faces one binary Gate: *is there a
finite object whose construction would be genuine progress?* Whatever passes is
scored on six independent axes — Frontier, Machinery Depth, Quantifier Form,
Prior Computation, Attention, Venue — which are deliberately **never combined
into a score**
([ADR-0005](docs/adr/0005-hard-gate-and-independent-axes-with-no-score.md)).

Frontier is the decisive axis and the one a model is least able to judge
honestly, so every frontier claim must quote the paper or be recorded as
`unknown`. An unknown frontier is useful; an invented one sends someone to
search a region cleared a decade ago.

## Does it work?

Two conjectures refuted in July 2026 by explicit counterexamples serve as
calibration cases. Reconstructed as they stood *before* their refutation, the
rubric gates both correctly, quotes the real `n >= 12` bound for Monical's, and
reports `unknown` for Stanley's rather than confabulating one.

It has a known weakness: its prose over-weights prior human attention when
arguing against a problem. On all four judgments with a known answer, the stated
reason to walk away was some form of *"strong people already looked"* — and it
was wrong every time. Both conjectures had stood for decades against exactly
that roster of names.
[ADR-0008](docs/adr/0008-attention-requires-evidence-not-reputation.md) records
the fix and is candid that it was tuned on the same cases that validate it.

## Getting started

```sh
python3 -m venv .venv
.venv/bin/pip install anthropic pyyaml

# the rubric, against two conjectures whose real outcome we know
.venv/bin/python scripts/try_assess.py judgment/backtest/*.json

# extraction on the newest papers in a category
.venv/bin/python scripts/try_extract.py --recent 5 --category math.CO --show
```

No Anthropic developer-platform account is needed — the scripts run through the
authenticated Claude Code CLI by default. See
[useful_commands.md](useful_commands.md) for the full command reference,
backends, and troubleshooting.

## Layout

| Path | |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | The ubiquitous language. **Read this first.** |
| [`docs/adr/`](docs/adr/) | Why the design is the way it is |
| `prompts/` | The extraction and assessment prompts, and their schemas |
| `judgment/` | Verdicts, the calibration set, backtest fixtures |
| `schema/schema.sql` | Database shape |
| `scripts/` | Development harnesses — not the pipeline |
| `cache/` | Papers and results (gitignored) |

`prompts/` and `judgment/` are hand-authored source and are version controlled.
The database and everything under `cache/` are build artifacts, rebuildable for
a few dollars, and are not
([ADR-0006](docs/adr/0006-sqlite-is-a-build-artifact-judgment-is-source.md)).

## Status

Early. The domain model, both prompts, and the schema exist and are validated by
hand against real papers — extraction scores 5/5 recall with no false positives
on its ground-truth paper, and the rubric passes its backtest 2/2. The pipeline
that runs a whole month, deduplicates, populates the database, and emits the
digest is not built yet.
