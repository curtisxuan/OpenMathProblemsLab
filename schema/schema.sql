-- Open Math Problems Lab — database schema.
--
-- This database is a BUILD ARTIFACT (ADR-0006). It is gitignored and can be
-- rebuilt from cached LaTeX plus a pipeline re-run. Nothing hand-authored is
-- stored here as its origin: Verdicts and Calibration Cases live in
-- git-tracked files under judgment/ and are LOADED into these tables on build.
--
-- Vocabulary follows CONTEXT.md. Terms are capitalised there; table names here
-- are the same nouns, singular and lowercased.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Source material
-- ---------------------------------------------------------------------------

CREATE TABLE paper (
    arxiv_id            TEXT PRIMARY KEY,        -- '2606.12345v1'
    title               TEXT NOT NULL,
    authors             TEXT NOT NULL,           -- JSON array
    primary_category    TEXT NOT NULL,           -- 'math.CO'
    categories          TEXT NOT NULL,           -- JSON array
    submitted_at        TEXT NOT NULL,           -- ISO 8601

    -- Venue of Record: a feature of the Paper, matched by DOI. Never a source
    -- of Papers (ADR-0001). Expected to weight NEGATIVELY on tractability.
    doi                 TEXT,
    venue_of_record     TEXT,
    venue_issn          TEXT,

    -- Concrete objects and numeric bounds the Paper establishes, as a JSON
    -- array of short lines. Recorded at extraction because Frontier is the
    -- most decisive axis and the one stage 2 is least able to fill in: a
    -- Statement saying "find the smallest counterexample" is unassessable
    -- unless something records that the Paper already built one on 12 vertices.
    key_results         TEXT NOT NULL DEFAULT '[]',

    tex_sha256          TEXT NOT NULL,
    tex_token_estimate  INTEGER NOT NULL,
    fetched_at          TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Problems
-- ---------------------------------------------------------------------------

-- A Statement is ONE VERBATIM OCCURRENCE of an open problem in ONE Paper.
-- Judgment never attaches here (ADR-0002) — only what the Paper actually says.
CREATE TABLE statement (
    id                  INTEGER PRIMARY KEY,
    arxiv_id            TEXT NOT NULL REFERENCES paper(arxiv_id) ON DELETE CASCADE,

    verbatim            TEXT NOT NULL,           -- LaTeX as it appears
    context             TEXT NOT NULL,           -- surrounding paragraph(s)
    location            TEXT NOT NULL,           -- 'Conjecture 1.2', 'Section 6'
    environment         TEXT,                    -- latex env name, NULL if prose

    -- Resolution Claim: what this Paper says about the problem's status.
    -- 'resolved_here' is the signal that a Conjecture should stop being
    -- offered as open (ADR-0003) — it pays off once the Corpus spans years.
    stated_as           TEXT NOT NULL
                        CHECK (stated_as IN ('open',
                                             'partially_resolved',
                                             'resolved_here',
                                             'resolved_elsewhere')),

    -- Attribution: read from THIS Paper's citation text, never inferred from
    -- model knowledge. Sole input to the Attention axis (ADR-0003).
    attribution_kind    TEXT NOT NULL
                        CHECK (attribution_kind IN ('original',
                                                    'attributed',
                                                    'folklore',
                                                    'unclear')),
    attributed_to       TEXT,                    -- 'Stanley', 'Frankl'
    attributed_citation TEXT,                    -- '[17]', '\cite{Sta95}'

    conjecture_id       INTEGER REFERENCES conjecture(id) ON DELETE SET NULL,

    run_id              INTEGER NOT NULL REFERENCES extraction_run(id),
    extractor_notes     TEXT
);

CREATE INDEX statement_by_paper      ON statement(arxiv_id);
CREATE INDEX statement_by_conjecture ON statement(conjecture_id);
CREATE INDEX statement_by_status     ON statement(stated_as);

-- A Conjecture is the CANONICAL CLAIM one or more Statements express.
-- All judgment attaches here.
CREATE TABLE conjecture (
    id                  INTEGER PRIMARY KEY,
    canonical_statement TEXT NOT NULL,           -- from the representative Statement
    canonical_name      TEXT,                    -- 'Stanley-Stembridge conjecture'

    -- Dedup is deliberately cheap: high-confidence matches only (ADR-0003).
    -- 'singleton' means no match was found and it stands alone.
    dedup_key           TEXT NOT NULL,
    dedup_method        TEXT NOT NULL
                        CHECK (dedup_method IN ('attributed_name',
                                                'paper_and_number',
                                                'singleton')),
    created_at          TEXT NOT NULL
);

CREATE INDEX conjecture_by_dedup_key ON conjecture(dedup_key);

-- ---------------------------------------------------------------------------
-- Assessment
-- ---------------------------------------------------------------------------

-- A model's judgment of one Conjecture: the Gate outcome plus six Axes.
-- Deliberately NO combined score column (ADR-0005). Do not add one.
CREATE TABLE assessment (
    id                       INTEGER PRIMARY KEY,
    conjecture_id            INTEGER NOT NULL REFERENCES conjecture(id) ON DELETE CASCADE,
    model                    TEXT NOT NULL,
    rubric_version           TEXT NOT NULL,
    rubric_sha256            TEXT NOT NULL,

    -- THE GATE. Does a Finite Witness exist? Failing this means the Conjecture
    -- never reaches the Digest, whatever the Axes say. With no human reviewing
    -- at volume, the Gate is the only filter — keep it strict.
    gate_pass                INTEGER NOT NULL CHECK (gate_pass IN (0, 1)),
    finite_witness           TEXT,               -- what object would be constructed
    gate_reason              TEXT NOT NULL,

    -- Axis: Frontier. The most decisive axis and the one a model is least able
    -- to judge honestly. frontier_quote MUST be text lifted from the Paper;
    -- when the Paper is silent the status is 'unknown' (ADR-0005). An unknown
    -- Frontier is useful information. An invented one poisons the ranking.
    frontier_status          TEXT NOT NULL CHECK (frontier_status IN ('known', 'unknown')),
    frontier_quote           TEXT,
    frontier_smallest_open   TEXT,
    frontier_search_space    TEXT,

    -- Axis: Machinery Depth.
    machinery_depth          TEXT NOT NULL
                             CHECK (machinery_depth IN ('shallow', 'moderate', 'deep')),
    machinery_reason         TEXT NOT NULL,

    -- Axis: Quantifier Form.
    quantifier_form          TEXT NOT NULL
                             CHECK (quantifier_form IN ('universal', 'existential',
                                                        'mixed', 'neither')),

    -- Axis: Prior Computation.
    prior_computation        TEXT NOT NULL
                             CHECK (prior_computation IN ('none', 'referenced', 'available')),
    prior_computation_detail TEXT,

    -- Axis: Attention. Derived from the Attribution fields on this
    -- Conjecture's Statements. Read as evidence AGAINST tractability.
    attention                TEXT NOT NULL CHECK (attention IN ('fresh', 'some', 'heavy')),
    attention_reason         TEXT NOT NULL,

    -- Axis: Venue of Record. Also negative (ADR-0001).
    venue_signal             TEXT NOT NULL
                             CHECK (venue_signal IN ('none', 'strong_venue', 'top_four')),

    argument                 TEXT NOT NULL,      -- the case, in prose
    created_at               TEXT NOT NULL
);

CREATE INDEX assessment_by_conjecture ON assessment(conjecture_id);
CREATE INDEX assessment_by_gate       ON assessment(gate_pass);

-- A human's judgment, in the SAME axis shape so the two can be set against
-- each other. This is an affordance, not an expected workflow (ADR-0007):
-- rows here are LOADED from judgment/verdicts.yaml, never written by the
-- pipeline, so a re-run can never clobber one.
CREATE TABLE verdict (
    id                  INTEGER PRIMARY KEY,
    conjecture_id       INTEGER NOT NULL REFERENCES conjecture(id) ON DELETE CASCADE,
    author              TEXT NOT NULL,
    recorded_at         TEXT NOT NULL,

    gate_pass           INTEGER CHECK (gate_pass IN (0, 1)),
    frontier_status     TEXT CHECK (frontier_status IN ('known', 'unknown')),
    machinery_depth     TEXT CHECK (machinery_depth IN ('shallow', 'moderate', 'deep')),
    quantifier_form     TEXT CHECK (quantifier_form IN ('universal', 'existential',
                                                        'mixed', 'neither')),
    prior_computation   TEXT CHECK (prior_computation IN ('none', 'referenced', 'available')),
    attention           TEXT CHECK (attention IN ('fresh', 'some', 'heavy')),

    notes               TEXT
);

CREATE INDEX verdict_by_conjecture ON verdict(conjecture_id);

-- ---------------------------------------------------------------------------
-- Calibration
-- ---------------------------------------------------------------------------

-- Conjectures whose real outcome is already known, run blind through the
-- rubric. Because Verdicts will not accumulate, this set carries the ENTIRE
-- calibration load (ADR-0007). Loaded from judgment/calibration.yaml.
CREATE TABLE calibration_case (
    slug                TEXT PRIMARY KEY,        -- 'keller-dimension-7'
    name                TEXT NOT NULL,
    statement           TEXT NOT NULL,

    -- 'settled_by_witness' = positive control: an explicit construction or
    --   exhaustive search actually settled it.
    -- 'open_resistant'     = negative control: combinatorial-looking, decades old.
    -- 'settled_by_theory'  = settled, but by an argument no search would find.
    known_outcome       TEXT NOT NULL
                        CHECK (known_outcome IN ('settled_by_witness',
                                                 'settled_by_theory',
                                                 'open_resistant')),
    outcome_detail      TEXT NOT NULL,
    outcome_source      TEXT NOT NULL,           -- verification reference; NOT recalled
    expected_gate_pass  INTEGER CHECK (expected_gate_pass IN (0, 1)),

    -- Set when this case came from a Pilot Attack rather than curation.
    from_pilot_attack   INTEGER NOT NULL DEFAULT 0 CHECK (from_pilot_attack IN (0, 1)),
    notes               TEXT
);

-- ---------------------------------------------------------------------------
-- Provenance
-- ---------------------------------------------------------------------------

CREATE TABLE extraction_run (
    id                  INTEGER PRIMARY KEY,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    model               TEXT NOT NULL,
    prompt_sha256       TEXT NOT NULL,
    corpus_categories   TEXT NOT NULL,           -- JSON array
    corpus_from         TEXT NOT NULL,           -- ISO date
    corpus_to           TEXT NOT NULL,
    paper_count         INTEGER,
    batch_ids           TEXT                     -- JSON array of Batch API ids
);
