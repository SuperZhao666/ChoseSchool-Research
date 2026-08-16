CREATE TABLE policy_event_source_snapshots (
    policy_event_id INTEGER PRIMARY KEY REFERENCES policy_events(id),
    source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
    source_identity_key TEXT,
    source_title TEXT,
    source_institution TEXT,
    source_url TEXT,
    evidence_grade TEXT,
    source_document_type TEXT,
    source_content_sha256 TEXT,
    applicable_year INTEGER,
    published_date TEXT,
    retrieved_date TEXT,
    captured_at TEXT NOT NULL,
    trace_id TEXT
);

INSERT INTO policy_event_source_snapshots(
    policy_event_id, source_id, source_identity_key, source_title,
    source_institution, source_url, evidence_grade, source_document_type,
    source_content_sha256, applicable_year, published_date, retrieved_date,
    captured_at, trace_id
)
SELECT
    event.id,
    event.source_id,
    source.identity_key,
    source.title,
    source.institution,
    source.url,
    source.evidence_grade,
    source.document_type,
    source.content_sha256,
    source.applicable_year,
    source.published_date,
    source.retrieved_date,
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
    event.trace_id
FROM policy_events event
JOIN evidence_sources source ON source.id = event.source_id;

CREATE TRIGGER policy_event_source_snapshots_validate_insert
BEFORE INSERT ON policy_event_source_snapshots
BEGIN
    SELECT CASE
        WHEN NEW.trace_id IS NULL OR length(trim(NEW.trace_id)) = 0
        THEN RAISE(ABORT, 'policy event source snapshot trace_id is required')
    END;
    SELECT CASE
        WHEN NEW.source_identity_key IS NULL
          OR length(NEW.source_identity_key) != 64
          OR NEW.source_identity_key != lower(NEW.source_identity_key)
          OR NEW.source_identity_key GLOB '*[^0-9a-f]*'
        THEN RAISE(ABORT, 'policy event source identity must be lowercase SHA-256')
    END;
    SELECT CASE
        WHEN NEW.source_title IS NULL OR length(trim(NEW.source_title)) = 0
          OR NEW.source_institution IS NULL OR length(trim(NEW.source_institution)) = 0
          OR NEW.source_url IS NULL OR length(trim(NEW.source_url)) = 0
        THEN RAISE(ABORT, 'policy event source snapshot metadata is required')
    END;
    SELECT CASE
        WHEN NEW.evidence_grade != 'official'
          OR NEW.source_document_type != 'official_notice'
        THEN RAISE(ABORT, 'policy event source snapshot must describe an official notice')
    END;
    SELECT CASE
        WHEN NEW.source_content_sha256 IS NULL
          OR length(NEW.source_content_sha256) != 64
          OR NEW.source_content_sha256 != lower(NEW.source_content_sha256)
          OR NEW.source_content_sha256 GLOB '*[^0-9a-f]*'
        THEN RAISE(ABORT, 'policy event source snapshot hash must be lowercase SHA-256')
    END;
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM policy_events event
            WHERE event.id = NEW.policy_event_id
              AND event.source_id = NEW.source_id
              AND event.source_content_sha256 = NEW.source_content_sha256
              AND event.effective_year = NEW.applicable_year
              AND event.trace_id = NEW.trace_id
        )
        THEN RAISE(ABORT, 'policy event source snapshot does not match its event')
    END;
END;

CREATE TRIGGER protect_policy_event_source_snapshots_update
BEFORE UPDATE ON policy_event_source_snapshots
BEGIN
    SELECT RAISE(ABORT, 'policy_event_source_snapshots are append-only');
END;

CREATE TRIGGER protect_policy_event_source_snapshots_delete
BEFORE DELETE ON policy_event_source_snapshots
BEGIN
    SELECT RAISE(ABORT, 'policy_event_source_snapshots are append-only');
END;

DROP VIEW v_policy_event_history;

CREATE VIEW v_policy_event_history AS
SELECT
    event.id AS event_id,
    event.school_id,
    school.display_name AS school,
    event.project_id,
    college.display_name AS college,
    project.program_code,
    project.program_name,
    project.direction,
    event.effective_year,
    event.event_type,
    event.event_status,
    event.scope_text,
    event.title,
    event.description,
    event.announced_on,
    event.source_id,
    snapshot.source_title,
    snapshot.source_institution,
    snapshot.source_url,
    snapshot.source_document_type,
    snapshot.source_content_sha256,
    snapshot.applicable_year,
    snapshot.published_date,
    snapshot.retrieved_date,
    event.supersedes_event_id,
    CASE WHEN EXISTS (
        SELECT 1
        FROM policy_events successor
        WHERE successor.supersedes_event_id = event.id
    ) THEN 1 ELSE 0 END AS is_superseded,
    event.trace_id,
    event.event_fingerprint,
    event.created_at,
    0 AS establishes_official_catalog,
    0 AS can_confirm_strict_22408
FROM policy_events event
JOIN schools school ON school.id = event.school_id
LEFT JOIN projects project ON project.id = event.project_id
LEFT JOIN colleges college ON college.id = project.college_id
JOIN policy_event_source_snapshots snapshot
  ON snapshot.policy_event_id = event.id;
