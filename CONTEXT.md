# Open Math Problems Lab

A funnel that reads mathematics preprints, extracts the open problems stated in them, and judges which of those problems could plausibly be moved by constructing an explicit example. Its output is a short ranked list of problems worth a week of a human's attention — not a comprehensive catalogue.

## Language

### Source Material

**Corpus**:
The set of Papers in scope for one run, fixed by arXiv category and submission window.

**Paper**:
One arXiv e-print in the Corpus, read from its LaTeX source rather than its PDF or abstract.
_Avoid_: article, preprint, publication

**Venue of Record**:
The journal that published a Paper, matched by DOI. A property *of* a Paper, never a source *of* Papers.
_Avoid_: journal, publication venue

### Problems

**Statement**:
A single verbatim occurrence of an open problem as it appears in one Paper, carrying the location and surrounding context it was found in.
_Avoid_: problem, mention, occurrence, extraction

**Conjecture**:
The canonical mathematical claim that one or more Statements express. All judgment attaches to a Conjecture; none attaches to a Statement.
_Avoid_: problem, open problem, question, claim

**Attribution**:
Whom a Statement credits its claim to, read from the Paper's own citation text rather than inferred from anywhere else.
_Avoid_: citation, credit, provenance

**Resolution Claim**:
A Paper's assertion that it settles a Conjecture that was stated as open elsewhere. Evidence that a Conjecture should no longer be offered as open.
_Avoid_: proof, solution, closure

### Assessment

**Finite Witness**:
A finite mathematical object whose explicit construction — or whose exhaustive absence across a bounded family — would constitute genuine progress on a Conjecture. The central concept of the project.
_Avoid_: example, counterexample, certificate

**Gate**:
The single binary admission test: does a Finite Witness exist for this Conjecture? A Conjecture that fails the Gate never reaches the Digest, whatever its Axes say.
_Avoid_: filter, threshold, cutoff

**Axis**:
One of the six independent dimensions on which a gated Conjecture is judged. Axes are read side by side and never combined into a single score.
_Avoid_: criterion, metric, dimension, factor

**Frontier**:
The boundary between the instances of a Conjecture already settled and the smallest instance still open, together with the size of the search space at that boundary.
_Avoid_: bound, progress, state of the art

**Machinery Depth**:
How much prior theory a reader must absorb before the Conjecture's statement can be understood and attacked.
_Avoid_: difficulty, complexity, prerequisites

**Quantifier Form**:
Whether a Conjecture is universal, so one counterexample settles it, or existential, so one construction settles it. A Conjecture that is neither rarely admits a Finite Witness.

**Prior Computation**:
Published tables, code, or OEIS entries that let an attack begin at the Frontier instead of rebuilding toward it.
_Avoid_: existing work, related work

**Attention**:
How heavily a Conjecture has already been worked, inferred from how often Papers attribute it to prior work rather than state it fresh. Read as evidence *against* tractability.
_Avoid_: popularity, prominence, citation count

**Assessment**:
A model's judgment of one Conjecture: the Gate outcome, a value per Axis, and the argument supporting each.
_Avoid_: score, rating, evaluation

**Verdict**:
A human's judgment of one Conjecture, recorded in the same shape as an Assessment so the two can be set against each other.
_Avoid_: review, opinion, override

**Digest**:
The generated ranked report of Conjectures that passed the Gate. The funnel's deliverable.
_Avoid_: shortlist, report, output

### Calibration

**Calibration Case**:
A Conjecture whose real-world outcome is already known, run blind through the rubric to test whether the Axes predict anything.
_Avoid_: test case, benchmark, control

**Pilot Attack**:
A timeboxed manual attempt to construct a Finite Witness for a top-ranked Conjecture. Its outcome becomes a Calibration Case.
_Avoid_: experiment, trial, solve attempt
