<!--
Stage 1 extraction prompt. SOURCE, not a build artifact (ADR-0006).
Version: 1
Model: claude-haiku-4-5, Batch API, structured output against prompts/extract.schema.json

Placeholders substituted by the pipeline: {{ARXIV_ID}}, {{TITLE}}, {{TEX}}

Design note: stage 1 optimises for RECALL. The Gate (stage 2) does the
filtering, and it is strict. A Statement wrongly extracted here costs a
fraction of a cent to discard later; a Statement missed here is invisible
forever. When in doubt, extract it.
-->

You are reading the LaTeX source of a mathematics preprint and cataloguing every open problem it states. You are **not** judging whether any problem is interesting, important, or solvable — a later stage does that. Your only job is to find them and record faithfully what the paper says.

## Paper

- arXiv ID: `{{ARXIV_ID}}`
- Title: {{TITLE}}

## What counts as a Statement

Extract a Statement for each of these:

1. **A formal environment** posing something unresolved — `\begin{conjecture}`, `\begin{problem}`, `\begin{question}`, `\begin{openproblem}`, and any similarly-named custom environment.
2. **A conjecture stated in prose** — "we conjecture that…", "we believe that…", "it seems likely that…", "we expect that…".
3. **A question posed in prose** — "it would be interesting to determine…", "we ask whether…", "does there exist…?", "can this bound be improved?".
4. **A problem the paper flags as unresolved** — "remains open", "is not known", "we have been unable to determine", "the general case is open".
5. **Someone else's problem cited as still open** — "the conjecture of Frankl [12] remains open". Extract these; the attribution is exactly the signal we need.
6. **Anything in a section named for open problems** — "Open Problems", "Further Questions", "Concluding Remarks", "Future Work". Read these sections especially carefully; they are dense with Statements that appear in no formal environment.

**Read `remark` environments with the same care.** A `\begin{remark}` is not a problem environment, but authors routinely park their most interesting unsolved questions in one, immediately after the result that provoked them. These are often the best Statements in the paper. Record `environment` as the enclosing environment name (`remark`) — that field says where the text sat, not that it was formally posed.

Extract each distinct problem separately, and note that one sentence can hold several. "It would be interesting to find the smallest counterexample, as well as infinite families of counterexamples" is **two** Statements: the smallest counterexample, and the infinite families. Likewise, if one `\begin{conjecture}` block has parts (a), (b) and (c) that could be settled independently, that is three Statements.

## What does not count

- **Rhetorical or expository questions** used to motivate a section — "But what happens when $n$ is odd? We answer this in Theorem 3.1."
- **Exercises and worked examples.**
- **A theorem the paper proves.** A proved result is not an open problem.
- **A conjecture named but never stated.** If a paper refers to "the Linear Hadwiger Conjecture" as background or as the target of some reduction, but never says what it asserts, there is nothing to put in `verbatim` — skip it. A name in a keyword list, an abstract, or a citation is not a statement of a problem. Extract rule 5 above only when the paper actually gives you the claim.

Two exceptions worth being careful about, because both carry signal we need:

**The paper settles something.** If it claims to resolve a conjecture that was open elsewhere — "we prove the conjecture of Stanley [17]", "we give a counterexample to Conjecture 2.37 of [Mphd]" — **extract it**, `stated_as: resolved_here`. That record is how we learn a problem should stop being offered as open. Extract it even though the conjecture is now dead.

**Someone else settled it.** Use `resolved_elsewhere` only when the paper reports the resolution as an event, naming who did it — "conjectured by Stanley and Stembridge in 1993, and verified by Hikita in 2024". Do not use it for every passing reference to a known theorem; if the paper is simply citing established results to build on, that is background, not a Statement.

## Fields

For each Statement:

**`claim`** — one sentence, in your own words, stating what would have to be done to settle *this* problem. Plain prose; expand the notation enough to be readable on its own, since this is what a human reads first in the digest.

This field is what distinguishes problems when one sentence holds several. For "it would be interesting to find the smallest counterexample, as well as infinite families of counterexamples", the two Statements share a `verbatim` but have different claims: *"Find the smallest counterexample to Stanley's claw-free conjecture"* and *"Construct an infinite family of counterexamples to Stanley's claw-free conjecture"*. Two Statements with the same `claim` are the same problem and should have been one.

**`verbatim`** — the problem statement copied from the source, LaTeX intact. Copy it; do not paraphrase, translate, or clean it up. Include the full statement but not the surrounding discussion. When one sentence yields several Statements, each carries the same full sentence here — `claim` is what tells them apart.

**`context`** — the surrounding text needed to make the statement interpretable: enough of the preceding discussion to establish what the symbols mean, plus any immediately following remarks about difficulty or partial progress. A few hundred words at most. Copy, don't summarise.

**`location`** — where it sits, as a reader would cite it: `Conjecture 1.2`, `Question 4.7`, `Section 6, unnumbered`.

You are reading source, not a compiled document, so `\ref` and `\label` numbers are not resolved and you cannot know that a block is "Conjecture 1.2". When the number is not determinable, give the environment plus its label — `conjecture [conj:stanley claw-free]` — rather than falling back to the section name. The label identifies it exactly; a section name does not.

**`environment`** — the LaTeX environment name if it is in one (`conjecture`, `problem`, `question`), otherwise `null`.

**`stated_as`** — the paper's own claim about status:
- `open` — presented as unresolved
- `partially_resolved` — the paper proves a special case or partial bound but not the whole thing
- `resolved_here` — this paper claims to settle it
- `resolved_elsewhere` — the paper notes that someone else has settled it

**`attribution_kind`** — who the paper credits:
- `original` — the authors are proposing it themselves
- `attributed` — credited to a named person or paper
- `folklore` — called well known, classical, or folklore with no specific credit
- `unclear` — you cannot tell from the text

**`attributed_to`** and **`attributed_citation`** — the name and the citation as they appear in the text (`Stanley`, `[17]`; or `Erdős and Ko`, `\cite{EKR61}`). `null` when the paper does not say.

> **This is the one rule to get right.** These fields must be copied from *this paper's text*. If the paper does not name a source, leave them `null` — even when you recognise the conjecture and could name its originator from your own knowledge. A downstream signal depends on measuring what papers actually say, and a helpfully-supplied attribution silently corrupts it.

**`notes`** — anything a later reader needs: an ambiguity you resolved, a reason you were unsure whether to extract it, a partial result stated nearby. Otherwise `null`.

## Also record

**`key_results`** — the concrete objects and numeric bounds this paper establishes, one short line each. These are what tell a later reader where a search should start, so be specific and quantitative: *"exhibits two claw-free line graphs on 12 vertices with a negative Schur coefficient ($-64$ and $-40$)"*, *"proves every $K_t$-minor-free graph with $d(G) \geq Ck$ has a $k$-connected subgraph on $\leq C^2 t\log^2 t$ vertices"*, *"verifies the conjecture for all $n \leq 9$"*.

Include a line whenever the paper states a vertex count, an order, a threshold, a verified range, or names an explicit object it constructed. Omit qualitative claims — "improves the bound" without the bound is useless here. Empty array if the paper establishes nothing concrete.

**`open_problems_section`** — `true` if the paper has a section devoted to open problems or future work, else `false`.

**`extraction_confidence`** — `high` if the source was clean and you are confident you found everything; `low` if the LaTeX was fragmentary, heavily macro-laden, truncated, or otherwise hard to read. Say why in `notes_on_paper`.

## Source

```latex
{{TEX}}
```
