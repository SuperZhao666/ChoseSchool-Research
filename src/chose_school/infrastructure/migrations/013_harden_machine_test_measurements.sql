ALTER TABLE machine_test_sessions
ADD COLUMN received_assistance INTEGER NOT NULL DEFAULT 0
CHECK (received_assistance IN (0, 1));

ALTER TABLE machine_test_sessions
ADD COLUMN paused_timer INTEGER NOT NULL DEFAULT 0
CHECK (paused_timer IN (0, 1));

ALTER TABLE machine_test_sessions
ADD COLUMN scoring_method TEXT NOT NULL DEFAULT 'unknown'
CHECK (scoring_method IN ('solved_count', 'points', 'mixed', 'unknown'));

ALTER TABLE machine_test_sessions
ADD COLUMN raw_score REAL;

ALTER TABLE machine_test_sessions
ADD COLUMN maximum_score REAL;

ALTER TABLE machine_test_sessions
ADD COLUMN debugging_minutes INTEGER;

CREATE TRIGGER machine_test_sessions_validate_measurement_v2
BEFORE INSERT ON machine_test_sessions
BEGIN
    SELECT CASE
        WHEN NOT (
            (
                NEW.first_exposure = 1
                AND NEW.consulted_materials = 0
                AND NEW.received_assistance = 0
                AND NEW.paused_timer = 0
                AND NEW.strict_timed = 1
                AND length(trim(COALESCE(NEW.invalid_reason, ''))) = 0
            )
            OR
            (
                (
                    NEW.first_exposure = 0
                    OR NEW.consulted_materials = 1
                    OR NEW.received_assistance = 1
                    OR NEW.paused_timer = 1
                    OR NEW.strict_timed = 0
                )
                AND length(trim(COALESCE(NEW.invalid_reason, ''))) > 0
            )
        )
        THEN RAISE(ABORT, 'machine test validity facts and invalid_reason disagree')
    END;

    SELECT CASE
        WHEN NEW.debugging_minutes IS NOT NULL
         AND (
             typeof(NEW.debugging_minutes) != 'integer'
             OR NEW.debugging_minutes < 0
             OR NEW.debugging_minutes > NEW.duration_minutes
         )
        THEN RAISE(ABORT, 'debugging_minutes is outside the timed session')
    END;

    SELECT CASE
        WHEN (NEW.raw_score IS NULL) != (NEW.maximum_score IS NULL)
        THEN RAISE(ABORT, 'raw_score and maximum_score must be supplied together')
    END;

    SELECT CASE
        WHEN NEW.maximum_score IS NOT NULL
         AND (
             NEW.maximum_score <= 0
             OR NEW.raw_score < 0
             OR NEW.raw_score > NEW.maximum_score
         )
        THEN RAISE(ABORT, 'machine test score is outside the declared scale')
    END;

    SELECT CASE
        WHEN NEW.scoring_method IN ('points', 'mixed')
         AND (NEW.raw_score IS NULL OR NEW.maximum_score IS NULL)
        THEN RAISE(ABORT, 'points and mixed scoring require raw and maximum scores')
    END;
END;

DROP VIEW v_machine_test_sessions;

CREATE VIEW v_machine_test_sessions AS
SELECT
    session.*,
    CASE
        WHEN session.first_exposure = 1
         AND session.consulted_materials = 0
         AND session.received_assistance = 0
         AND session.paused_timer = 0
         AND session.strict_timed = 1
         AND length(trim(COALESCE(session.invalid_reason, ''))) = 0
        THEN 1
        ELSE 0
    END AS is_valid
FROM machine_test_sessions session;
