#!/usr/bin/env python3
"""Browse every Statement across all cached extractions.

Stage 1 writes one JSON file per paper, which is the wrong shape for asking
"what open problems do I have?". This reads all of them and gives one view.

    scripts/statements.py                      # everything, one line each
    scripts/statements.py --open               # only what is still open
    scripts/statements.py --open --full        # with verbatim and context
    scripts/statements.py --paper 2607.26049   # one paper
    scripts/statements.py --attributed         # credited to someone else
    scripts/statements.py --stale              # extracted by an older prompt
    scripts/statements.py --open --json        # for piping

Nothing here calls a model. It reads cache/extractions/ only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACTIONS = ROOT / "cache" / "extractions"
PROMPT = ROOT / "prompts" / "extract.md"

DIM, BOLD, GREEN, YELLOW, OFF = "\033[2m", "\033[1m", "\033[32m", "\033[33m", "\033[0m"


def current_prompt_sha() -> str:
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:12]


def load() -> list[dict]:
    """Flatten every extraction into a list of statement records."""
    out = []
    for path in sorted(EXTRACTIONS.glob("*.json")):
        doc = json.loads(path.read_text())
        meta = doc.get("_meta", {})
        for i, s in enumerate(doc.get("statements", []), 1):
            out.append({
                **s,
                "arxiv_id": meta.get("arxiv_id", path.stem),
                "paper_title": meta.get("title", "(unknown)"),
                "ref": f"{meta.get('arxiv_id', path.stem)}#{i}",
                "prompt_sha256": meta.get("prompt_sha256", "?"),
                "key_results": doc.get("key_results", []),
                "source_file": str(path.relative_to(ROOT)),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open", action="store_true", help="only stated_as == open")
    ap.add_argument("--status", help="filter stated_as exactly")
    ap.add_argument("--paper", help="filter by arXiv id")
    ap.add_argument("--attributed", action="store_true", help="credited to someone else")
    ap.add_argument("--original", action="store_true", help="the authors' own questions")
    ap.add_argument("--stale", action="store_true",
                    help="only records from a prompt version other than the current one")
    ap.add_argument("--full", action="store_true", help="include verbatim and context")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    if not EXTRACTIONS.exists():
        print("no cache/extractions/ yet — run scripts/try_extract.py first", file=sys.stderr)
        return 1

    rows = load()
    total_before = len(rows)
    current = current_prompt_sha()

    if args.open:
        rows = [r for r in rows if r["stated_as"] == "open"]
    if args.status:
        rows = [r for r in rows if r["stated_as"] == args.status]
    if args.paper:
        rows = [r for r in rows if r["arxiv_id"].startswith(args.paper)]
    if args.attributed:
        rows = [r for r in rows if r["attribution_kind"] == "attributed"]
    if args.original:
        rows = [r for r in rows if r["attribution_kind"] == "original"]
    if args.stale:
        rows = [r for r in rows if r["prompt_sha256"] != current]

    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        print()
        return 0

    by_paper: dict[str, list[dict]] = {}
    for r in rows:
        by_paper.setdefault(r["arxiv_id"], []).append(r)

    for arxiv_id, group in by_paper.items():
        stale = group[0]["prompt_sha256"] != current
        flag = f"  {YELLOW}[stale prompt {group[0]['prompt_sha256']}]{OFF}" if stale else ""
        print(f"\n{BOLD}{arxiv_id}{OFF}  {group[0]['paper_title'][:64]}{flag}")
        for r in group:
            who = r["attributed_to"] or r["attribution_kind"]
            mark = GREEN + "open" + OFF if r["stated_as"] == "open" else DIM + r["stated_as"] + OFF
            print(f"  {r['ref']:<18} [{mark}] {DIM}{who}{OFF}")
            print(f"    {r['claim']}")
            if args.full:
                print(f"    {DIM}at {r['location']} · env={r['environment']}{OFF}")
                print(f"    {DIM}verbatim: {' '.join(r['verbatim'].split())[:260]}{OFF}")
                if r.get("notes"):
                    print(f"    {DIM}notes: {r['notes'][:200]}{OFF}")

    print(f"\n{'-' * 66}")
    print(f"{len(rows)} statements shown of {total_before} total, "
          f"across {len(by_paper)} papers")
    for label, key in (("status", "stated_as"), ("attribution", "attribution_kind")):
        counts = Counter(r[key] for r in rows)
        print(f"  by {label:12} " + "  ".join(f"{k}={v}" for k, v in counts.most_common()))

    # Check staleness at the FILE level, not from `rows`. A paper that yielded
    # zero statements contributes no rows, so a statement-level check can never
    # see it -- and a zero-statement result from an old prompt is exactly the
    # kind of thing worth re-running.
    stale_files = sorted(
        json.loads(p.read_text()).get("_meta", {}).get("arxiv_id", p.stem)
        for p in EXTRACTIONS.glob("*.json")
        if json.loads(p.read_text()).get("_meta", {}).get("prompt_sha256") != current
    )
    if stale_files:
        print(f"\n{YELLOW}{len(stale_files)} paper(s) extracted by an older prompt "
              f"(current is {current}).{OFF}")
        print("  Stage 2 will get fewer fields than it expects. Re-extract:")
        print(f"    scripts/try_extract.py {' '.join(stale_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
