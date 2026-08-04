#!/usr/bin/env python3
"""Generate a LaTeX collection of the top-ranked open problems.

    scripts/make_collection.py                    # top 30, all categories
    scripts/make_collection.py --top 40
    scripts/make_collection.py --category math.CO
    scripts/make_collection.py --compile          # also run a LaTeX engine

Writes digest/collection.tex, sectioned by arXiv primary category, in the style
of a curated problem collection: numbered Conjecture/Problem environments, the
statement verbatim from the paper, then a note on what is known and why the
problem looks attackable.

Only Gate-passing assessments are included, ordered by the same shovel-readiness
sort as scripts/rank.py.

A note on LaTeX robustness: statements are lifted verbatim from arbitrary papers,
which define their own macros. Any macro this document does not know is stubbed
with \\providecommand so the file always compiles -- an unknown \\zdmg renders as
a visible placeholder rather than killing the build. Problems whose statement
needed a stub are flagged in the output so they can be checked by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from rank import RANK_KEYS, backtest_stems, risk_sentence, sort_key  # noqa: E402

ASSESSMENTS = ROOT / "cache" / "assessments"
EXTRACTIONS = ROOT / "cache" / "extractions"
META = ROOT / "cache" / "meta"
OUT = ROOT / "digest"

CATEGORY_NAMES = {
    "math.CO": "Combinatorics",
    "math.AC": "Commutative Algebra",
    "math.RT": "Representation Theory",
    "math.GR": "Group Theory",
    "math.AG": "Algebraic Geometry",
    "math.NT": "Number Theory",
    "math.PR": "Probability",
    "math.MG": "Metric Geometry",
    "math.LO": "Logic",
    "math.OC": "Optimization and Control",
    "math.DS": "Dynamical Systems",
    "math.FA": "Functional Analysis",
    "math.GT": "Geometric Topology",
    "math.NA": "Numerical Analysis",
    "math.RA": "Rings and Algebras",
    "cs.DM": "Discrete Mathematics (CS)",
    "cs.CC": "Computational Complexity",
    "cs.IT": "Information Theory",
    "cs.DS": "Data Structures and Algorithms",
}

# Macros the preamble genuinely provides. Anything outside this gets stubbed.
PROVIDED = set("""
frac dfrac tfrac sqrt sum prod int oint iint lim limsup liminf log ln exp
sin cos tan sec csc cot arcsin arccos arctan sinh cosh tanh
mathbb mathcal mathbf mathrm mathfrak mathsf mathtt mathit boldsymbol
text textbf textit textrm textsf texttt emph bf it rm sf tt bm
leq geq neq approx simeq sim cong equiv propto asymp ll gg
subseteq subsetneq subset supseteq supset supsetneq in notin ni
cup cap sqcup sqcap setminus complement uplus
to rightarrow longrightarrow leftarrow Rightarrow Leftrightarrow iff implies
mapsto hookrightarrow twoheadrightarrow xrightarrow
forall exists nexists neg lnot land lor wedge vee bigwedge bigvee bigcup bigcap
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi
psi omega ell hbar imath jmath aleph
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
infty partial nabla emptyset varnothing top bot angle measuredangle
cdot cdots ldots dots vdots ddots bullet circ star ampersand
left right middle big Big bigg Bigg bigl bigr Bigl Bigr biggl biggr
langle rangle lfloor rfloor lceil rceil lvert rvert lVert rVert vert Vert
binom choose overline underline widehat widetilde hat tilde bar vec dot ddot
check acute grave breve overrightarrow overbrace underbrace
operatorname deg det ker dim rank tr trace Hom End Aut Out Inn Sym Alt
gcd lcm max min sup inf arg Pr mod bmod pmod pod
quad qquad hspace vspace hfill medskip smallskip bigskip
begin end item label ref eqref cref Cref pageref footnote
pm mp times div ast dagger ddagger prime backslash
colon semicolon nmid mid parallel perp
leftrightarrow uparrow downarrow updownarrow
displaystyle textstyle scriptstyle nonumber notag
ge le ne gets to cite citep citet mbox fbox makebox framebox
geqslant leqslant coloneqq eqqcolon defeq doteq
not neq nleq ngeq nsubseteq nparallel
H c v u d b r t k l o O i j AA aa ss S P dag ddag copyright pounds
sc scriptsize footnotesize small normalsize large Large LARGE huge Huge
newline linebreak par noindent indent centering raggedright raggedleft
mathpunct mathopen mathclose mathbin mathrel mathord limits nolimits
substack overset underset stackrel xleftarrow rightleftharpoons
""".split())

TEMPLATE = r"""\documentclass[11pt]{amsart}

\usepackage[margin=1.1in]{geometry}
\usepackage{amsmath,amssymb,amsthm,amsfonts,mathrsfs,mathtools}
\usepackage{enumitem}
\usepackage[colorlinks,linkcolor=blue,urlcolor=blue,citecolor=blue]{hyperref}
\usepackage{microtype}

\theoremstyle{definition}
\newtheorem{conjecture}{Conjecture}[section]
\newtheorem{problem}[conjecture]{Problem}
\newtheorem{question}[conjecture]{Question}
\theoremstyle{remark}
\newtheorem*{note}{Note}

%% ---- macro stubs -------------------------------------------------------
%% Statements are lifted verbatim from arbitrary papers, each with its own
%% preamble. These stubs make undefined macros render visibly instead of
%% breaking the build. Statements marked [macro] below should be checked.
__STUBS__
%% -----------------------------------------------------------------------

\title{Open Problems from arXiv}
\author{Generated by Open Math Problems Lab}
\date{__DATE__}

\begin{document}

\begin{abstract}
__ABSTRACT__
\end{abstract}

\maketitle
\tableofcontents

__BODY__

\end{document}
"""


# The model writes prose with literal Unicode maths in it, which Latin Modern
# has no glyph for. Translate rather than drop, so meaning survives.
UNICODE_MATH = {
    "≡": r"\equiv", "≥": r"\geq", "≤": r"\leq", "≠": r"\neq", "≈": r"\approx",
    "→": r"\to", "←": r"\leftarrow", "↦": r"\mapsto", "⇒": r"\Rightarrow",
    "∈": r"\in", "∉": r"\notin", "⊆": r"\subseteq", "⊂": r"\subset",
    "∪": r"\cup", "∩": r"\cap", "∅": r"\emptyset", "∞": r"\infty",
    "∀": r"\forall", "∃": r"\exists", "∑": r"\sum", "∏": r"\prod",
    "√": r"\sqrt{}", "×": r"\times", "·": r"\cdot", "±": r"\pm",
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\varepsilon", "θ": r"\theta", "λ": r"\lambda", "μ": r"\mu",
    "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "φ": r"\varphi",
    "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega", "Δ": r"\Delta",
    "Γ": r"\Gamma", "Σ": r"\Sigma", "Ω": r"\Omega", "Φ": r"\Phi",
    "⌈": r"\lceil", "⌉": r"\rceil", "⌊": r"\lfloor", "⌋": r"\rfloor",
    "ℕ": r"\mathbb{N}", "ℤ": r"\mathbb{Z}", "ℚ": r"\mathbb{Q}",
    "ℝ": r"\mathbb{R}", "ℂ": r"\mathbb{C}", "𝔽": r"\mathbb{F}",
}


def latex_escape_prose(s: str) -> str:
    """Make model-written prose safe to compile.

    Two hazards, both observed in real output:
      * literal Unicode maths -- no glyph in Latin Modern, hard error
      * bare ^ and _ OUTSIDE math mode, e.g. "roughly 10^15 classes"

    The prose deliberately contains inline math like $X_G$, so ^ and _ must be
    escaped only in the non-math spans. Split on $...$ and treat the halves
    differently.
    """
    for u, tex in UNICODE_MATH.items():
        s = s.replace(u, f"${tex}$" if "$" not in s[:0] else f"${tex}$")

    parts = re.split(r"(\$[^$]*\$)", s)   # keep the $...$ groups
    for i, part in enumerate(parts):
        if part.startswith("$") and part.endswith("$") and len(part) > 1:
            continue                        # inside math: leave alone
        parts[i] = (part.replace("&", r"\&").replace("%", r"\%")
                        .replace("#", r"\#").replace("~", r"\textasciitilde{}")
                        .replace("^", r"\textasciicircum{}").replace("_", r"\_"))
    return "".join(parts)


def unknown_macros(text: str) -> set[str]:
    return {m for m in re.findall(r"\\([a-zA-Z]+)", text) if m not in PROVIDED}


def load_problems() -> list[dict]:
    """Gate-passing assessments joined back to their statement and paper."""
    skip = backtest_stems()
    out = []
    for path in sorted(ASSESSMENTS.glob("*.json")):
        if path.name.startswith(".") or path.stem in skip:
            continue
        a = json.loads(path.read_text())
        if not a.get("gate_pass"):
            continue
        m = re.match(r"(.+)_(\d+)$", path.stem)
        if not m:
            continue
        paper, idx = m.group(1), int(m.group(2))
        ext = EXTRACTIONS / f"{paper}.json"
        if not ext.exists():
            continue
        doc = json.loads(ext.read_text())
        sts = doc.get("statements", [])
        if not 0 < idx <= len(sts):
            continue
        st = sts[idx - 1]

        meta_path = META / f"{paper}.json"
        cats = []
        if meta_path.exists():
            cats = json.loads(meta_path.read_text()).get("categories") or []
        out.append({**a, "statement": st, "paper": paper,
                    "title": doc["_meta"].get("title", ""),
                    "key_results": doc.get("key_results", []),
                    "category": cats[0] if cats else "uncategorised"})
    return out


def render_problem(p: dict, flagged: list[str]) -> str:
    st, a = p["statement"], p
    env = ("conjecture" if (st.get("environment") or "").startswith("conj")
           else "question" if (st.get("environment") or "").startswith("quest")
           else "problem")
    who = st.get("attributed_to")
    head = f"[{latex_escape_prose(who)}]" if who else ""

    risky = unknown_macros(st["verbatim"])
    if risky:
        flagged.append(f"{p['paper']}: " + ", ".join(sorted(f"\\{m}" for m in risky)))

    lines = [f"\\begin{{{env}}}{head}", st["verbatim"].strip(), f"\\end{{{env}}}", ""]

    note = [f"\\emph{{Stated in}} \\href{{https://arxiv.org/abs/{p['paper'].rstrip('v0123456789') or p['paper']}}}"
            f"{{arXiv:{p['paper']}}}, \\emph{{{latex_escape_prose(p['title'])}}}."]
    if a.get("frontier_status") == "known" and a.get("frontier_quote"):
        note.append(f"The paper reports: ``{latex_escape_prose(a['frontier_quote'].strip())}''")
        if a.get("frontier_smallest_open"):
            note.append(f"Smallest open case: {latex_escape_prose(a['frontier_smallest_open'])}")
    else:
        note.append("No verification frontier is stated in the source; establishing "
                    "how far the problem has been checked is the first task.")
    if a.get("finite_witness"):
        note.append(f"\\textbf{{What to construct:}} {latex_escape_prose(a['finite_witness'])}")
    risk = risk_sentence(a.get("argument", ""))
    if risk:
        note.append(f"\\textbf{{Main risk:}} {latex_escape_prose(risk)}")
    note.append(f"\\textsl{{Machinery: {a['machinery_depth']}. "
                f"Prior computation: {a['prior_computation']}. "
                f"Attention: {a['attention']}.}}")

    lines += [r"\begin{note}", " ".join(note), r"\end{note}", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=30, help="how many problems (default 30)")
    ap.add_argument("--category", help="restrict to one arXiv category")
    ap.add_argument("--compile", action="store_true", help="run a LaTeX engine if available")
    ap.add_argument("--out", type=Path, default=OUT / "collection.tex")
    args = ap.parse_args()

    problems = load_problems()
    if not problems:
        print("no Gate-passing assessments found — run scripts/try_assess.py first",
              file=sys.stderr)
        return 1
    if args.category:
        problems = [p for p in problems if p["category"] == args.category]

    total_available = len(problems)
    problems.sort(key=sort_key)
    problems = problems[:args.top]

    by_cat = defaultdict(list)
    for p in problems:
        by_cat[p["category"]].append(p)

    flagged: list[str] = []
    body = []
    for cat in sorted(by_cat, key=lambda c: (-len(by_cat[c]), c)):
        body.append(f"\\section{{{CATEGORY_NAMES.get(cat, cat)}}}")
        body.append(f"\\noindent\\textsl{{arXiv category: \\texttt{{{cat}}}}}\\medskip\n")
        body += [render_problem(p, flagged) for p in by_cat[cat]]

    stubs = sorted({m for p in problems for m in unknown_macros(p["statement"]["verbatim"])})
    stub_tex = "\n".join(
        rf"\providecommand{{\{m}}}{{\ensuremath{{\mathrm{{{m}}}}}}}" for m in stubs
    ) or "% none needed"

    abstract = (
        f"{len(problems)} open problems selected from {total_available} that passed an "
        f"automated screen for having a \\emph{{finite witness}}: a concrete finite object "
        f"whose construction or exhaustive absence would constitute genuine progress. "
        f"Problems asking only for an asymptotic bound are excluded, since no finite "
        f"computation can settle them. Each entry records the statement verbatim from its "
        f"source, the verification frontier where the source states one, and the object a "
        f"search would look for. Ordered by how ready each problem is to be attacked, not "
        f"by importance or by likelihood of success."
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    tex = (TEMPLATE
           .replace("__STUBS__", stub_tex)
           .replace("__DATE__", date.today().isoformat())
           .replace("__ABSTRACT__", abstract)
           .replace("__BODY__", "\n".join(body)))
    args.out.write_text(tex)

    print(f"wrote {args.out.relative_to(ROOT)}  "
          f"({len(problems)} problems, {len(by_cat)} sections, {len(tex):,} bytes)")
    for cat in sorted(by_cat, key=lambda c: -len(by_cat[c])):
        print(f"  {CATEGORY_NAMES.get(cat, cat):<28} {len(by_cat[cat])}")
    if stubs:
        shown = ", ".join("\\" + m for m in stubs[:10])
        print(f"\n{len(stubs)} undefined macro(s) stubbed so the file compiles: {shown}"
              + (" ..." if len(stubs) > 10 else ""))
    if flagged:
        print(f"\n{len(flagged)} statement(s) use macros from their source preamble and "
              f"may render oddly — check these by hand:")
        for f in flagged[:10]:
            print(f"  {f}")

    if args.compile:
        engine = next((e for e in ("tectonic", "latexmk", "pdflatex", "xelatex")
                       if shutil.which(e)), None)
        if not engine:
            print("\nno LaTeX engine found. Either:\n"
                  "  brew install tectonic      # single binary, ~50MB\n"
                  "  or upload digest/collection.tex to overleaf.com", file=sys.stderr)
            return 0
        cmd = ([engine, args.out.name] if engine == "tectonic"
               else [engine, "-pdf", "-interaction=nonstopmode", args.out.name]
               if engine == "latexmk" else
               [engine, "-interaction=nonstopmode", args.out.name])
        for _ in range(2 if engine in ("pdflatex", "xelatex") else 1):  # TOC needs two passes
            r = subprocess.run(cmd, cwd=args.out.parent, capture_output=True, text=True)
        pdf = args.out.with_suffix(".pdf")
        if pdf.exists():
            print(f"\ncompiled {pdf.relative_to(ROOT)} with {engine}")
        else:
            print(f"\n{engine} failed. Last 20 lines:", file=sys.stderr)
            print("\n".join(r.stdout.splitlines()[-20:]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
