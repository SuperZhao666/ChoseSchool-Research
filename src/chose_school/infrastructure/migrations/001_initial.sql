CREATE TABLE import_batches (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    importer_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'duplicate')),
    duplicate_of TEXT REFERENCES import_batches(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    source_file_count INTEGER NOT NULL DEFAULT 0 CHECK (source_file_count >= 0),
    raw_row_count INTEGER NOT NULL DEFAULT 0 CHECK (raw_row_count >= 0),
    observation_count INTEGER NOT NULL DEFAULT 0 CHECK (observation_count >= 0),
    issue_count INTEGER NOT NULL DEFAULT 0 CHECK (issue_count >= 0),
    ignored_member_count INTEGER NOT NULL DEFAULT 0 CHECK (ignored_member_count >= 0),
    error_message TEXT
);

CREATE UNIQUE INDEX uq_import_batches_successful_source
    ON import_batches(source_sha256, importer_version)
    WHERE status = 'succeeded';

CREATE TABLE source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    archive_member TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    header_json TEXT NOT NULL,
    expected_column_count INTEGER NOT NULL CHECK (expected_column_count > 0),
    row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    UNIQUE (batch_id, archive_member)
);

CREATE TABLE raw_catalog_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    source_row_number INTEGER NOT NULL CHECK (source_row_number >= 2),
    row_sha256 TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    raw_cells_json TEXT NOT NULL,
    cell_count INTEGER NOT NULL CHECK (cell_count >= 0),
    expected_cell_count INTEGER NOT NULL CHECK (expected_cell_count > 0),
    imported_at TEXT NOT NULL,
    UNIQUE (source_file_id, source_row_number)
);

CREATE TABLE schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE colleges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    canonical_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (school_id, canonical_name)
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_key TEXT NOT NULL UNIQUE,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    college_id INTEGER NOT NULL REFERENCES colleges(id),
    program_code TEXT,
    program_name TEXT,
    direction TEXT,
    campus TEXT,
    training_location TEXT,
    study_mode TEXT,
    training_type_raw TEXT,
    admission_type TEXT,
    degree_type TEXT,
    training_arrangement TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE project_year_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    raw_row_id INTEGER NOT NULL UNIQUE REFERENCES raw_catalog_rows(id) ON DELETE CASCADE,
    observation_fingerprint TEXT NOT NULL UNIQUE,
    admission_year INTEGER,
    strict_22408_claim TEXT NOT NULL CHECK (
        strict_22408_claim IN ('yes', 'no', 'unknown')
    ),
    strict_22408_evidence_status TEXT NOT NULL CHECK (
        strict_22408_evidence_status IN (
            'unverified', 'secondary_only', 'official_pending_catalog',
            'official_confirmed', 'official_non_strict', 'conflict'
        )
    ),
    strict_22408_status_raw TEXT,
    subject_politics_code TEXT,
    subject_english_code TEXT,
    subject_math_code TEXT,
    subject_professional_code TEXT,
    total_plan INTEGER,
    recommendation_actual INTEGER,
    special_plan INTEGER,
    effective_general_exam_quota INTEGER,
    retest_cutoff REAL,
    retest_count INTEGER,
    general_exam_admit_count INTEGER,
    admit_initial_min REAL,
    admit_initial_median REAL,
    admit_initial_mean REAL,
    initial_exam_weight REAL,
    retest_weight REAL,
    machine_test_weight REAL,
    machine_test_elimination_line REAL,
    tuition_per_year REAL,
    study_length_years REAL,
    first_choice_protection INTEGER CHECK (first_choice_protection IN (0, 1) OR first_choice_protection IS NULL),
    evidence_grade TEXT NOT NULL CHECK (
        evidence_grade IN ('official', 'official_mixed', 'secondary', 'tertiary', 'unknown')
    ),
    source_level_raw TEXT,
    official_source TEXT,
    retrieval_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX ix_observations_year_status
    ON project_year_observations(admission_year, strict_22408_evidence_status);
CREATE INDEX ix_observations_project_year
    ON project_year_observations(project_id, admission_year);

CREATE TABLE evidence_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    institution TEXT,
    url TEXT,
    evidence_grade TEXT NOT NULL CHECK (
        evidence_grade IN ('official', 'official_mixed', 'secondary', 'tertiary', 'unknown')
    ),
    published_date TEXT,
    retrieved_date TEXT,
    source_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE duplicate_observations (
    raw_row_id INTEGER PRIMARY KEY REFERENCES raw_catalog_rows(id) ON DELETE CASCADE,
    canonical_observation_id INTEGER NOT NULL REFERENCES project_year_observations(id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE observation_sources (
    observation_id INTEGER NOT NULL REFERENCES project_year_observations(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
    relationship TEXT NOT NULL DEFAULT 'supports' CHECK (relationship IN ('supports', 'contradicts', 'context')),
    PRIMARY KEY (observation_id, source_id, relationship)
);

CREATE TABLE field_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL REFERENCES project_year_observations(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    raw_value TEXT,
    normalized_value TEXT,
    source_id INTEGER REFERENCES evidence_sources(id),
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        verification_status IN ('pending', 'accepted', 'rejected', 'conflict')
    ),
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (observation_id, field_name, source_id)
);

CREATE INDEX ix_field_evidence_field_status
    ON field_evidence(field_name, verification_status);

CREATE TABLE data_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_fingerprint TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    raw_row_id INTEGER REFERENCES raw_catalog_rows(id) ON DELETE CASCADE,
    observation_id INTEGER REFERENCES project_year_observations(id) ON DELETE CASCADE,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    field_name TEXT,
    raw_value TEXT,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'wont_fix')),
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX ix_quality_issues_open
    ON data_quality_issues(status, severity, issue_code);
CREATE INDEX ix_quality_issues_observation
    ON data_quality_issues(observation_id);

CREATE TABLE subject_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL REFERENCES project_year_observations(id) ON DELETE CASCADE,
    politics_code TEXT NOT NULL,
    english_code TEXT NOT NULL,
    math_code TEXT NOT NULL,
    professional_code TEXT NOT NULL,
    derived_status TEXT NOT NULL CHECK (derived_status IN ('official_confirmed', 'official_non_strict')),
    source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
    note TEXT,
    verified_at TEXT NOT NULL,
    UNIQUE (observation_id, source_id)
);

CREATE TABLE policy_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(id),
    project_id INTEGER REFERENCES projects(id),
    effective_year INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_status TEXT NOT NULL CHECK (event_status IN ('announced', 'pending_directory', 'confirmed', 'superseded')),
    title TEXT NOT NULL,
    description TEXT,
    source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
    announced_on TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX ix_policy_events_year_status
    ON policy_events(effective_year, event_status);

CREATE TABLE applicant_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT NOT NULL UNIQUE,
    undergraduate_school TEXT,
    undergraduate_major TEXT,
    target_exam_year INTEGER NOT NULL,
    politics_code TEXT NOT NULL,
    english_code TEXT NOT NULL,
    math_code TEXT NOT NULL,
    professional_code TEXT NOT NULL,
    target_degree_type TEXT,
    target_tier TEXT,
    preferences_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE mock_exam_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE CASCADE,
    taken_on TEXT NOT NULL,
    paper_name TEXT NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number >= 1),
    strict_timed INTEGER NOT NULL CHECK (strict_timed IN (0, 1)),
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (profile_id, taken_on, paper_name, attempt_number)
);

CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX ix_audit_events_trace ON audit_events(trace_id, created_at);

CREATE TABLE mock_exam_scores (
    session_id INTEGER NOT NULL REFERENCES mock_exam_sessions(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0),
    maximum_score REAL NOT NULL CHECK (maximum_score > 0),
    duration_minutes INTEGER CHECK (duration_minutes > 0 OR duration_minutes IS NULL),
    PRIMARY KEY (session_id, subject_code),
    CHECK (score <= maximum_score)
);

CREATE TABLE decision_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    mock_session_count INTEGER NOT NULL CHECK (mock_session_count >= 0),
    total_mean REAL,
    total_standard_deviation REAL,
    conservative_total REAL,
    machine_test_level TEXT,
    official_catalog_as_of TEXT,
    notes TEXT
);

CREATE TABLE decision_candidates (
    snapshot_id INTEGER NOT NULL REFERENCES decision_snapshots(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    tier TEXT NOT NULL CHECK (tier IN ('sprint', 'match', 'steady', 'watch', 'excluded')),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'rejected', 'selected')),
    PRIMARY KEY (snapshot_id, project_id)
);

CREATE VIEW v_catalog AS
SELECT
    o.id AS observation_id,
    r.source_row_number,
    sf.archive_member,
    s.display_name AS school,
    c.display_name AS college,
    p.program_code,
    p.program_name,
    p.direction,
    p.campus,
    p.training_location,
    p.study_mode,
    p.training_type_raw,
    p.admission_type,
    p.degree_type,
    p.training_arrangement,
    o.admission_year,
    o.strict_22408_claim,
    CASE
        WHEN (
            SELECT COUNT(DISTINCT (
                sv.politics_code || '+' || sv.english_code || '+' ||
                sv.math_code || '+' || sv.professional_code
            ))
            FROM subject_verifications sv
            WHERE sv.observation_id = o.id
        ) > 1 THEN 'conflict'
        ELSE COALESCE(
            (
                SELECT sv.derived_status
                FROM subject_verifications sv
                WHERE sv.observation_id = o.id
                ORDER BY sv.verified_at DESC, sv.id DESC
                LIMIT 1
            ),
            o.strict_22408_evidence_status
        )
    END AS strict_22408_status,
    o.strict_22408_evidence_status AS imported_evidence_status,
    o.subject_politics_code,
    o.subject_english_code,
    o.subject_math_code,
    o.subject_professional_code,
    o.effective_general_exam_quota,
    o.retest_cutoff,
    o.retest_count,
    o.general_exam_admit_count,
    o.admit_initial_min,
    o.admit_initial_median,
    o.admit_initial_mean,
    o.initial_exam_weight,
    o.retest_weight,
    o.machine_test_weight,
    o.machine_test_elimination_line,
    o.tuition_per_year,
    o.study_length_years,
    o.first_choice_protection,
    o.evidence_grade,
    o.official_source,
    o.retrieval_date,
    o.notes,
    (SELECT COUNT(*) FROM data_quality_issues q WHERE q.observation_id = o.id AND q.status = 'open') AS open_issue_count
FROM project_year_observations o
JOIN projects p ON p.id = o.project_id
JOIN schools s ON s.id = p.school_id
JOIN colleges c ON c.id = p.college_id
JOIN raw_catalog_rows r ON r.id = o.raw_row_id
JOIN source_files sf ON sf.id = r.source_file_id;

CREATE VIEW v_strict_22408_candidates AS
SELECT *
FROM v_catalog
WHERE strict_22408_claim = 'yes'
  AND strict_22408_status IN (
      'official_confirmed', 'official_pending_catalog', 'secondary_only', 'unverified'
  );

CREATE VIEW v_open_issue_summary AS
SELECT severity, issue_code, COUNT(*) AS issue_count
FROM data_quality_issues
WHERE status = 'open'
GROUP BY severity, issue_code;
