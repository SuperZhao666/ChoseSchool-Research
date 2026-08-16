ALTER TABLE mock_exam_sessions
ADD COLUMN ledger_version INTEGER NOT NULL DEFAULT 1
CHECK (ledger_version IN (1, 2));

ALTER TABLE mock_exam_sessions ADD COLUMN trace_id TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN completed_on TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN paper_key TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN paper_source TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN paper_content_sha256 TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN exam_contract TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN first_exposure INTEGER
CHECK (first_exposure IN (0, 1) OR first_exposure IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN complete_paper_set INTEGER
CHECK (complete_paper_set IN (0, 1) OR complete_paper_set IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN strict_schedule INTEGER
CHECK (strict_schedule IN (0, 1) OR strict_schedule IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN authentic_time_slots INTEGER
CHECK (authentic_time_slots IN (0, 1) OR authentic_time_slots IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN consulted_materials INTEGER
CHECK (consulted_materials IN (0, 1) OR consulted_materials IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN received_assistance INTEGER
CHECK (received_assistance IN (0, 1) OR received_assistance IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN paused_timer INTEGER
CHECK (paused_timer IN (0, 1) OR paused_timer IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN reviewed_answers_early INTEGER
CHECK (reviewed_answers_early IN (0, 1) OR reviewed_answers_early IS NULL);
ALTER TABLE mock_exam_sessions ADD COLUMN paper_family TEXT
CHECK (
    paper_family IN ('official_past', 'calibrated_mock', 'training', 'unknown')
    OR paper_family IS NULL
);
ALTER TABLE mock_exam_sessions ADD COLUMN difficulty_label TEXT
CHECK (
    difficulty_label IN ('standard', 'easier', 'harder', 'unknown')
    OR difficulty_label IS NULL
);
ALTER TABLE mock_exam_sessions ADD COLUMN scoring_rule_key TEXT;
ALTER TABLE mock_exam_sessions ADD COLUMN invalid_reason_code TEXT
CHECK (
    invalid_reason_code IN (
        'not_first_exposure',
        'consulted_materials',
        'received_assistance',
        'paused_timer',
        'not_strict_timed',
        'not_complete_paper_set',
        'not_strict_schedule',
        'inauthentic_time_slots',
        'reviewed_answers_early',
        'technical_interruption',
        'health_interruption',
        'absent_subject',
        'other_protocol_failure'
    ) OR invalid_reason_code IS NULL
);
ALTER TABLE mock_exam_sessions ADD COLUMN invalid_reason_note TEXT;

CREATE UNIQUE INDEX ux_mock_exam_v2_paper_attempt
    ON mock_exam_sessions(profile_id, paper_key, attempt_number)
    WHERE ledger_version = 2;

CREATE UNIQUE INDEX ux_mock_exam_v2_content_attempt
    ON mock_exam_sessions(profile_id, paper_content_sha256, attempt_number)
    WHERE ledger_version = 2 AND paper_content_sha256 IS NOT NULL;

CREATE INDEX ix_mock_exam_v2_profile_completed
    ON mock_exam_sessions(profile_id, ledger_version, completed_on, id);

CREATE INDEX ix_mock_exam_v2_trace
    ON mock_exam_sessions(trace_id, created_at);

CREATE TABLE mock_exam_subject_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL
        REFERENCES mock_exam_sessions(id) ON DELETE RESTRICT,
    subject_code TEXT NOT NULL CHECK (length(trim(subject_code)) > 0),
    attendance_status TEXT NOT NULL CHECK (
        attendance_status IN ('present_scored', 'present_blank', 'absent')
    ),
    score_lower REAL,
    score_upper REAL,
    maximum_score REAL NOT NULL CHECK (maximum_score > 0),
    started_at TEXT,
    ended_at TEXT,
    actual_duration_minutes INTEGER,
    note TEXT,
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    UNIQUE (session_id, subject_code),
    CHECK (
        (attendance_status = 'present_scored'
         AND score_lower IS NOT NULL
         AND score_upper IS NOT NULL
         AND score_lower >= 0
         AND score_lower <= score_upper
         AND score_upper <= maximum_score
         AND started_at IS NOT NULL
         AND ended_at IS NOT NULL
         AND actual_duration_minutes > 0)
        OR
        (attendance_status = 'present_blank'
         AND score_lower = 0
         AND score_upper = 0
         AND started_at IS NOT NULL
         AND ended_at IS NOT NULL
         AND actual_duration_minutes > 0)
        OR
        (attendance_status = 'absent'
         AND score_lower IS NULL
         AND score_upper IS NULL
         AND started_at IS NULL
         AND ended_at IS NULL
         AND actual_duration_minutes IS NULL)
    )
);

CREATE INDEX ix_mock_exam_subject_results_session
    ON mock_exam_subject_results(session_id, subject_code);

CREATE INDEX ix_mock_exam_subject_results_trace
    ON mock_exam_subject_results(trace_id, created_at);

CREATE TABLE mock_exam_session_exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE
        REFERENCES mock_exam_sessions(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL
);

CREATE INDEX ix_mock_exam_session_exclusions_trace
    ON mock_exam_session_exclusions(trace_id, created_at);

CREATE TRIGGER mock_exam_sessions_validate_v2
BEFORE INSERT ON mock_exam_sessions
WHEN NEW.ledger_version = 2
BEGIN
    SELECT CASE
        WHEN length(trim(COALESCE(NEW.trace_id, ''))) = 0
          OR length(trim(COALESCE(NEW.paper_key, ''))) = 0
          OR length(trim(COALESCE(NEW.paper_source, ''))) = 0
          OR length(trim(COALESCE(NEW.exam_contract, ''))) = 0
          OR length(trim(COALESCE(NEW.scoring_rule_key, ''))) = 0
          OR NEW.completed_on IS NULL
          OR NEW.first_exposure IS NULL
          OR NEW.complete_paper_set IS NULL
          OR NEW.strict_schedule IS NULL
          OR NEW.authentic_time_slots IS NULL
          OR NEW.consulted_materials IS NULL
          OR NEW.received_assistance IS NULL
          OR NEW.paused_timer IS NULL
          OR NEW.reviewed_answers_early IS NULL
          OR NEW.paper_family IS NULL
          OR NEW.difficulty_label IS NULL
        THEN RAISE(ABORT, 'mock ledger v2 requires complete protocol facts')
    END;

    SELECT CASE
        WHEN NEW.attempt_number > 1 AND NEW.first_exposure = 1
        THEN RAISE(ABORT, 'repeat mock attempt cannot be first exposure')
    END;

    SELECT CASE
        WHEN NEW.first_exposure = 1
         AND EXISTS (
             SELECT 1
             FROM mock_exam_sessions prior
             WHERE prior.profile_id = NEW.profile_id
               AND prior.ledger_version = 2
               AND prior.paper_key = NEW.paper_key
         )
        THEN RAISE(ABORT, 'mock paper key has already been recorded')
    END;

    SELECT CASE
        WHEN NEW.first_exposure = 1
         AND NEW.paper_content_sha256 IS NOT NULL
         AND EXISTS (
             SELECT 1
             FROM mock_exam_sessions prior
             WHERE prior.profile_id = NEW.profile_id
               AND prior.ledger_version = 2
               AND prior.paper_content_sha256 = NEW.paper_content_sha256
         )
        THEN RAISE(ABORT, 'mock paper content has already been recorded')
    END;

    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM mock_exam_sessions prior
            WHERE prior.profile_id = NEW.profile_id
              AND prior.ledger_version = 2
              AND date(NEW.taken_on) <= date(prior.completed_on)
              AND date(NEW.completed_on) >= date(prior.taken_on)
        )
        THEN RAISE(ABORT, 'mock ledger sessions cannot overlap calendar days')
    END;

    SELECT CASE
        WHEN NOT (
            (
                NEW.first_exposure = 1
                AND NEW.complete_paper_set = 1
                AND NEW.strict_schedule = 1
                AND NEW.authentic_time_slots = 1
                AND NEW.strict_timed = 1
                AND NEW.consulted_materials = 0
                AND NEW.received_assistance = 0
                AND NEW.paused_timer = 0
                AND NEW.reviewed_answers_early = 0
                AND date(NEW.completed_on) = date(NEW.taken_on, '+1 day')
                AND NEW.invalid_reason_code IS NULL
                AND length(trim(COALESCE(NEW.invalid_reason_note, ''))) = 0
            )
            OR
            (
                (
                    NEW.first_exposure = 0
                    OR NEW.complete_paper_set = 0
                    OR NEW.strict_schedule = 0
                    OR NEW.authentic_time_slots = 0
                    OR NEW.strict_timed = 0
                    OR NEW.consulted_materials = 1
                    OR NEW.received_assistance = 1
                    OR NEW.paused_timer = 1
                    OR NEW.reviewed_answers_early = 1
                    OR date(NEW.completed_on) != date(NEW.taken_on, '+1 day')
                )
                AND NEW.invalid_reason_code IS NOT NULL
                AND length(trim(COALESCE(NEW.invalid_reason_note, ''))) > 0
            )
        )
        THEN RAISE(ABORT, 'mock protocol facts and invalid reason disagree')
    END;
END;

CREATE TRIGGER mock_exam_subject_results_validate_parent
BEFORE INSERT ON mock_exam_subject_results
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM mock_exam_sessions session
            WHERE session.id = NEW.session_id
              AND session.ledger_version = 2
              AND session.trace_id = NEW.trace_id
        )
        THEN RAISE(ABORT, 'mock subject result must match its v2 session trace')
    END;

    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM mock_exam_sessions session
            JOIN applicant_profiles profile ON profile.id = session.profile_id
            WHERE session.id = NEW.session_id
              AND NEW.subject_code IN (
                  profile.politics_code,
                  profile.english_code,
                  profile.math_code,
                  profile.professional_code
              )
        )
        THEN RAISE(ABORT, 'mock subject code is outside the applicant exam contract')
    END;

    SELECT CASE
        WHEN NEW.maximum_score != CASE NEW.subject_code
            WHEN '101' THEN 100
            WHEN '204' THEN 100
            WHEN '302' THEN 150
            WHEN '408' THEN 150
            ELSE NEW.maximum_score
        END
        THEN RAISE(ABORT, 'mock subject maximum score does not match strict 22408')
    END;

    SELECT CASE
        WHEN NEW.attendance_status != 'absent'
         AND (
             julianday(NEW.started_at) IS NULL
             OR julianday(NEW.ended_at) IS NULL
             OR CAST(ROUND(
                 (julianday(NEW.ended_at) - julianday(NEW.started_at)) * 1440
             ) AS INTEGER) != NEW.actual_duration_minutes
         )
        THEN RAISE(ABORT, 'mock subject timestamps and duration disagree')
    END;

    SELECT CASE
        WHEN NEW.attendance_status != 'absent'
         AND EXISTS (
             SELECT 1
             FROM mock_exam_sessions session
             WHERE session.id = NEW.session_id
               AND session.authentic_time_slots = 1
               AND (
                   date(NEW.started_at, '+8 hours') != CASE NEW.subject_code
                       WHEN '101' THEN date(session.taken_on)
                       WHEN '204' THEN date(session.taken_on)
                       WHEN '302' THEN date(session.completed_on)
                       WHEN '408' THEN date(session.completed_on)
                   END
                   OR strftime('%H:%M', NEW.started_at, '+8 hours') !=
                       CASE NEW.subject_code
                           WHEN '101' THEN '08:30'
                           WHEN '204' THEN '14:00'
                           WHEN '302' THEN '08:30'
                           WHEN '408' THEN '14:00'
                       END
                   OR strftime('%H:%M', NEW.ended_at, '+8 hours') !=
                       CASE NEW.subject_code
                           WHEN '101' THEN '11:30'
                           WHEN '204' THEN '17:00'
                           WHEN '302' THEN '11:30'
                           WHEN '408' THEN '17:00'
                       END
               )
         )
        THEN RAISE(ABORT, 'mock subject timestamps do not match authentic exam slots')
    END;
END;

CREATE TRIGGER mock_exam_sessions_no_update
BEFORE UPDATE ON mock_exam_sessions
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_sessions are append-only');
END;

CREATE TRIGGER mock_exam_sessions_no_delete
BEFORE DELETE ON mock_exam_sessions
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_sessions are append-only');
END;

CREATE TRIGGER mock_exam_scores_no_update
BEFORE UPDATE ON mock_exam_scores
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_scores are append-only legacy records');
END;

CREATE TRIGGER mock_exam_scores_no_delete
BEFORE DELETE ON mock_exam_scores
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_scores are append-only legacy records');
END;

CREATE TRIGGER mock_exam_subject_results_no_update
BEFORE UPDATE ON mock_exam_subject_results
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_subject_results are append-only');
END;

CREATE TRIGGER mock_exam_subject_results_no_delete
BEFORE DELETE ON mock_exam_subject_results
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_subject_results are append-only');
END;

CREATE TRIGGER mock_exam_session_exclusions_no_update
BEFORE UPDATE ON mock_exam_session_exclusions
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_session_exclusions are append-only');
END;

CREATE TRIGGER mock_exam_session_exclusions_no_delete
BEFORE DELETE ON mock_exam_session_exclusions
BEGIN
    SELECT RAISE(ABORT, 'mock_exam_session_exclusions are append-only');
END;

CREATE TRIGGER applicant_profiles_protect_mock_history
BEFORE DELETE ON applicant_profiles
WHEN EXISTS (
    SELECT 1 FROM mock_exam_sessions session WHERE session.profile_id = OLD.id
)
BEGIN
    SELECT RAISE(ABORT, 'applicant profile has append-only mock exam history');
END;

CREATE VIEW v_mock_exam_ledger_sessions AS
WITH subject_summary AS (
    SELECT
        result.session_id,
        COUNT(*) AS result_count,
        COUNT(DISTINCT result.subject_code) AS distinct_subject_count,
        SUM(CASE WHEN result.attendance_status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
        SUM(CASE
            WHEN result.attendance_status != 'absent'
             AND result.actual_duration_minutes != 180
            THEN 1 ELSE 0 END
        ) AS duration_mismatch_count,
        SUM(result.score_lower) AS total_lower,
        SUM(result.score_upper) AS total_upper,
        MAX(CASE
            WHEN result.score_lower IS NOT NULL
             AND result.score_upper IS NOT NULL
             AND result.score_lower != result.score_upper
            THEN 1 ELSE 0 END
        ) AS has_score_interval
    FROM mock_exam_subject_results result
    GROUP BY result.session_id
), protocol_state AS (
    SELECT
        session.*,
        COALESCE(summary.result_count, 0) AS result_count,
        COALESCE(summary.distinct_subject_count, 0) AS distinct_subject_count,
        COALESCE(summary.absent_count, 0) AS absent_count,
        COALESCE(summary.duration_mismatch_count, 0) AS duration_mismatch_count,
        summary.total_lower,
        summary.total_upper,
        COALESCE(summary.has_score_interval, 0) AS has_score_interval,
        exclusion.id AS exclusion_id,
        exclusion.reason AS exclusion_reason,
        CASE
            WHEN session.ledger_version = 2
             AND length(trim(COALESCE(session.trace_id, ''))) > 0
             AND session.first_exposure = 1
             AND session.complete_paper_set = 1
             AND session.strict_schedule = 1
             AND session.authentic_time_slots = 1
             AND session.strict_timed = 1
             AND session.consulted_materials = 0
             AND session.received_assistance = 0
             AND session.paused_timer = 0
             AND session.reviewed_answers_early = 0
             AND date(session.completed_on) = date(session.taken_on, '+1 day')
             AND session.invalid_reason_code IS NULL
             AND length(trim(COALESCE(session.invalid_reason_note, ''))) = 0
            THEN 1 ELSE 0
        END AS is_execution_valid
    FROM mock_exam_sessions session
    LEFT JOIN subject_summary summary ON summary.session_id = session.id
    LEFT JOIN mock_exam_session_exclusions exclusion
      ON exclusion.session_id = session.id
)
SELECT
    state.*,
    CASE
        WHEN state.has_score_interval = 1 THEN 'interval'
        WHEN state.result_count = 4 AND state.absent_count = 0 THEN 'exact'
        ELSE 'unknown'
    END AS score_precision_mode,
    CASE
        WHEN state.ledger_version = 1 THEN 'legacy_unverified'
        WHEN state.exclusion_id IS NOT NULL THEN 'excluded'
        WHEN state.is_execution_valid = 0 THEN 'invalid_execution'
        WHEN state.result_count != 4 OR state.distinct_subject_count != 4
            THEN 'incomplete_results'
        WHEN state.absent_count > 0 THEN 'absent_subject'
        WHEN state.duration_mismatch_count > 0 THEN 'duration_mismatch'
        WHEN state.paper_family IN ('training', 'unknown')
          OR state.difficulty_label = 'unknown'
            THEN 'ineligible_comparison_group'
        ELSE 'valid'
    END AS eligibility_status,
    CASE
        WHEN state.ledger_version = 2
         AND state.exclusion_id IS NULL
         AND state.is_execution_valid = 1
         AND state.result_count = 4
         AND state.distinct_subject_count = 4
         AND state.absent_count = 0
         AND state.duration_mismatch_count = 0
         AND state.paper_family IN ('official_past', 'calibrated_mock')
         AND state.difficulty_label != 'unknown'
        THEN 1 ELSE 0
    END AS is_assessment_eligible,
    state.exam_contract || '|' || state.paper_family || '|' ||
        state.difficulty_label || '|' || state.scoring_rule_key || '|' ||
        CASE
            WHEN state.has_score_interval = 1 THEN 'interval'
            WHEN state.result_count = 4 AND state.absent_count = 0 THEN 'exact'
            ELSE 'unknown'
        END AS comparison_key
FROM protocol_state state;
