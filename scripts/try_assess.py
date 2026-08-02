#!/usr/bin/env python3
"""Run the stage-2 rubric over one or more problems and print the axes.

    # backtest: two conjectures whose real outcome we know
    scripts/try_assess.py judgment/backtest/*.json

    # anything stage 1 extracted
    scripts/try_assess.py --from-extraction cache/extractions/2607.21508v1.json

Input files are JSON with: claim, verbatim, context, attribution, paper_meta.
Results land in cache/assessments/.

When a file carries a `calibration_slug`, the matching entry in
judgment/calibration.yaml is looked up and the rubric's Gate verdict is scored
against the known outcome -- that is the whole point of the backtest.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "assess.md"
SCHEMA = ROOT / "prompts" / "assess.schema.json"
CALIBRATION = ROOT / "judgment" / "calibration.yaml"
OUT = ROOT / "cache" / "assessments"

CLI_SYSTEM_PROMPT = (
    "You assess open mathematical problems against a fixed rubric. "
    "Reply with a single JSON object and nothing else."
)

GREEN, RED, DIM, BOLD, OFF = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def load_calibration() -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    if not CALIBRATION.exists():
        return {}
    doc = yaml.safe_load(CALIBRATION.read_text()) or {}
    return {c["slug"]: c for c in doc.get("cases", []) if c.get("verified")}


def paper_abstract(arxiv_id: str) -> str:
    """Pull the abstract out of the cached LaTeX, if we have the source."""
    src = ROOT / "cache" / "src" / f"{arxiv_id.replace('/', '_')}.tar.gz"
    if not src.exists():
        return ""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from try_extract import read_tex  # local dev helper, same directory

    tex, _ = read_tex(src)
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def build_related(doc: dict, this_index: int) -> str:
    """Abstract plus every OTHER problem in the same paper.

    Without this, a remark referring to another conjecture by name is
    unassessable -- the rubric confidently assesses the wrong problem.
    """
    meta = doc.get("_meta", {})
    parts = []
    abstract = paper_abstract(meta.get("arxiv_id", ""))
    if abstract:
        parts.append(f"**Abstract.** {abstract}")
    if doc.get("key_results"):
        parts.append("**Concrete results this paper establishes.**\n"
                     + "\n".join(f"- {r}" for r in doc["key_results"]))
    siblings = []
    for i, s in enumerate(doc["statements"], 1):
        if i == this_index:
            continue
        siblings.append(
            f"- [{s['stated_as']}] at {s['location']}"
            + (f", attributed to {s['attributed_to']}" if s["attributed_to"] else "")
            + f"\n  claim: {s['claim']}\n  as stated: {' '.join(s['verbatim'].split())}"
        )
    if siblings:
        parts.append("**Other problems extracted from this paper.**\n" + "\n".join(siblings))
    return "\n\n".join(parts) if parts else "(nothing else extracted from this paper)"


SCREEN = ROOT / "cache" / "screen"
EXTRACTIONS = ROOT / "cache" / "extractions"


def screened_problems() -> list[tuple[str, dict]]:
    """Every open statement that PASSED the cheap gate screen.

    The screen answers only the Gate question on Haiku; this reads its verdicts
    and rebuilds the full problem record for the survivors, so the expensive
    six-axis assessment never runs on something already ruled out.
    """
    passes = set()
    for f in SCREEN.glob("*.json"):
        if f.name.startswith("."):
            continue
        try:
            d = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
        if d.get("gate_pass"):
            passes.add(f.stem)

    out = []
    for path in sorted(EXTRACTIONS.glob("*.json")):
        doc = json.loads(path.read_text())
        meta = doc.get("_meta", {})
        for i, st in enumerate(doc.get("statements", []), 1):
            if st["stated_as"] != "open":
                continue
            ref = f"{meta.get('arxiv_id','?')}_{i}"
            if ref not in passes:
                continue
            out.append((ref, {
                "claim": st["claim"], "verbatim": st["verbatim"], "context": st["context"],
                "attribution": f"{st['attribution_kind']}"
                               + (f", to {st['attributed_to']} {st['attributed_citation']}"
                                  if st["attributed_to"] else ""),
                "paper_meta": f"arXiv {meta.get('arxiv_id','?')}: {meta.get('title','')}",
                "related": build_related(doc, i),
            }))
    return out


def build_prompt(problem: dict) -> str:
    text = PROMPT.read_text()
    for key in ("CLAIM", "VERBATIM", "CONTEXT", "ATTRIBUTION", "PAPER_META", "RELATED"):
        text = text.replace("{{" + key + "}}", str(problem.get(key.lower(), "(not supplied)")))
    return text + (
        "\n\n## Output\n\nReturn ONLY a JSON object conforming to this schema. "
        "No prose, no markdown fences.\n\n```json\n" + SCHEMA.read_text() + "\n```\n"
    )



def _repair_json(text: str) -> str:
    """Double backslashes that are not legal JSON escapes.

    The claude-cli backend has no schema enforcement, and mathematics papers are
    almost entirely backslashes -- a verbatim LaTeX statement containing \alpha
    or \{ is emitted as an invalid escape and json.loads rejects the whole
    record. Legal escapes are " \\ / b f n r t and u+4hex; anything else gets
    doubled so it survives as a literal backslash.
    """
    # Each escape must be CONSUMED, not looked ahead at. A lookahead leaves the
    # second character of a valid \\ pair to be rescanned as the start of a new
    # escape, so "\\valid" gets corrupted into "\\\valid". Note 'u' is excluded
    # from the single-char class so that \umbral (invalid) is repaired while
    # é (valid) is not.
    return re.sub(
        r'\\(?:(["\\/bfnrt])|u([0-9a-fA-F]{4})|(.)|$)',
        lambda m: m.group(0) if (m.group(1) or m.group(2)) else "\\\\" + (m.group(3) or ""),
        text,
        flags=re.S,
    )


def _parse_json(text: str) -> dict:
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(_repair_json(body))


def run_claude_cli(prompt: str, model: str, timeout: int = 1200) -> tuple[dict, dict]:
    proc = subprocess.run(
        ["claude", "-p", "--model", model,
         "--system-prompt", CLI_SYSTEM_PROMPT,
         "--tools", "--exclude-dynamic-system-prompt-sections",
         "--output-format", "json"],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:400]}")
    env = json.loads(proc.stdout)
    if env.get("is_error"):
        raise RuntimeError(f"claude error: {env.get('result','')[:400]}")
    return _parse_json(env["result"]), {"cost_usd": env.get("total_cost_usd"),
                              "output_tokens": env["usage"]["output_tokens"]}


def run_api(prompt: str, model: str) -> tuple[dict, dict]:
    import anthropic
    r = anthropic.Anthropic().messages.create(
        model=model, max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": json.loads(SCHEMA.read_text())}},
    )
    return json.loads(next(b.text for b in r.content if b.type == "text")), {
        "cost_usd": None, "output_tokens": r.usage.output_tokens}


def show(name: str, a: dict, expected: dict | None) -> bool | None:
    gate = a["gate_pass"]
    print(f"\n{BOLD}{name}{OFF}")
    print(f"  GATE       {GREEN + 'PASS' + OFF if gate else RED + 'FAIL' + OFF}   {a['gate_reason'][:150]}")
    if gate and a.get("finite_witness"):
        print(f"  witness    {a['finite_witness'][:150]}")
    print(f"  frontier   {a['frontier_status']}"
          + (f"  smallest_open={a['frontier_smallest_open']}" if a["frontier_smallest_open"] else ""))
    if a["frontier_quote"]:
        print(f'{DIM}             quote: "{a["frontier_quote"][:130]}"{OFF}')
    print(f"  machinery  {a['machinery_depth']}   quantifier {a['quantifier_form']}")
    print(f"  prior_comp {a['prior_computation']}   venue {a['venue_signal']}")
    print(f"  attention  {a['attention']}")
    print(f"{DIM}             {a['attention_reason'][:150]}{OFF}")
    print(f"\n  {a['argument']}")

    if not expected:
        return None
    want = bool(expected.get("expected_gate_pass"))
    ok = gate == want
    print(f"\n  {GREEN + '✓ MATCHES' + OFF if ok else RED + '✗ MISMATCH' + OFF} known outcome: "
          f"{expected['known_outcome']} (expected gate_pass={want})")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--from-extraction", type=Path, nargs="+", metavar="FILE",
                    help="assess every open statement in one or more stage-1 extraction "
                         "files; accepts a glob, e.g. cache/extractions/*.json")
    ap.add_argument("--screened", action="store_true",
                    help="assess only statements that PASSED scripts/screen.py")
    ap.add_argument("--limit", type=int, metavar="N", help="assess at most N problems")
    ap.add_argument("--max-cost", type=float, default=15.0, metavar="USD",
                    help="stop cleanly at this cumulative spend (default 15.00). Safe to "
                         "hit -- the run is resumable.")
    ap.add_argument("--force", action="store_true",
                    help="re-assess problems already in cache/assessments")
    ap.add_argument("--backend", choices=["claude-cli", "api"], default="claude-cli")
    ap.add_argument("--model", default=None, help="default: 'opus' (cli) / 'claude-opus-5' (api)")
    args = ap.parse_args()

    model = args.model or ("opus" if args.backend == "claude-cli" else "claude-opus-5")

    problems: list[tuple[str, dict]] = []
    for path in args.files:
        problems.append((path.stem, json.loads(path.read_text())))
    for extraction in args.from_extraction or []:
        doc = json.loads(extraction.read_text())
        meta = doc.get("_meta", {})
        for i, s in enumerate(doc["statements"], 1):
            if s["stated_as"] != "open":
                continue
            problems.append((f"{meta.get('arxiv_id','?')}#{i}", {
                "claim": s["claim"], "verbatim": s["verbatim"], "context": s["context"],
                "attribution": f"{s['attribution_kind']}"
                               + (f", to {s['attributed_to']} {s['attributed_citation']}"
                                  if s["attributed_to"] else ""),
                "paper_meta": f"arXiv {meta.get('arxiv_id','?')}: {meta.get('title','')}",
                "related": build_related(doc, i),
            }))
    if args.screened:
        problems.extend(screened_problems())
    if not problems:
        ap.error("give input files, --from-extraction, or --screened")

    # Resumable: a 350-problem run is hours long and will be interrupted.
    if not args.force:
        before = len(problems)
        problems = [(n, p) for n, p in problems
                    if not (OUT / f"{n.replace('#', '_')}.json").exists()]
        if before != len(problems):
            print(f"skipping {before - len(problems)} already assessed; "
                  f"{len(problems)} to go  (--force to redo)")
    if args.limit:
        problems = problems[:args.limit]
    if not problems:
        print("nothing to do")
        return 0

    # Single-instance lock: two concurrent runs duplicate every call, and
    # --max-cost is per process so the cap silently doubles.
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT / ".running.pid"
    if lock.exists():
        try:
            other = int(lock.read_text())
            os.kill(other, 0)
            print(f"already running as pid {other}. Kill it, or delete "
                  f"{lock.relative_to(ROOT)} if stale.", file=sys.stderr)
            return 1
        except (ProcessLookupError, ValueError):
            pass
    lock.write_text(str(os.getpid()))
    atexit.register(lambda: lock.unlink(missing_ok=True))

    calibration = load_calibration()
    OUT.mkdir(parents=True, exist_ok=True)
    cost = 0.0
    scored = [0, 0]

    for n_done, (name, problem) in enumerate(problems, 1):
        if cost >= args.max_cost:
            print(f"\nSTOPPED: cost cap ${args.max_cost:.2f} reached after "
                  f"{n_done - 1} problems (${cost:.2f}). {len(problems) - n_done + 1} "
                  f"remaining — re-run with a higher --max-cost to continue.")
            break
        started = time.time()
        try:
            result, usage = (run_claude_cli(build_prompt(problem), model)
                             if args.backend == "claude-cli"
                             else run_api(build_prompt(problem), model))
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        cost += usage.get("cost_usd") or 0.0
        result["_meta"] = {"name": name, "model": model, "backend": args.backend,
                           "seconds": round(time.time() - started, 1), "usage": usage}
        (OUT / f"{name.replace('#', '_')}.json").write_text(json.dumps(result, indent=2))

        if len(problems) > 5:
            print(f"{DIM}[{n_done}/{len(problems)}]  ${cost:.2f} spent{OFF}", flush=True)
        verdict = show(name, result, calibration.get(problem.get("calibration_slug", "")))
        if verdict is not None:
            scored[0 if verdict else 1] += 1

    print(f"\n{'-' * 60}")
    if sum(scored):
        print(f"backtest: {GREEN}{scored[0]} matched{OFF}, {RED}{scored[1]} mismatched{OFF}")
    if cost:
        print(f"cost: ${cost:.3f}")
    print(f"full records in cache/assessments/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
