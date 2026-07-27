# Reading an assessment

An Assessment is not a recommendation and it is not a score. It is six
independent readings plus an argument, and the whole design assumes a human
decides ([ADR-0005](adr/0005-hard-gate-and-independent-axes-with-no-score.md)).
This is how to decide quickly.

## Read in this order

Not top to bottom. Most assessments can be dismissed in about fifteen seconds.

**1. Gate.** Binary. `FAIL` means there is no finite object to go looking for —
stop reading, and check the `gate_reason` only if you disagree. `PASS` means the
problem is the right *shape*; it says nothing about whether it is worth doing.

**2. `frontier_status`.** The single most decisive field.

- `unknown` — nobody has told you where the settled region ends. Your first task
  is establishing that, **not** searching. Budget a day for literature and
  tooling before you write any enumeration code. Many `unknown` problems are
  perfectly good; they are just not shovel-ready.
- `known` — go straight to the quote.

**3. `frontier_quote`.** Read the quote itself, not the fields derived from it.
The quote is evidence lifted from a paper. `frontier_smallest_open` and
`frontier_search_space` are the model's *interpretation* of that evidence, and
interpretation is where errors live. If the quote does not contain a number, a
range, or a named settled case, treat the frontier as `unknown` regardless of
what the status field says.

**4. `attention_reason`** — and specifically, whether it describes **searching**
or merely **names**. "Named authors across three decades, no computational
search described" and "exhaustively verified by SAT in 2024" are both `heavy`,
and they mean opposite things for your week
([ADR-0008](adr/0008-attention-requires-evidence-not-reputation.md)).

**5. The argument's last sentence.** Every argument ends with the strongest
reason this is a waste of time. That sentence carries more decision-relevant
information than the five axes above it — *provided* it names something concrete.

**6. Everything else.** `machinery_depth`, `quantifier_form`,
`prior_computation`, `venue_signal` are supporting detail. They rarely change a
decision on their own.

## How much to trust each field

| Field | Trust | Why |
|---|---|---|
| `frontier_quote` | Highest | Lifted text. Verifiable against the paper in seconds. |
| `gate_pass`, `quantifier_form` | High | Structural. You can check them yourself instantly. |
| `finite_witness` | High | Concrete enough to be obviously right or obviously wrong. |
| `attention`, `machinery_depth` | Medium | Genuine judgments. Reasonable people differ. |
| `frontier_smallest_open`, `frontier_search_space` | **Medium-low** | *Derived* from the quote. Re-derive them yourself. |
| `argument` | Most useful, least verifiable | Read it critically; see red flags below. |

## Red flags

Each of these has actually occurred during development.

**`frontier: known` on a quote with no bound.** The quote turns out to be the
problem restated, or text saying the question is interesting. Rule violation —
downgrade to `unknown` yourself.

**The witness describes a different problem than the claim.** Symptom of
context starvation: the problem referenced another conjecture by name and the
rubric did not have its statement. Check that `finite_witness` and `claim` are
about the same thing before trusting anything else in the record.

**The walk-away reason is "people have surely tried" with no attempt named.**
This is a prior wearing an argument's clothes, and it is the rubric's known
failure mode — on every development case with a verifiable answer, this
reasoning was wrong. If it appears without a named attempt, discount it.

**Everything is `moderate` and `some`.** The model hedged instead of committing.
A record with no strong reading anywhere is usually a record built on thin
context; check what it was actually given.

**The frontier quote came from `key_results` rather than the paper.** Stage 1
produced that line, so the provenance is paper → Haiku → quote. It reads like a
citation but carries an extra hop of trust. Verify against the source before
acting on it.

## Worked example

Three problems from the same paper, all `attention: fresh`, all
`machinery: moderate` — the axes that separated them were Gate and Frontier.

**Find the smallest claw-free counterexample.** `PASS`, frontier `known`,
quoting that the paper's own examples sit at 12 vertices with 21 and 22 edges.
So the open region is $n \leq 11$, plus 12 vertices under 21 edges — bounded,
enumerable, with a stated stopping condition. The argument adds two real leads:
both known negatives sit at $s_{3333}$, and both are line graphs, so line graphs
first. Walk-away reason is verification cost, not reputation. **This is what a
shovel-ready problem looks like.**

**Construct an infinite family.** `FAIL` — the object requested is a
parameterised sequence, and no finite computation settles it. The assessment
redirects to the problem above. Correct behaviour: an infinite family is not a
finite witness, though a new *member* would be.

**Find a claw-free counterexample to Monical's conjecture.** `PASS`, frontier
`known`, but read the argument: the pool must be claw-free **and** $s$-positive
**and** non-SNP, and *"you would have no way to distinguish emptiness from an
insufficient search."* Shovel-ready and possibly futile are not contradictory —
this is exactly the case where you read the argument rather than the axes.

## The decision

Roughly:

- **Gate `FAIL`** → discard.
- **Gate `PASS`, frontier `unknown`** → a reading task, not a search task. Worth
  keeping if the claim is interesting; do not schedule compute.
- **Gate `PASS`, frontier `known`, walk-away reason is concrete and survivable**
  → candidate. The verification cost named in the argument is usually the real
  constraint, so cost it before committing.
- **Gate `PASS`, frontier `known`, walk-away reason is reputational** → treat as
  a candidate anyway and check the claim yourself. That reasoning has the worst
  track record of anything in this system.

When you act on one, record what happened in
[`judgment/verdicts.yaml`](../judgment/verdicts.yaml) using the same axes, and
if it was a Pilot Attack put the outcome in
[`judgment/calibration.yaml`](../judgment/calibration.yaml). An attack that is
run but not recorded teaches you something for a week and then evaporates
([ADR-0007](adr/0007-human-assessment-is-an-affordance-and-scope-ends-at-one-pilot-attack.md)).
