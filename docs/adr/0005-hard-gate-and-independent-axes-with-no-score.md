# A hard Gate and independent Axes, with no combined score

A Conjecture must pass one binary Gate — does a Finite Witness exist? — to reach the Digest at all; everything that passes is then judged on six Axes that are deliberately *not* rolled up into a single number. A scalar would be trivially sortable, but it hides its own reasoning, buries the weighting as an invisible arbitrary choice, and is far harder to calibrate than six separate judgments. If a future reader is tempted to add a `solvability_score` column, this is why there isn't one.

## Consequences

The Gate is doing all the filtering, because no human reviews the output at volume (see ADR-0007). Its prompt is therefore the highest-leverage text in the repository and should be strict: eight Conjectures a month that survive scrutiny beats eighty that need triage.

Frontier is the most decisive Axis and the one a model is least able to judge honestly — asked where the smallest open case sits, it will confabulate a bound. Every Frontier claim must therefore quote the Paper it came from, and record `unknown` when the Paper is silent. An unknown Frontier is useful; an invented one poisons the ranking.
