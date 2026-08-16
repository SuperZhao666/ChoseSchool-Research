DROP VIEW v_current_applicant_preferences;
DROP TRIGGER applicant_preference_events_no_update;
DROP TRIGGER applicant_preference_events_no_delete;
DROP INDEX ix_applicant_preference_events_identity;
DROP INDEX ix_applicant_preference_events_trace;

ALTER TABLE applicant_preference_events
    RENAME TO applicant_preference_events_v1;

CREATE TABLE applicant_preference_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    dimension TEXT NOT NULL CHECK (
        dimension IN (
            'region',
            'training_location',
            'program_code',
            'tuition_ceiling',
            'retest_format',
            'joint_training',
            'school_tier_requirement',
            'admission_fairness',
            'institution'
        )
    ),
    subject_key TEXT NOT NULL CHECK (length(trim(subject_key)) BETWEEN 1 AND 120),
    value_json TEXT NOT NULL DEFAULT '{}' CHECK (
        json_valid(value_json) AND json_type(value_json) = 'object'
    ),
    acceptance_level TEXT NOT NULL CHECK (
        acceptance_level IN ('accept', 'reluctant', 'reject', 'unknown')
    ),
    note TEXT,
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL
);

INSERT INTO applicant_preference_events(
    id, profile_id, dimension, subject_key, value_json,
    acceptance_level, note, trace_id, created_at
)
SELECT
    id, profile_id, dimension, subject_key, value_json,
    acceptance_level, note, trace_id, created_at
FROM applicant_preference_events_v1
ORDER BY id;

DROP TABLE applicant_preference_events_v1;

CREATE INDEX ix_applicant_preference_events_identity
    ON applicant_preference_events(profile_id, dimension, subject_key, id DESC);

CREATE INDEX ix_applicant_preference_events_trace
    ON applicant_preference_events(trace_id, created_at);

CREATE TRIGGER applicant_preference_events_no_update
BEFORE UPDATE ON applicant_preference_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_preference_events are append-only');
END;

CREATE TRIGGER applicant_preference_events_no_delete
BEFORE DELETE ON applicant_preference_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_preference_events are append-only');
END;

CREATE VIEW v_current_applicant_preferences AS
SELECT event.*
FROM applicant_preference_events event
WHERE event.id = (
    SELECT MAX(candidate.id)
    FROM applicant_preference_events candidate
    WHERE candidate.profile_id = event.profile_id
      AND candidate.dimension = event.dimension
      AND candidate.subject_key = event.subject_key
);

CREATE TABLE applicant_context_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    dimension TEXT NOT NULL CHECK (
        dimension IN (
            'study_progress',
            'study_routine',
            'measurement_status',
            'preparation_strategy',
            'personal_constraint'
        )
    ),
    subject_key TEXT NOT NULL CHECK (length(trim(subject_key)) BETWEEN 1 AND 120),
    value_json TEXT NOT NULL CHECK (
        json_valid(value_json) AND json_type(value_json) = 'object'
    ),
    note TEXT,
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL
);

CREATE INDEX ix_applicant_context_events_identity
    ON applicant_context_events(profile_id, dimension, subject_key, id DESC);

CREATE INDEX ix_applicant_context_events_trace
    ON applicant_context_events(trace_id, created_at);

CREATE TRIGGER applicant_context_events_no_update
BEFORE UPDATE ON applicant_context_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_context_events are append-only');
END;

CREATE TRIGGER applicant_context_events_no_delete
BEFORE DELETE ON applicant_context_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_context_events are append-only');
END;

CREATE VIEW v_current_applicant_context AS
SELECT event.*
FROM applicant_context_events event
WHERE event.id = (
    SELECT MAX(candidate.id)
    FROM applicant_context_events candidate
    WHERE candidate.profile_id = event.profile_id
      AND candidate.dimension = event.dimension
      AND candidate.subject_key = event.subject_key
);

CREATE TABLE candidate_fairness_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    observation_id INTEGER NOT NULL REFERENCES project_year_observations(id) ON DELETE RESTRICT,
    review_version TEXT NOT NULL CHECK (review_version = 'candidate-fairness-v1'),
    conclusion TEXT NOT NULL CHECK (
        conclusion IN ('favorable', 'mixed', 'adverse', 'insufficient')
    ),
    summary TEXT NOT NULL CHECK (length(trim(summary)) BETWEEN 1 AND 2000),
    evidence_json TEXT NOT NULL CHECK (
        json_valid(evidence_json) AND json_type(evidence_json) = 'array'
    ),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL
);

CREATE INDEX ix_candidate_fairness_reviews_identity
    ON candidate_fairness_reviews(profile_id, observation_id, id DESC);

CREATE INDEX ix_candidate_fairness_reviews_trace
    ON candidate_fairness_reviews(trace_id, created_at);

CREATE TRIGGER candidate_fairness_reviews_no_update
BEFORE UPDATE ON candidate_fairness_reviews
BEGIN
    SELECT RAISE(ABORT, 'candidate_fairness_reviews are append-only');
END;

CREATE TRIGGER candidate_fairness_reviews_no_delete
BEFORE DELETE ON candidate_fairness_reviews
BEGIN
    SELECT RAISE(ABORT, 'candidate_fairness_reviews are append-only');
END;

CREATE VIEW v_current_candidate_fairness_reviews AS
SELECT review.*
FROM candidate_fairness_reviews review
WHERE review.id = (
    SELECT MAX(candidate.id)
    FROM candidate_fairness_reviews candidate
    WHERE candidate.profile_id = review.profile_id
      AND candidate.observation_id = review.observation_id
);
