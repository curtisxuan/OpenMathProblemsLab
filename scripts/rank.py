#!/usr/bin/env python3
"""Rank assessed problems by shovel-readiness.

    scripts/rank.py              # ranked table
    scripts/rank.py --why        # show the argument's last sentence too
    scripts/rank.py --all        # include gate failures at the bottom
    scripts/rank.py --json

WHAT THIS IS NOT: a probability that a problem will be solved. Nobody has yet
attacked a problem this system recommended, so there is no data on how often it
is right. This ranks how READY a problem is for someone to start today.

WHY IT IS A SORT AND NOT A SCORE (ADR-0005): the axes are not commensurable, so
any weighted total would bury an arbitrary choice of weights inside a single
number nobody can audit. A lexicographic sort orders the list while leaving every
input visible -- you can always see which axis broke a tie, and disagree with it.

THE PRIORITY ORDER, and why:

  1. Frontier known before unknown.  An unknown frontier means you cannot start;
     the first task is a literature search, not a computation.
  2. Shallow machinery before deep.  If you cannot understand the statement this
     week, nothing else about it matters.
  3. Prior computation available before none.  Starting from someone's tables or
     code beats rebuilding toward the frontier.
  4. Universal/existential before mixed/neither.  One object settles those; the
     others need a theory.
  5. Attention fresh before heavy.  LAST, deliberately: on every case we could
     check against reality, this axis was wrong in the pessimistic direction, so
     it earns the weakest tie-break rather than a primary key.

Edit RANK_KEYS to disagree. That is the point of keeping it a sort.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def _pick(kind: str) -> tuple[Path, bool]:
    """cache/ when populated, else the tracked examples. See ADR-0006."""
    live = ROOT / "cache" / kind
    if live.exists() and any(live.glob("*.json")):
        return live, False
    return ROOT / "examples" / kind, True


ASSESSMENTS, USING_EXAMPLES = _pick("assessments")
EXTRACTIONS, _ = _pick("extractions")

BOLD, DIM, GREEN, YELLOW, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

# (field, best-to-worst). Order of this list IS the priority order.
RANK_KEYS: list[tuple[str, list[str]]] = [
    ("frontier_status",   ["known", "unknown"]),
    ("machinery_depth",   ["shallow", "moderate", "deep"]),
    ("prior_computation", ["available", "referenced", "none"]),
    ("quantifier_form",   ["existential", "universal", "mixed", "neither"]),
    ("attention",         ["fresh", "some", "heavy"]),
]


def claim_for(name: str) -> str:
    """Recover the human-readable claim from the extraction that produced this."""
    m = re.match(r"(.+)_(\d+)$", name)
    if not m:
        return name
    paper, idx = m.group(1), int(m.group(2))
    path = EXTRACTIONS / f"{paper}.json"
    if not path.exists():
        return name
    statements = json.loads(path.read_text()).get("statements", [])
    return statements[idx - 1]["claim"] if 0 < idx <= len(statements) else name


def sort_key(a: dict) -> tuple:
    return tuple(
        order.index(a[field]) if a.get(field) in order else len(order)
        for field, order in RANK_KEYS
    )


def backtest_stems() -> set[str]:
    """Names of calibration fixtures, which must never appear as candidates.

    Backtest inputs are conjectures whose outcome is already known -- both
    current ones are refuted. They are graded test cases for the rubric, not
    problems to work on, and ranking them as candidates would be actively
    misleading.
    """
    d = ROOT / "judgment" / "backtest"
    return {p.stem for p in d.glob("*.json")} if d.exists() else set()


RISK_CUES = ("strongest reason", "waste", "wastes", "burns", "burn", "eats a week",
             "reason to walk away", "the risk", "danger")


def risk_sentence(argument: str) -> str:
    """The sentence stating why this might be a bad use of a week.

    The prompt asks for it but does not fix its position, and it is often not
    last -- arguments frequently close on an upside. Look for the cue, and only
    fall back to the final sentence if none is found.
    """
    sentences = re.split(r"(?<=[.!?])\s+", argument.strip())
    for s in sentences:
        if any(cue in s.lower() for cue in RISK_CUES):
            return s
    return sentences[-1] if sentences else ""


def load() -> list[dict]:
    skip = backtest_stems()
    out = []
    for path in sorted(ASSESSMENTS.glob("*.json")):
        if path.stem in skip:
            continue
        a = json.loads(path.read_text())
        a["_name"] = path.stem
        a["_claim"] = claim_for(path.stem)
        out.append(a)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--why", action="store_true",
                    help="show each argument's closing sentence")
    ap.add_argument("--all", action="store_true", help="include gate failures")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not ASSESSMENTS.exists():
        print("no assessments found — run scripts/try_assess.py first", file=sys.stderr)
        return 1
    if USING_EXAMPLES and not args.json:
        print(f"{DIM}reading the tracked examples/ set (cache/ is empty). "
              f"Run scripts/try_assess.py to generate your own.{OFF}")

    rows = load()
    passed = sorted((r for r in rows if r["gate_pass"]), key=sort_key)
    failed = [r for r in rows if not r["gate_pass"]]

    if args.json:
        json.dump({"ranked": passed, "gate_failed": failed}, sys.stdout, indent=2, default=str)
        print()
        return 0

    print(f"{BOLD}Ranked by shovel-readiness{OFF} "
          f"{DIM}(not probability of success — see --help){OFF}")
    print(DIM + "priority: " + " > ".join(f for f, _ in RANK_KEYS) + OFF)
    print()
    hdr = f"{'#':>2}  {'frontier':<8} {'machinery':<9} {'priorcomp':<10} {'quant':<11} {'atten':<5}  problem"
    print(hdr); print("-" * len(hdr))

    for i, a in enumerate(passed, 1):
        front = (GREEN + "known" + OFF) if a["frontier_status"] == "known" else (YELLOW + "unknown" + OFF)
        pad = 8 + len(front) - len(re.sub(r"\033\[[0-9;]*m", "", front))
        print(f"{i:>2}  {front:<{pad}} {a['machinery_depth']:<9} "
              f"{a['prior_computation']:<10} {a['quantifier_form']:<11} "
              f"{a['attention']:<5}  {a['_claim'][:60]}")
        print(f"    {DIM}{a['_name']}{OFF}")
        if args.why:
            print(f"    {DIM}risk: {risk_sentence(a['argument'])[:240]}{OFF}\n")

    if failed and args.all:
        print(f"\n{RED}Gate failed — no finite object settles these{OFF}")
        for a in failed:
            print(f"    {a['_claim'][:70]}")
            print(f"    {DIM}{a['_name']} · {a['gate_reason'][:110]}{OFF}")

    print(f"\n{len(passed)} ranked, {len(failed)} rejected by the Gate"
          + ("" if args.all else "  (--all to see them)"))
    print(f"{DIM}Ranking is a reading order. The argument matters more than the axes — "
          f"use --why, or read docs/reading-an-assessment.md.{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
