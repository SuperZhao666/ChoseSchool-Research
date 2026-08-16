CREATE TABLE machine_test_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    taken_on TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 30 AND 360),
    language TEXT NOT NULL CHECK (length(trim(language)) BETWEEN 1 AND 60),
    environment TEXT NOT NULL CHECK (length(trim(environment)) BETWEEN 1 AND 240),
    problem_source TEXT NOT NULL CHECK (length(trim(problem_source)) BETWEEN 1 AND 240),
    difficulty_label TEXT NOT NULL CHECK (
        difficulty_label IN ('basic', 'mixed', 'candidate_specific', 'unknown')
    ),
    problem_count INTEGER NOT NULL CHECK (problem_count BETWEEN 1 AND 100),
    independently_solved_count INTEGER NOT NULL CHECK (
        independently_solved_count BETWEEN 0 AND problem_count
    ),
    first_solve_minutes INTEGER,
    first_exposure INTEGER NOT NULL CHECK (first_exposure IN (0, 1)),
    consulted_materials INTEGER NOT NULL CHECK (consulted_materials IN (0, 1)),
    strict_timed INTEGER NOT NULL CHECK (strict_timed IN (0, 1)),
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number >= 1),
    invalid_reason TEXT,
    primary_blocker TEXT,
    notes TEXT,
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    UNIQUE (profile_id, taken_on, problem_source, attempt_number),
    CHECK (
        (independently_solved_count = 0 AND first_solve_minutes IS NULL)
        OR
        (independently_solved_count > 0
         AND first_solve_minutes BETWEEN 1 AND duration_minutes)
    ),
    CHECK (
        (first_exposure = 1 AND consulted_materials = 0 AND strict_timed = 1)
        OR length(trim(COALESCE(invalid_reason, ''))) > 0
    )
);

CREATE INDEX ix_machine_test_sessions_profile_duration_date
    ON machine_test_sessions(profile_id, duration_minutes, taken_on, id);

CREATE INDEX ix_machine_test_sessions_trace
    ON machine_test_sessions(trace_id, created_at);

CREATE TRIGGER machine_test_sessions_no_update
BEFORE UPDATE ON machine_test_sessions
BEGIN
    SELECT RAISE(ABORT, 'machine_test_sessions are append-only');
END;

CREATE TRIGGER machine_test_sessions_no_delete
BEFORE DELETE ON machine_test_sessions
BEGIN
    SELECT RAISE(ABORT, 'machine_test_sessions are append-only');
END;

CREATE VIEW v_machine_test_sessions AS
SELECT
    session.*,
    CASE
        WHEN session.first_exposure = 1
         AND session.consulted_materials = 0
         AND session.strict_timed = 1
        THEN 1
        ELSE 0
    END AS is_valid
FROM machine_test_sessions session;
