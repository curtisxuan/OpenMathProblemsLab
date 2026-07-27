# Attention is read from Attribution text, not derived from clustering

Attention — how heavily a Conjecture has already been worked — is one of our strongest ranking signals, and the obvious way to compute it is to cluster Statements across the Corpus and count. That does not work over a one-month window: a famous conjecture cited once in June is indistinguishable from a brand-new one. Instead the extractor reads Attribution directly off each Paper's own citation text ("a conjecture of Stanley [17]", "Conjecture 1.2 (Frankl)"), which turns a multi-year-corpus problem into a per-Paper extraction problem.

## Consequences

Clustering is left with only the modest job of deduplicating Statements, so we do it cheaply — high-confidence matches on attributed name or paper-plus-problem-number, with unmatched Statements each becoming their own Conjecture. Residual duplicates cost us little because they no longer corrupt the Attention signal. Detecting Resolution Claims falls out of the same extraction, though it pays off only once the Corpus spans years and there is something already in the database to close.
