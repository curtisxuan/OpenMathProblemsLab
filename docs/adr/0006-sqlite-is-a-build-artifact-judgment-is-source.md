# SQLite is a build artifact; judgment is source

The database holding Statements, Conjectures, and Assessments is gitignored and rebuildable from cached LaTeX plus a re-run costing roughly $20. Everything hand-authored — Verdicts, the Calibration Case set, the rubric prompt itself — lives in git-tracked files keyed by Conjecture and is loaded into the database on build. The split is by *regenerability*, not by storage technology: machine output is cheap and churns, human judgment is irreplaceable and deserves diffs.

## Consequences

A pipeline re-run can never clobber a Verdict, because Verdicts are not stored where the pipeline writes. Committing the database instead would have been simpler with nothing to reconcile on load, but every run would rewrite an opaque binary that git cannot show you the changes in.
