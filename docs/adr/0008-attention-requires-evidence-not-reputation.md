# The Attention axis requires evidence of search, not a roster of names

The rubric's `attention` axis reads prior work as evidence against tractability, and in early testing that reasoning was wrong every time we could check it. Across four problems with known outcomes, all four of the rubric's stated reasons to walk away were pessimistic and all four were false — "brute force has plainly been machine-checked to whatever $n$ was reachable" (it had not), "the candidate pool may be empty by construction" (it was not). Each rested on the same inference: many distinguished names have looked, therefore the reachable space is exhausted.

That inference no longer holds. Human attention measures how much *thinking* has been done; it says little about how much *searching* has been done, and the two came apart once SAT solvers, cheap compute, and LLM-driven search became available. Both conjectures in our calibration set had stood for decades against exactly that roster of names, and both fell to an LLM in under 90 minutes.

`prompts/assess.md` therefore requires the assessment to record *when* prior work happened and *whether any of it was computational*, and forbids "others have surely tried" as a walk-away argument unless the attempt can be named.

## Consequences

The fix demands evidence for pessimism rather than mandating optimism. Flipping the prior would install the opposite bias, which is worse: a rubric that talks itself into optimism wastes the weeks this project exists to protect.

**This was tuned on the calibration set, which is the overfitting we said we would avoid.** The four cases motivating it are the same four that validate it, so it is not independently confirmed. Treat the change as provisional until control cases from outside `arXiv:2607.21508v1` exercise it. If a later backtest shows the rubric now waving through heavily-searched dead ends, this is the first thing to revisit.
