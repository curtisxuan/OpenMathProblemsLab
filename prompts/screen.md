<!--
Gate screen. SOURCE, not a build artifact (ADR-0006).
Version: 1
Model: claude-haiku-4-5, structured output against prompts/screen.schema.json

Placeholders: {{CLAIM}}, {{VERBATIM}}

Cheap pre-filter in front of the full Opus assessment. Answers ONLY the Gate
question, on ~$0.005 per problem instead of ~$0.10. Everything that passes gets
the full six-axis treatment; everything that fails is dropped.

Deliberately given only the claim and the verbatim statement -- no context, no
related problems. The Gate turns on the SHAPE of the question, which is visible
in the statement alone, and sending context would cost most of the saving.

Because a wrong reject is invisible downstream, this prompt errs toward passing
when genuinely unsure. The full assessment is strict; this one is a sieve, not
a judge.
-->

You are deciding one thing about a mathematical problem: **is there a finite object someone could construct, whose existence or absence would settle it?**

You are not judging whether the problem is interesting, important, tractable, or worth anyone's time. Only whether it has the right *shape*.

## The problem

**What would settle it:** {{CLAIM}}

**As stated in the paper:**
```latex
{{VERBATIM}}
```

## Pass if all three hold

1. **A finite object settles it** — you can name a specific finite thing (a graph, matrix, colouring, set system, polynomial, configuration, integer tuple) whose existence or non-existence resolves the problem, or constitutes real partial progress.
2. **Checking one candidate terminates** — given such an object, verifying it is a computation that finishes.
3. **The candidates are enumerable** — they live in a family you could search in some structured way, however large. "All graphs on 12 vertices" qualifies. "All continuous functions" does not.

## First, the mistake to avoid

**A universal claim is settled by one counterexample.** Do not ask only whether a finite object could *prove* the statement — almost never, for any "for all $n$" claim. Ask whether a finite object could **refute** it. That is the direction this project attacks from, and rejecting every universal statement because no finite object proves it would throw away nearly everything worth having.

*"$R(C_n, K_m) = (n-1)(m-1) + 1$ for all $n, m$"* covers infinitely many cases and is settled the moment you exhibit one pair where it fails. **Pass it.**

## Fail these

- **Claims with an unquantified escape hatch.** This is the real asymptotic test, and it is narrower than "mentions $n \to \infty$". Fail when the statement is hedged such that **no finite instance could contradict it**:
  - $O(\cdot)$ or $\Omega(\cdot)$ bounds — *"decomposes into $O(n)$ cycles"*. Any single finite graph is consistent with some constant, so no counterexample exists.
  - $o(1)$ or $(c + o(1))$ terms — *"the threshold is $(9/64 + o(1))t^2$"*. Same reason.
  - "for sufficiently large $n$", "for some constant $C$", "for all $n \geq C|H|$" where $C$ is never pinned down. A small counterexample is always dismissible as below the threshold.

  Contrast with an **exact** claim over infinitely many cases — a specific formula, a specific constant, a stated bound with no hidden slack. Those pass: one failing instance kills them.

  The test is one question: **could a single concrete instance contradict this statement?** If yes, pass. If the statement can always absorb a bad instance by adjusting a hidden constant, fail.
- **Build a theory.** "Characterise all…", "develop a framework for…", "explain why…", "find a conceptual proof of…".
- **Infinite families**, unless producing one *new member* would itself be progress — which is usually true when none is known and rarely true when several are.
- **Anything over an uncountable domain** — real functions, measures, general metric spaces.

## When unsure

**Pass it.** A wrong pass costs about ten cents downstream, where a strict assessment will catch it. A wrong reject is silent and permanent — nobody ever sees the problem again. These are not symmetric errors.

Keep `reason` to one sentence. If you pass, name the object in `witness`.
