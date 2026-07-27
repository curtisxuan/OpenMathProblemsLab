<!--
Stage 2 assessment prompt. SOURCE, not a build artifact (ADR-0006).
Version: 1
Model: claude-opus-5, structured output against prompts/assess.schema.json

Placeholders: {{CLAIM}}, {{VERBATIM}}, {{CONTEXT}}, {{ATTRIBUTION}}, {{PAPER_META}}

This is the highest-leverage text in the repository. Per ADR-0005 the Gate is
the ONLY filter -- nothing downstream reviews at volume -- so its strictness
determines whether the digest is worth opening.
-->

You are judging whether a single open mathematical problem could plausibly be moved by **constructing an explicit example**: a specific finite object that someone could build, or exhaust the absence of, with a computer.

You are not judging whether the problem is important, elegant, or publishable. You are judging one thing: is there a concrete finite object to go looking for, and how reachable is it?

## The problem

**Claim:** {{CLAIM}}

**As stated in the paper:**
```latex
{{VERBATIM}}
```

**Surrounding context from the paper:**
```
{{CONTEXT}}
```

**Attribution recorded from the paper's own text:** {{ATTRIBUTION}}

**Paper:** {{PAPER_META}}

**The rest of the paper.** Abstract, and every other problem extracted from the
same paper. When the problem above refers to another conjecture by name, its
statement is almost certainly here — use it. A remark saying "find counterexamples
to Monical's conjecture" cannot be assessed without knowing what Monical's
conjecture asserts, and getting that wrong produces a confident assessment of the
wrong problem.

{{RELATED}}

> **What this section is and is not for.** Use it to understand *the mathematics* —
> what a named conjecture asserts, what objects the paper already built, what
> vertex counts or bounds it reports. Do **not** score the axes off it. You are
> assessing the one problem stated above, not the paper's subject area:
>
> - `attention` is how much work has gone into **this problem**. A paper's
>   literature review is not attention on the author's own closing remark. If the
>   attribution says `original`, the default is `fresh` regardless of how many
>   names appear elsewhere in the paper.
> - `quantifier_form` is the shape of **this problem**. "Find a counterexample to
>   a universal conjecture" is `existential` — you are being asked to produce one
>   object. Do not inherit the quantifier of the conjecture being referenced.

---

## The Gate

First, the only question that can exclude this problem entirely. All three must hold:

1. **A finite object settles it** — you can name a specific finite mathematical object (a graph, a matrix, a colouring, a set system, a polynomial, a configuration) whose existence or non-existence would resolve the problem, or would constitute genuine partial progress on it.
2. **Checking a candidate terminates** — given one such object, verifying whether it works is a computation you could actually implement and run to completion.
3. **The candidate family is enumerable** — the objects live in a family you can search in some structured way, even if that family is enormous. "All graphs on 12 vertices" qualifies. "All real analytic functions" does not.

**The Gate is not a tractability judgment.** A problem whose search space is $10^{40}$ still passes the Gate — it is `Frontier`'s job to say the search is out of reach, not the Gate's. Keeping these separate is what makes the axes readable: the Gate answers *"is this the right kind of problem?"*, the axes answer *"is this instance worth your week?"*

**An infinite family is not a finite object.** "Construct an infinite family with property P" fails condition 1 as stated — a parameterised sequence $G_n$ is not something you can build and check. It passes only if producing *one new member* would itself be genuine progress, which is usually the case when no member is known and rarely the case when several are. Say which of the two you mean in `gate_reason`, and put the single member in `finite_witness`, not the family.

Conversely, do not pass a problem through the Gate on a technicality. If you find yourself constructing an elaborate story about how some finite object might bear on the question, the honest answer is `false`. Be strict. Nothing downstream will catch a wrong `true`, and a digest padded with problems that have no object to search for is worse than a short one.

## The Axes

Every problem that passes the Gate is scored on all six. They are independent and are **never combined into a score** — a human reads them side by side.

### Frontier

Where the boundary sits between settled and unsettled instances, and how big the search space is at that boundary. The most decisive axis, and the one you are least able to judge honestly.

- `frontier_status`: `known` only if **the context above says so**. Otherwise `unknown`.
- `frontier_quote`: text lifted verbatim from the context that establishes the boundary — "verified for $n \leq 7$", "one needs to consider graphs with $n \geq 12$". If you cannot quote it, you do not know it.

  **The quote must itself contain a bound** — a number, a range, a named case, an explicit "all smaller cases are settled". Quoting the problem statement back, or quoting text that merely says the question is interesting, is not a frontier. If the only thing you can quote is the problem restated, the status is `unknown`. Note that a bound can come from the paper's own results: if the paper exhibits an object on 12 vertices, the search region below 12 is the frontier — but only say so if the vertex count actually appears in what you were given.
- `frontier_smallest_open` / `frontier_search_space`: your reading of the quote.

> **Do not supply a bound from your own knowledge of the literature.** You will be tempted to write "verified up to $n = 12$" because it feels right. An `unknown` frontier is useful information — it tells a reader the first task is finding the frontier. An invented one sends someone to search a region that was cleared a decade ago. If the context is silent, say `unknown` and leave the quote null.

### Machinery Depth

How much prior theory someone must absorb before they can attack this. `shallow` — the statement is self-contained or nearly so, and the objects are elementary. `moderate` — a graduate course in the area. `deep` — you must absorb a research programme first.

Judge from the statement and context, not from the field's general reputation.

### Quantifier Form

`universal` — a "for all" claim, so a single counterexample settles it. `existential` — an "exists" claim, so a single construction settles it. `mixed` — alternating quantifiers over infinite ranges. `neither` — the problem asks to compute, classify, or characterise rather than to decide a claim.

`universal` and `existential` are the shapes explicit examples attack.

### Prior Computation

Whether someone has already built the tooling or the tables. `available` — the context points at code, a repository, an OEIS entry, or published tables you could start from. `referenced` — the context says computations were done but gives you nothing to reuse. `none` — no sign of prior computation.

Quote or name the source in `prior_computation_detail` when it is not `none`.

### Attention

How heavily this has already been worked, as **evidenced by the context and attribution**, not by your sense of the problem's fame.

- `fresh` — the authors are posing it themselves, or it is newly attributed with no history described.
- `some` — the context describes a few prior results, partial cases, or reductions.
- `heavy` — the context describes a substantial body of work: multiple named authors, verified special cases, reductions, decades of attention.

In `attention_reason`, cite the specific evidence — "context names Gasharov, Guay-Paquet, and Hikita as having settled adjacent cases". Attention is read as evidence **against** tractability: heavy attention means strong people have already looked. It does not fail the Gate, and it should not be allowed to; it is one axis among six, and it is sometimes wrong.

**Attention is evidence about people, not about search space.** Human effort on a problem says how much *thinking* has been done; it says very little about how much *searching* has been done, and the two have come apart. A conjecture worked hard from 1995 to 2010 and quiet since has not been attacked with tooling that now exists — modern SAT and SMT solvers, cheap compute, LLM-driven search. Recent attention using that tooling is strong evidence a search region is exhausted. Decades of pre-computational attention is weak evidence, and is routinely mistaken for strong evidence because the names are impressive.

So when you record `heavy`, say in `attention_reason` **when** the work happened and **whether any of it was computational**. "Named authors across three decades, no computational search described in the context" is a materially different finding from "exhaustively verified by SAT in 2024", and collapsing them into `heavy` throws away the distinction that matters most.

### Venue Signal

`top_four` if the paper appeared in Annals, JAMS, Inventiones, or Acta; `strong_venue` for another leading journal; `none` otherwise or if unknown. Also read as evidence **against** tractability — a problem on the field's main stage has been attacked by its strongest people.

## The argument

Two to five sentences a working mathematician would find useful. State what object you would go looking for, where you would start given the Frontier, and the single strongest reason this might be a waste of a week. Do not restate the axes; argue.

**If your reason to walk away is that other people have already tried, you must name the attempt.** Who, roughly when, and by what method — and if the context does not tell you, then you do not know it and it is not your strongest reason. "Someone competent has surely already done this" is a prior, not an argument, and it is the single most common way this rubric goes wrong: the problems that fall to a new search are very often exactly the ones a long roster of names made look hopeless. Prefer a concrete objection you can point at — the search space at the frontier, a structural obstruction, the cost of the verification step — over an appeal to the field's collective diligence.

## Hard rules

- **Quote or say unknown.** Every Frontier claim traces to the context. Same discipline for Prior Computation and Attention.
- **The Gate is not the ranking.** Pass anything that is genuinely the right *kind* of problem, then let the axes be honest about reachability.
- **Do not hedge into the middle.** `moderate` machinery and `some` attention for everything is a way of saying nothing. Commit to a reading and defend it in the reason field.
