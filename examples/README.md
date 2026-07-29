# Example output

A small hand-picked set of real pipeline output, committed so a fresh clone shows
something before you spend anything. `scripts/statements.py` and
`scripts/rank.py` read `cache/` when it exists and fall back to this directory
when it doesn't.

## Why this is tracked when `cache/` isn't

[ADR-0006](../docs/adr/0006-sqlite-is-a-build-artifact-judgment-is-source.md)
splits files by whether they are **regenerable**: machine output is a build
artifact and stays out of git, hand-authored judgment is source and goes in.

`cache/` is machine output. It is overwritten on every run, grows without bound,
and would dirty the working tree constantly if tracked.

This directory is different: a human *chose* these seven files for what they
demonstrate. The curation is the hand-authored part, which makes it source. It is
frozen — regenerating the cache does not touch it.

## What each file shows

### Extractions

| File | Why it's here |
|---|---|
| `2607.21508v1.json` | The ground-truth paper. 5 statements: two conjectures this paper *refutes* (`resolved_here`) plus three open problems stated as prose inside `remark` blocks — the case a keyword filter would miss entirely. `key_results` carries the 12-vertex counts that stage 2 needs. |
| `2607.21222v1.json` | The negative control. **Zero statements.** It name-drops Hadwiger's conjecture in its title keywords and abstract without ever stating it, so there is nothing to extract. Correct output here is an empty list. |
| `2607.26049.json` | A survey paper. 11 statements, 5 credited to famous names (Erdős and others), 3 the authors' own. Surveys are the densest source of open problems in the corpus. |

### Assessments

| File | Why it's here |
|---|---|
| `monical-snp.json` | Backtest. Gate `PASS`, frontier `known`, quoting the real `n >= 12` bound from prior work — the axis working as designed. |
| `stanley-claw-free.json` | Backtest. Gate `PASS`, frontier `known` but **structural** rather than numeric, with an explicit note that no vertex-count range appears in the context. The model declining to invent a number is the behaviour under test. |
| `2607.21508v1_3.json` | Gate `PASS` on a live problem, and the current top of the ranking. |
| `2607.26049_4.json` | Gate **`FAIL`**. Asks to prove an asymptotic `O(n)` bound, where no finite object settles anything. Shows the Gate rejecting correctly. |

Both backtest cases are conjectures **already refuted** — they are graded test
inputs, not candidates. `rank.py` excludes them from the ranking by name.

## Refreshing these

They should be regenerated when a prompt changes enough that the old output is
misleading. Check `_meta.prompt_sha256` in each file against the current prompt:

```sh
.venv/bin/python -c "
import json, pathlib, hashlib
cur = hashlib.sha256(pathlib.Path('prompts/extract.md').read_bytes()).hexdigest()[:12]
print('current extract prompt:', cur)
for p in sorted(pathlib.Path('examples/extractions').glob('*.json')):
    got = json.loads(p.read_text())['_meta']['prompt_sha256']
    print(f'  {p.stem:<16} {got}', '' if got == cur else '<-- stale')"
```

To refresh: re-run the pipeline on those ids, then copy from `cache/` back over
these. Keep the same set unless you have a better teaching example — the value is
in the coverage (rich paper, empty paper, survey, gate pass, gate fail, both
backtests), not in being current.
