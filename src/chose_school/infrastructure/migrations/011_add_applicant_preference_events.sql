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
            'school_tier_requirement'
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
