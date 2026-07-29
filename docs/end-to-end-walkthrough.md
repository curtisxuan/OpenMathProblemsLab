# End-to-end walkthrough

Run these in order. The ordering is deliberate: **every step whose correct answer
is already known comes before any step whose isn't.** If the rubric has silently
broken, you want to discover that on a conjecture whose fate you know, for 20
cents, before spending real money on fresh papers whose output you cannot grade.

Total: about 12 minutes and under $1.50.

| Step | What | Cost | Answer known? |
|---|---|---|---|
| 0 | Sanity checks | free | yes |
| 1 | Rubric backtest | ~$0.20 | **yes** |
| 2 | Extraction regression | ~$0.10 | **yes** |
| 3 | Extraction on fresh papers | ~$0.45 | no |
| 4 | The funnel end to end | ~$0.30 | no |
| 5 | Corpus scale | free | n/a |

---

## Step 0 — Sanity, no inference

```sh
cd ~/workspace/OpenMathProblemsLab

# schema applies cleanly
rm -f /tmp/omp.sqlite && sqlite3 /tmp/omp.sqlite < schema/schema.sql \
  && sqlite3 /tmp/omp.sqlite ".tables"

# prompts, schemas, fixtures all parse
.venv/bin/python -c "
import json, pathlib, yaml
json.loads(pathlib.Path('prompts/extract.schema.json').read_text())
json.loads(pathlib.Path('prompts/assess.schema.json').read_text())
yaml.safe_load(pathlib.Path('judgment/calibration.yaml').read_text())
[json.loads(p.read_text()) for p in pathlib.Path('judgment/backtest').glob('*.json')]
print('all parse')"

# the JSON-repair regression test
.venv/bin/python tests/test_json_repair.py
```

**Expect:** 7 tables; `all parse`; `all passed` across 8 escape cases.

**If it fails:** stop. Everything downstream depends on these.

---

## Step 1 — Rubric backtest *(the important one)*

```sh
.venv/bin/python scripts/try_assess.py judgment/backtest/*.json
```

Two conjectures that were refuted in July 2026 by explicit 12-vertex
counterexamples, reconstructed as they stood *beforehand*. The rubric is being
graded against reality.

**Expect** (~2 min, ~$0.20):

```
backtest: 2 matched, 0 mismatched
```

**Check four things, in this order:**

1. **Both Gates `PASS`.** A single finite graph settled each one. A `FAIL` here
   means the rubric is broken at its central job.
2. **`monical-snp` frontier is `known`**, quoting *"one needs to consider graphs
   with $n \geq 12$ vertices"*. That bound is in the supplied context and is
   exactly where the real search succeeded. `unknown` means the Frontier axis
   stopped reading.
3. **`stanley-claw-free` frontier is `unknown` or structural.** Its context
   contains no numeric bound. If it reports a specific verified range like
   *"checked to $n = 10$"*, **the anti-confabulation rule has broken** — that is
   the single most damaging failure mode in the system, because an invented
   frontier sends you to search cleared ground.
4. **Read each argument's last sentence.** It should name a *concrete* obstacle —
   verification cost, search-space size, a structural obstruction. If it says
   some version of *"strong people have surely already tried this"* without
   naming an attempt, ADR-0008's fix has regressed. That reasoning was wrong on
   all four cases we can verify.

---

## Step 2 — Extraction regression

```sh
.venv/bin/python scripts/try_extract.py 2607.21508v1 2607.21222v1 --show
```

Both cached, so no arXiv traffic. Ground truth was derived by hand.

**Expect** (~90s, ~$0.10):

- `2607.21508v1` → **5 statements, 3 open.** Two `resolved_here` (Stanley,
  Monical — this paper refutes both) and three `open` prose problems from
  `remark` environments.
- `2607.21222v1` → **0 statements.** It name-drops Hadwiger's conjecture in its
  title keywords and abstract without ever stating it. Anything above zero here
  is over-extraction.

Then confirm `key_results` picked up the numbers the Frontier axis depends on:

```sh
.venv/bin/python -c "
import json,pathlib
d=json.loads(pathlib.Path('cache/extractions/2607.21508v1.json').read_text())
[print(' -',r) for r in d['key_results']]"
```

**Expect** three lines mentioning **12 vertices** and the coefficients $-64$ and
$-40$. If these go missing, Step 4's frontiers will silently degrade to
`unknown`.

---

## Step 3 — Fresh papers *(answer not known)*

```sh
.venv/bin/python scripts/try_extract.py --recent 5 --category math.CO --show
```

**Expect** (~4 min, ~$0.45): a mix. Some papers legitimately state no open
problems; others yield several. `0 statements` is a normal and correct outcome.

**Grade it by hand — this is the only way to measure recall.** Pick the paper
with the most interesting-looking output and read the source yourself:

```sh
ls cache/tex/ 2>/dev/null || mkdir -p cache/tex
.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts'); import try_extract as t, pathlib
aid='PUT_AN_ID_HERE'
tex,_=t.read_tex(t.ensure_source(aid))
pathlib.Path(f'cache/tex/{aid}.tex').write_text(tex); print(len(tex),'chars')"
```

Then open that `.tex`, jump to any **Concluding Remarks / Open Problems /
Further Questions** section and every `\begin{remark}`, and ask: did the
extractor get everything stated there? Misses concentrate in prose, not in
`conjecture` environments.

**Also watch for:** an `!! JSONDecodeError` line. That should no longer happen —
it was a 20% failure rate before the escape repair. One appearing means a new
malformation shape.

---

## Step 4 — The funnel, end to end

Pick a paper from Step 3 that produced `open` statements:

```sh
.venv/bin/python scripts/try_assess.py --from-extraction cache/extractions/<ID>.json
```

Assesses every `open` statement and skips whatever a paper already resolved.
~$0.10 per problem on Opus.

**This is the product.** Read the output using
[reading-an-assessment.md](reading-an-assessment.md) — the short version being:
Gate, then `frontier_status`, then the quote itself, then the argument's last
sentence.

**Health signals rather than pass/fail:**

- **Some Gates should FAIL.** If everything passes, the Gate is too permissive and
  it is the only filter in the system. Asking to "characterise" or "develop a
  theory of" something should fail; asking to "construct an infinite family"
  should fail unless one new member counts as progress.
- **`attention: fresh`** on an author's own closing remark. `some`/`heavy` there
  means the axis is reading the paper's literature review instead of the
  problem's provenance.
- **`finite_witness` and `claim` describe the same problem.** A mismatch means
  context starvation — it happened when a remark referenced another conjecture by
  name and the rubric lacked its statement.
- **Verify one `frontier_quote` against the paper.** Quotes now arrive via
  stage-1 `key_results`, so the chain is paper → Haiku → quote. It reads like a
  citation but carries an extra hop of trust.

---

## Step 5 — Corpus scale, free

```sh
# one week, all four target categories, listing only
.venv/bin/python scripts/try_extract.py --harvest 2026-07-06:2026-07-10
```

No inference — prints counts and titles, then stops. Add `--extract-all` only
when you mean it.

**Expect** a few hundred papers. Scale from there: a full month is ~930 papers,
which is **~$85** through the Claude Code CLI backend against your usage quota,
versus **~$12** on the Batch API with real schema enforcement.

**Skim the titles.** Ones like *"A counterexample for the polar conjecture
of…"*, *"Dittert's conjecture in dimension 16"*, or *"New lower bounds for
binary constant-weight codes: $A(23,6,10) \geq 297$"* are the target shape —
explicit objects, explicit bounds. Their density in the titles is a free
estimate of how much the funnel has to work with.

---

## Where to point the next iteration

Whatever you find, these are the known-weak spots:

| Symptom | Likely cause | Where to look |
|---|---|---|
| Everything passes the Gate | Gate too permissive; it is the only filter | `prompts/assess.md` § The Gate |
| Frontiers mostly `unknown` | `key_results` not capturing bounds | `prompts/extract.md` § key_results |
| Arguments all sound alike | Rubric hedging on thin context | check what `build_related` supplied |
| Recall misses in prose | Inclusion rules too environment-centric | `prompts/extract.md` § What counts |
| A confabulated frontier | Worst failure mode | `prompts/assess.md` § Frontier |

Two gaps that are known and not yet addressed: **six of eight calibration cases
are still `verified: false`** stubs, and they carry the entire calibration load
(ADR-0007); and **no Pilot Attack has been run**, so nothing yet confirms the
rubric points at genuinely tractable problems rather than merely well-formed
ones.
