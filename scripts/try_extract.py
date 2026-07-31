#!/usr/bin/env python3
"""Run the stage-1 extraction prompt over a few papers and dump the results.

A development tool for iterating on prompts/extract.md, not the pipeline. The
point is to read the output by hand: stage 1 optimises for recall, and the only
way to know whether it is recalling is to open a paper and check what it missed.

    scripts/try_extract.py --recent 5 --category math.CO
    scripts/try_extract.py 2607.21466v1 2607.21568v1
    scripts/try_extract.py --recent 3 --show          # print each claim inline

Two execution backends:

  claude-cli (default)  Runs through the authenticated Claude Code CLI. Needs no
                        Anthropic developer-platform account, which is why it is
                        the default. Costs ~2x the batched API rate per paper and
                        runs one paper per invocation, so it does not scale to a
                        full month unaided -- but it is enough to iterate on the
                        prompt, which is what this script is for.

  api                   Direct Anthropic SDK with schema-enforced structured
                        output. Needs ANTHROPIC_API_KEY or an `ant auth login`
                        profile. Use this once platform access exists.

Sources are cached under cache/ so re-runs cost nothing and stay polite to
arXiv. Results land in cache/extractions/.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html as _html
import io
import json
import re
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "extract.md"
SCHEMA = ROOT / "prompts" / "extract.schema.json"
CACHE = ROOT / "cache"
OUT = CACHE / "extractions"

USER_AGENT = "OpenMathProblemsLab/0.1 (research prototype)"
ARXIV_DELAY_S = 3  # arXiv asks for one request per 3 seconds
MAX_TEX_CHARS = 500_000

# Replacing Claude Code's default system prompt and dropping its tools takes the
# per-invocation overhead from ~24,600 tokens to ~590. Measured, not guessed.
CLI_SYSTEM_PROMPT = (
    "You extract structured data from mathematics papers. "
    "Reply with a single JSON object and nothing else."
)


# --------------------------------------------------------------------------
# arXiv
# --------------------------------------------------------------------------

_last_call = 0.0


def fetch(url: str, timeout: int = 120, attempts: int = 5) -> bytes:
    """GET with politeness spacing and backoff.

    arXiv returns 429 readily and does not always send Retry-After, so we
    enforce a minimum gap between calls and back off exponentially on top.
    """
    global _last_call
    for attempt in range(attempts):
        gap = time.time() - _last_call
        if gap < ARXIV_DELAY_S:
            time.sleep(ARXIV_DELAY_S - gap)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            _last_call = time.time()
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503):
                raise
            if attempt == attempts - 1:
                # arXiv answers a sustained burst with "Rate exceeded" and keeps
                # doing so for several minutes. A traceback here is noise; the
                # only useful advice is to wait or work from cache.
                raise SystemExit(
                    f"\narXiv is rate-limiting us (HTTP {exc.code}) and did not "
                    f"relent after {attempts} attempts.\n"
                    f"Wait several minutes, or skip the API entirely by naming "
                    f"cached papers explicitly:\n"
                    f"    ls cache/src/    # already downloaded\n"
                    f"    scripts/try_extract.py 2607.21508v1 2607.21222v1 --show\n"
                ) from None
            wait = int(exc.headers.get("Retry-After") or 0) or ARXIV_DELAY_S * 2 ** (attempt + 1)
            print(f"  .. arXiv {exc.code}, retrying in {wait}s "
                  f"({attempt + 1}/{attempts - 1})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _entries(xml: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        body = m.group(1)
        ident = re.search(r"<id>http://arxiv\.org/abs/([^<]+)</id>", body)
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        if ident:
            out.append({
                "arxiv_id": ident.group(1),
                "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "(unknown)",
            })
    return out


def recent(category: str, count: int) -> list[dict]:
    """Most recent papers in a category, with titles.

    Uses the HTML listing page rather than export.arxiv.org/api/query. The query
    API is chronically overloaded -- it has been observed taking 46 seconds to
    return "Rate exceeded" -- while the listing page answers in ~50ms and gives
    us ids and titles in one request. Both live on different hosts, so a query
    API outage does not affect this path.
    """
    html = fetch(
        f"https://arxiv.org/list/{category}/recent?skip=0&show={max(count, 50)}"
    ).decode("utf-8", "replace")

    ids = re.findall(r'href="/pdf/(\d{4}\.\d{4,5})', html)
    titles = re.findall(
        r"<div class='list-title mathjax'>"
        r"<span class='descriptor'>Title:</span>\s*(.*?)\s*</div>",
        html, re.S,
    )
    entries, seen = [], set()
    for i, arxiv_id in enumerate(ids):
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        title = (_html.unescape(re.sub(r"\s+", " ", titles[i])).strip()
                 if i < len(titles) else "(unknown)")
        entry = {"arxiv_id": arxiv_id, "title": title}
        _cache_meta(arxiv_id, entry)
        entries.append(entry)
        if len(entries) >= count:
            break
    return entries


def harvest(categories: list[str], date_from: str, date_until: str) -> list[dict]:
    """Bulk-harvest a date range over OAI-PMH -- the real corpus path.

    OAI-PMH is the interface arXiv actually intends for harvesting, and unlike
    /api/query it is not throttled: one day of the whole `math` set returns ~476
    records in about five seconds. Handles resumption tokens for longer ranges.

    Note OAI filters on DATESTAMP, not submission date, so a range includes
    revisions of much older papers. We keep only ids whose YYMM prefix falls in
    the requested months, which is what "papers from June 2026" actually means.
    """
    base = "https://export.arxiv.org/oai2"
    params = {"verb": "ListRecords", "set": "math", "metadataPrefix": "arXiv",
              "from": date_from, "until": date_until}
    wanted = set(categories)
    months = {f"{d[2:4]}{d[5:7]}" for d in (date_from, date_until)}
    out, token = [], None

    while True:
        query = {"verb": "ListRecords", "resumptionToken": token} if token else params
        xml = fetch(f"{base}?{urllib.parse.urlencode(query)}").decode("utf-8", "replace")

        for rec in re.findall(r"<record>(.*?)</record>", xml, re.S):
            def field(tag: str) -> str:
                m = re.search(rf"<{tag}>(.*?)</{tag}>", rec, re.S)
                return _html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""

            arxiv_id, cats = field("id"), field("categories").split()
            if not arxiv_id or arxiv_id[:4] not in months:
                continue  # a revision of an older paper, not a submission
            if not wanted.intersection(cats):
                continue
            entry = {"arxiv_id": arxiv_id, "title": field("title"),
                     "categories": cats, "created": field("created")}
            _cache_meta(arxiv_id, entry)
            out.append(entry)

        m = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", xml)
        token = m.group(1) if m else None
        print(f"  .. harvested {len(out)} matching papers", file=sys.stderr)
        if not token:
            return out


def _meta_path(arxiv_id: str) -> Path:
    return CACHE / "meta" / f"{arxiv_id.replace('/', '_')}.json"


def _cache_meta(arxiv_id: str, meta: dict) -> None:
    path = _meta_path(arxiv_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta))


def metadata(arxiv_id: str) -> dict:
    """Cached, so re-runs and mixed id/--recent invocations cost no API calls."""
    path = _meta_path(arxiv_id)
    if path.exists():
        return json.loads(path.read_text())
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"id_list": arxiv_id.split("v")[0], "max_results": 1}
    )
    entries = _entries(fetch(url).decode())
    meta = entries[0] if entries else {"arxiv_id": arxiv_id, "title": "(unknown)"}
    _cache_meta(arxiv_id, meta)
    return meta


def ensure_source(arxiv_id: str) -> Path:
    path = CACHE / "src" / f"{arxiv_id.replace('/', '_')}.tar.gz"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fetch(f"https://arxiv.org/e-print/{arxiv_id}"))
    time.sleep(ARXIV_DELAY_S)
    return path


def _already_done(arxiv_id: str, prompt_sha: str) -> bool:
    """True if this paper has a cached extraction from the CURRENT prompt.

    Makes a long run resumable: a 331-paper job that dies at paper 200 picks up
    where it left off. Keyed on the prompt hash so editing the prompt correctly
    invalidates everything.
    """
    path = OUT / f"{arxiv_id.replace('/', '_')}.json"
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text()).get("_meta", {}).get("prompt_sha256") == prompt_sha
    except Exception:  # noqa: BLE001 - unreadable cache is not done
        return False


def read_tex(path: Path) -> tuple[str, str]:
    """Return (tex, how). arXiv e-prints are a tarball or a single gzipped .tex."""
    raw = path.read_bytes()
    try:
        tf = tarfile.open(fileobj=io.BytesIO(raw))
        parts = [
            tf.extractfile(m).read().decode("utf-8", "replace")
            for m in tf.getmembers()
            if m.name.lower().endswith(".tex")
        ]
        return "\n".join(parts), "tar"
    except tarfile.ReadError:
        pass
    try:
        return gzip.decompress(raw).decode("utf-8", "replace"), "gzip"
    except Exception as exc:  # noqa: BLE001 - surface it, don't kill the batch
        return "", f"unreadable:{type(exc).__name__}"


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

def build_prompt(arxiv_id: str, title: str, tex: str) -> str:
    return (
        PROMPT.read_text()
        .replace("{{ARXIV_ID}}", arxiv_id)
        .replace("{{TITLE}}", title)
        .replace("{{TEX}}", tex[:MAX_TEX_CHARS])
    )


def _strip_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())


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
    body = _strip_fences(text)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(_repair_json(body))


def run_claude_cli(prompt: str, model: str, timeout: int = 900) -> tuple[dict, dict]:
    """Execute via the authenticated Claude Code CLI.

    No schema enforcement is available here, so the schema is appended to the
    prompt and the reply is parsed defensively.
    """
    prompt += (
        "\n\n## Output\n\nReturn ONLY a JSON object conforming to this schema. "
        "No prose, no markdown fences.\n\n```json\n"
        + SCHEMA.read_text()
        + "\n```\n"
    )
    proc = subprocess.run(
        [
            "claude", "-p",
            "--model", model,
            "--system-prompt", CLI_SYSTEM_PROMPT,
            "--tools",
            "--exclude-dynamic-system-prompt-sections",
            "--output-format", "json",
        ],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:400]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude error: {envelope.get('result', '')[:400]}")
    return _parse_json(envelope["result"]), {
        "input_tokens": envelope["usage"]["input_tokens"],
        "output_tokens": envelope["usage"]["output_tokens"],
        "cost_usd": envelope.get("total_cost_usd"),
    }


def run_api(prompt: str, model: str) -> tuple[dict, dict]:
    """Execute via the Anthropic SDK, with the schema actually enforced."""
    import anthropic

    response = anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": json.loads(SCHEMA.read_text())}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": None,
    }


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="arXiv IDs, e.g. 2607.21466v1")
    ap.add_argument("--recent", type=int, help="instead, take the N most recent papers")
    ap.add_argument("--category", default="math.CO")
    ap.add_argument("--harvest", metavar="FROM:UNTIL",
                    help="bulk-harvest a date range over OAI-PMH, e.g. 2026-06-01:2026-06-30. "
                         "Lists what it finds and exits unless --extract-all is given.")
    ap.add_argument("--categories", default="math.CO,math.AC,math.RT,math.GR",
                    help="categories to keep when harvesting")
    ap.add_argument("--extract-all", action="store_true",
                    help="with --harvest, actually run extraction over everything found")
    ap.add_argument("--force", action="store_true",
                    help="re-extract papers already in cache/extractions (default: skip them, "
                         "so a long run is resumable)")
    ap.add_argument("--backend", choices=["claude-cli", "api"], default="claude-cli")
    ap.add_argument("--model", default=None, help="default: 'haiku' (cli) / 'claude-haiku-4-5' (api)")
    ap.add_argument("--show", action="store_true", help="print each claim inline")
    args = ap.parse_args()

    model = args.model or ("haiku" if args.backend == "claude-cli" else "claude-haiku-4-5")
    if args.ids:
        papers = [{"arxiv_id": i} for i in args.ids]
    elif args.recent:
        papers = recent(args.category, args.recent)
    elif args.harvest:
        date_from, _, date_until = args.harvest.partition(":")
        papers = harvest([c.strip() for c in args.categories.split(",")],
                         date_from, date_until)
        print(f"\n{len(papers)} papers in {args.categories} "
              f"submitted {date_from}..{date_until}")
        if not args.extract_all:
            for p in papers[:20]:
                print(f"  {p['arxiv_id']}  {p['title'][:70]}")
            if len(papers) > 20:
                print(f"  ... and {len(papers) - 20} more")
            print("\nAdd --extract-all to run extraction over these.")
            return 0
    else:
        ap.error("give some arXiv IDs, --recent N, or --harvest FROM:UNTIL")

    OUT.mkdir(parents=True, exist_ok=True)

    if not args.force:
        prompt_sha = hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:12]
        before = len(papers)
        papers = [e for e in papers if not _already_done(e["arxiv_id"], prompt_sha)]
        if before != len(papers):
            print(f"skipping {before - len(papers)} paper(s) already extracted with this "
                  f"prompt; {len(papers)} to go  (--force to redo)")
    if not papers:
        print("nothing to do")
        return 0

    totals = {"papers": 0, "statements": 0, "open": 0, "cost": 0.0, "seconds": 0.0}
    total_n = len(papers)

    for n_done, entry in enumerate(papers, 1):
        arxiv_id = entry["arxiv_id"]
        title = entry.get("title") or metadata(arxiv_id)["title"]
        tex, how = read_tex(ensure_source(arxiv_id))
        if not tex:
            print(f"  !! {arxiv_id}: no .tex ({how})", file=sys.stderr)
            continue

        prompt = build_prompt(arxiv_id, title, tex)
        started = time.time()
        try:
            result, usage = (run_claude_cli(prompt, model) if args.backend == "claude-cli"
                             else run_api(prompt, model))
        except Exception as exc:  # noqa: BLE001 - one bad paper shouldn't stop the run
            print(f"  !! {arxiv_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        elapsed = time.time() - started

        result["_meta"] = {
            "arxiv_id": arxiv_id, "title": title, "backend": args.backend, "model": model,
            "prompt_sha256": hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:12],
            "tex_chars": len(tex), "tex_truncated": len(tex) > MAX_TEX_CHARS,
            "usage": usage, "seconds": round(elapsed, 1),
        }
        (OUT / f"{arxiv_id.replace('/', '_')}.json").write_text(json.dumps(result, indent=2))

        statements = result["statements"]
        open_count = sum(1 for s in statements if s["stated_as"] == "open")
        totals["papers"] += 1
        totals["statements"] += len(statements)
        totals["open"] += open_count
        totals["cost"] += usage.get("cost_usd") or 0.0
        totals["seconds"] += elapsed

        flag = "" if result["extraction_confidence"] == "high" else "  [LOW CONFIDENCE]"
        eta = ""
        if total_n > 1:
            avg = totals["seconds"] / max(totals["papers"], 1)
            eta = f"  eta {(total_n - n_done) * avg / 60:.0f}m" if totals["papers"] else ""
            eta += f"  ${totals['cost']:.2f} so far"
        print(f"\n[{n_done}/{total_n}] {arxiv_id}  {title[:52]}{flag}{eta}")
        print(f"  {len(statements)} statement(s), {open_count} open  ({elapsed:.0f}s)")
        for s in statements:
            who = s["attributed_to"] or s["attribution_kind"]
            print(f"    - [{s['stated_as']:<19}] {s['location'][:34]:<34} ({who})")
            if args.show:
                print(f"        {s['claim']}")

    if totals["papers"]:
        print(f"\n{totals['papers']} papers | {totals['statements']} statements "
              f"({totals['open']} open) | {totals['seconds']:.0f}s"
              + (f" | ${totals['cost']:.3f}" if totals["cost"] else ""))
        print(f"Full records in {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
