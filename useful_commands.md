# Useful commands

All commands assume the repo root as the working directory. Costs and timings
below are measured, not estimated.

For a guided validation run in the right order, see
[docs/end-to-end-walkthrough.md](docs/end-to-end-walkthrough.md). This file is
the command reference.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install anthropic pyyaml
```

Nothing else is required. The scripts default to the **`claude-cli` backend**,
which runs through the authenticated Claude Code CLI and needs no Anthropic
developer-platform account. See [Backends](#backends) if you get platform
access later.

---

## Stage 2 — the rubric

### Run the backtest

The two conjectures whose real outcome we know, reconstructed as they stood
before July 2026. This is the regression test for the rubric.

```sh
.venv/bin/python scripts/try_assess.py judgment/backtest/*.json
```

Compares each Gate verdict against `judgment/calibration.yaml` and prints
`✓ MATCHES` / `✗ MISMATCH`. **Measured: ~$0.19, about 2 minutes, on Opus 5.**

For how to interpret what comes back — the reading order, which fields to
distrust, and the known failure modes — see
[docs/reading-an-assessment.md](docs/reading-an-assessment.md).

Re-run this after any edit to `prompts/assess.md`.

### Assess whatever stage 1 found

```sh
.venv/bin/python scripts/try_assess.py --from-extraction cache/extractions/2607.21508v1.json
```

Assesses every statement whose `stated_as` is `open`, skipping the ones a paper
already resolved. This is the funnel end to end.

### Assess one hand-written problem

Any JSON file with `claim`, `verbatim`, `context`, `attribution`, `paper_meta`
works — copy a file in `judgment/backtest/` as a template.

```sh
.venv/bin/python scripts/try_assess.py my-problem.json
```

---

## Stage 1 — extraction

### Newest papers in a category

```sh
.venv/bin/python scripts/try_extract.py --recent 5 --category math.CO --show
```

`--show` prints each statement's plain-English `claim`. Drop it for one line per
statement. **Measured: ~$0.07 and 15–80s per paper, on Haiku 4.5.**

The four target categories are `math.CO`, `math.AC`, `math.RT`, `math.GR`.

### Bulk-harvest a date range

```sh
# list what's there (no inference, no cost)
.venv/bin/python scripts/try_extract.py --harvest 2026-06-01:2026-06-30

# ...and actually extract all of it
.venv/bin/python scripts/try_extract.py --harvest 2026-06-01:2026-06-30 --extract-all
```

Uses OAI-PMH, which handles date ranges properly and is not throttled the way
the query API is ([ADR-0009](docs/adr/0009-avoid-the-arxiv-query-api.md)).
Defaults to the four target categories; override with
`--categories math.CO,math.AC`. Always run it without `--extract-all` first to
see the paper count before committing to the inference.

### Specific papers

```sh
.venv/bin/python scripts/try_extract.py 2607.21508v1 2607.21222v1 --show
```

Sources cache under `cache/src/`, so re-running these two is free of arXiv
traffic. `2607.21508v1` is the ground-truth paper (5 statements expected) and
`2607.21222v1` is the negative control (0 statements expected) — a quick
regression check after editing `prompts/extract.md`.

### Browse everything extracted so far

```sh
.venv/bin/python scripts/statements.py                    # all statements
.venv/bin/python scripts/statements.py --open             # only what's still open
.venv/bin/python scripts/statements.py --open --full      # with verbatim + context
.venv/bin/python scripts/statements.py --paper 2607.26049 # one paper
.venv/bin/python scripts/statements.py --attributed       # credited to someone else
.venv/bin/python scripts/statements.py --stale            # older prompt version
.venv/bin/python scripts/statements.py --open --json      # for piping
```

Calls no model — reads `cache/extractions/` only. Prints a per-status and
per-attribution breakdown, and warns when any paper was extracted by a prompt
version other than the current one.

### Inspect a full record

```sh
.venv/bin/python -m json.tool cache/extractions/2607.21508v1.json | less
```

The terminal summary omits `context`, `notes`, and `_meta` — read the JSON when
you are checking extraction quality rather than just counting statements.

---

## Backends

| Flag | Needs | Schema | Notes |
|---|---|---|---|
| `--backend claude-cli` *(default)* | Claude Code login | Prompt-and-parse | Works on a normal Claude seat |
| `--backend api` | `ANTHROPIC_API_KEY` or `ant auth login` | **Enforced** | Cheaper; use once platform access exists |

Model overrides work on both scripts:

```sh
.venv/bin/python scripts/try_assess.py judgment/backtest/*.json --model sonnet
.venv/bin/python scripts/try_extract.py 2607.21508v1 --model sonnet
```

CLI backend takes aliases (`haiku`, `sonnet`, `opus`); the API backend takes
full ids (`claude-haiku-4-5`, `claude-opus-5`).

Comparing Opus against Sonnet on the backtest is a cheap way to find out whether
the rubric needs the expensive model.

---

## Checks that need no inference

```sh
# schema applies cleanly
rm -f /tmp/omp.sqlite && sqlite3 /tmp/omp.sqlite < schema/schema.sql \
  && sqlite3 /tmp/omp.sqlite ".tables"

# prompts and fixtures parse
.venv/bin/python -c "
import json, pathlib, yaml
json.loads(pathlib.Path('prompts/extract.schema.json').read_text())
json.loads(pathlib.Path('prompts/assess.schema.json').read_text())
yaml.safe_load(pathlib.Path('judgment/calibration.yaml').read_text())
yaml.safe_load(pathlib.Path('judgment/verdicts.yaml').read_text())
[json.loads(p.read_text()) for p in pathlib.Path('judgment/backtest').glob('*.json')]
print('all parse')"
```

---

## Troubleshooting

**`HTTP Error 429` from arXiv.** Almost certainly not your fault, and waiting
may not help. `export.arxiv.org/api/query` is chronically congested — it has
been observed returning 429 for over an hour, taking 46 seconds per rejection.
We no longer use it: `--recent` reads the HTML listing page and `--harvest` uses
OAI-PMH, neither of which was affected during that outage
([ADR-0009](docs/adr/0009-avoid-the-arxiv-query-api.md)).

If you still see 429s, check which host is failing:

```sh
curl -s -o /dev/null -w "query-api  %{http_code} in %{time_total}s\n" \
  "https://export.arxiv.org/api/query?search_query=cat:math.CO&max_results=1"
curl -s -o /dev/null -w "listing    %{http_code} in %{time_total}s\n" \
  "https://arxiv.org/list/math.CO/recent"
curl -s -o /dev/null -w "oai-pmh    %{http_code} in %{time_total}s\n" \
  "https://export.arxiv.org/oai2?verb=Identify"
```

A slow 429 means congestion, not a penalty. Cached papers always work: pass
explicit IDs (`ls cache/src/`) instead of `--recent`.

**`claude exited 1`.** Check `claude -p "hi"` works on its own. The scripts pass
`--tools` with no arguments and `--exclude-dynamic-system-prompt-sections` to
strip the Claude Code harness from each invocation — this takes per-call
overhead from ~24,600 tokens to ~590, so do not remove those flags to "simplify".

**JSON parse errors from a backend run.** The `claude-cli` backend has no schema
enforcement, so a model can return prose or fenced JSON. Fences are stripped
automatically; anything worse means the prompt needs tightening, or switch to
`--backend api` where the schema is enforced by the API.

**Cache is stale after editing a prompt.** Results in `cache/extractions/` and
`cache/assessments/` are overwritten per run, but nothing invalidates them
automatically. `rm -rf cache/extractions` to force a clean re-run. Leave
`cache/src/` alone — those are the papers, and re-downloading is what gets you
rate-limited.

---

## Layout

```
CONTEXT.md               ubiquitous language — read this first
docs/adr/                why the design is the way it is
prompts/                 SOURCE: extract.md, assess.md + their schemas
judgment/                SOURCE: verdicts, calibration set, backtest fixtures
schema/schema.sql        the database shape
scripts/                 dev harnesses, not the pipeline
cache/                   gitignored: papers, extractions, assessments
```

`prompts/` and `judgment/` are hand-authored source and are version controlled.
`cache/` and any database are build artifacts and are not — see
[ADR-0006](docs/adr/0006-sqlite-is-a-build-artifact-judgment-is-source.md).
