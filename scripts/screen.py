#!/usr/bin/env python3
"""Cheap Gate screen in front of the full assessment.

    scripts/screen.py --validate     # compare against existing Opus verdicts
    scripts/screen.py --all          # screen every open statement
    scripts/screen.py --report       # summarise results, no model calls

Answers only "is there a finite object to look for?" on Haiku at ~$0.005 per
problem, so the ~$0.10 Opus assessment runs only on survivors. Results land in
cache/screen/ keyed the same way as assessments (<paper>_<n>.json).
"""
from __future__ import annotations
import argparse, atexit, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT, SCHEMA = ROOT / "prompts" / "screen.md", ROOT / "prompts" / "screen.schema.json"
EXTRACTIONS, ASSESSMENTS = ROOT / "cache" / "extractions", ROOT / "cache" / "assessments"
OUT = ROOT / "cache" / "screen"
SYS = "You classify mathematical problems. Reply with a single JSON object and nothing else."
GREEN, RED, DIM, OFF = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def statements() -> list[dict]:
    out = []
    for p in sorted(EXTRACTIONS.glob("*.json")):
        d = json.loads(p.read_text())
        for i, s in enumerate(d.get("statements", []), 1):
            if s["stated_as"] == "open":
                out.append({"ref": f"{d['_meta']['arxiv_id']}_{i}",
                            "claim": s["claim"], "verbatim": s["verbatim"]})
    return out


def screen_one(st: dict, model: str = "haiku") -> tuple[dict, float]:
    prompt = (PROMPT.read_text()
              .replace("{{CLAIM}}", st["claim"])
              .replace("{{VERBATIM}}", st["verbatim"])
              + "\n\n## Output\n\nReturn ONLY JSON matching this schema.\n\n```json\n"
              + SCHEMA.read_text() + "\n```\n")
    r = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", SYS,
                        "--tools", "--exclude-dynamic-system-prompt-sections",
                        "--output-format", "json"],
                       input=prompt, capture_output=True, text=True, timeout=240)
    env = json.loads(r.stdout)
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", env["result"].strip())
    return json.loads(body), env.get("total_cost_usd") or 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true",
                    help="screen only problems that already have an Opus verdict, and compare")
    ap.add_argument("--all", action="store_true", help="screen every open statement")
    ap.add_argument("--report", action="store_true", help="summarise cached results only")
    ap.add_argument("--max-cost", type=float, default=10.0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # Refuse to run twice. Two concurrent runs duplicate every call and double
    # the spend, while --max-cost is enforced per process so the cap silently
    # doubles too. Observed in practice; cheap to prevent.
    lock = OUT / ".running.pid"
    if not args.report:
        if lock.exists():
            try:
                other = int(lock.read_text())
                os.kill(other, 0)          # raises if that pid is gone
                print(f"already running as pid {other}. Kill it first, or delete "
                      f"{lock.relative_to(ROOT)} if it is stale.", file=sys.stderr)
                return 1
            except (ProcessLookupError, ValueError):
                pass                        # stale lock, take it over
        lock.write_text(str(os.getpid()))
        atexit.register(lambda: lock.unlink(missing_ok=True))

    if args.report:
        rows = [json.loads(p.read_text()) for p in OUT.glob("*.json")]
        n = len(rows); p_ = sum(1 for r in rows if r["gate_pass"])
        print(f"{n} screened: {GREEN}{p_} pass{OFF}, {RED}{n - p_} fail{OFF}"
              + (f"  ({100 * p_ / n:.0f}% survive)" if n else ""))
        if p_: print(f"full assessment of survivors: ~${p_ * 0.10:.0f}")
        return 0

    todo = statements()
    if args.validate:
        have = {p.stem for p in ASSESSMENTS.glob("*.json")}
        todo = [s for s in todo if s["ref"] in have]
        print(f"validating against {len(todo)} problems with existing Opus verdicts\n")
    elif not args.all:
        ap.error("give --validate, --all, or --report")

    cost = 0.0; agree = dis = 0
    for i, st in enumerate(todo, 1):
        cached = OUT / f"{st['ref']}.json"
        if cached.exists() and not args.validate:
            continue
        try:
            res, c = screen_one(st)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {st['ref']}: {type(exc).__name__}", file=sys.stderr); continue
        cost += c
        cached.write_text(json.dumps({**res, "ref": st["ref"]}, indent=2))

        if args.validate:
            opus = json.loads((ASSESSMENTS / f"{st['ref']}.json").read_text())["gate_pass"]
            ok = opus == res["gate_pass"]
            agree, dis = agree + ok, dis + (not ok)
            mark = f"{GREEN}agree{OFF}" if ok else f"{RED}DISAGREE{OFF}"
            print(f"  {st['ref']:<18} haiku={'PASS' if res['gate_pass'] else 'FAIL':<4} "
                  f"opus={'PASS' if opus else 'FAIL':<4} {mark}")
            if not ok:
                print(f"    {DIM}haiku: {res['reason'][:120]}{OFF}")
        else:
            print(f"  [{i}/{len(todo)}] {st['ref']:<18} "
                  f"{'PASS' if res['gate_pass'] else 'fail'}  ${cost:.2f}", flush=True)
        if cost >= args.max_cost:
            print(f"\nstopped: cost cap ${args.max_cost} reached"); break

    if args.validate and (agree + dis):
        print(f"\n{agree}/{agree + dis} agree with Opus ({100 * agree / (agree + dis):.0f}%)")
        print(f"cost: ${cost:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
