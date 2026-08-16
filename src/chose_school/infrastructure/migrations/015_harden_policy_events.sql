ALTER TABLE policy_events ADD COLUMN trace_id TEXT;
ALTER TABLE policy_events ADD COLUMN event_fingerprint TEXT;
ALTER TABLE policy_events ADD COLUMN scope_text TEXT;
ALTER TABLE policy_events ADD COLUMN source_content_sha256 TEXT;
ALTER TABLE policy_events ADD COLUMN supersedes_event_id INTEGER REFERENCES policy_events(id);

CREATE UNIQUE INDEX ux_policy_events_fingerprint
    ON policy_events(event_fingerprint)
    WHERE event_fingerprint IS NOT NULL;

CREATE UNIQUE INDEX ux_policy_events_single_successor
    ON policy_events(supersedes_event_id)
    WHERE supersedes_event_id IS NOT NULL;

CREATE INDEX ix_policy_events_trace
    ON policy_events(trace_id, created_at);

CREATE INDEX ix_policy_events_scope
    ON policy_events(school_id, project_id, effective_year, event_type, id);

CREATE TRIGGER policy_events_validate_new_insert
BEFORE INSERT ON policy_events
BEGIN
    SELECT CASE
        WHEN NEW.trace_id IS NULL OR length(trim(NEW.trace_id)) = 0
        THEN RAISE(ABORT, 'policy event trace_id is required')
    END;
    SELECT CASE
        WHEN NEW.event_fingerprint IS NULL
          OR length(NEW.event_fingerprint) != 64
          OR NEW.event_fingerprint != lower(NEW.event_fingerprint)
          OR NEW.event_fingerprint GLOB '*[^0-9a-f]*'
        THEN RAISE(ABORT, 'policy event fingerprint must be lowercase SHA-256')
    END;
    SELECT CASE
        WHEN NEW.scope_text IS NULL OR length(trim(NEW.scope_text)) = 0
        THEN RAISE(ABORT, 'policy event scope_text is required')
    END;
    SELECT CASE
        WHEN NEW.source_content_sha256 IS NULL
          OR length(NEW.source_content_sha256) != 64
          OR NEW.source_content_sha256 != lower(NEW.source_content_sha256)
          OR NEW.source_content_sha256 GLOB '*[^0-9a-f]*'
        THEN RAISE(ABORT, 'policy event source hash must be lowercase SHA-256')
    END;
    SELECT CASE
        WHEN NEW.created_at IS NULL
          OR NEW.updated_at IS NULL
          OR NEW.created_at != NEW.updated_at
        THEN RAISE(ABORT, 'policy event timestamps must be immutable')
    END;
    SELECT CASE
        WHEN NEW.event_type != 'subject_adjustment_notice'
        THEN RAISE(ABORT, 'unsupported policy event type')
    END;
    SELECT CASE
        WHEN NEW.event_status != 'pending_directory'
        THEN RAISE(ABORT, 'subject adjustment notice must remain pending_directory')
    END;
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM evidence_sources source
            WHERE source.id = NEW.source_id
              AND source.evidence_grade = 'official'
              AND source.document_type = 'official_notice'
              AND source.applicable_year = NEW.effective_year
              AND source.content_sha256 = NEW.source_content_sha256
        )
        THEN RAISE(ABORT, 'policy event source metadata mismatch')
    END;
    SELECT CASE
        WHEN NEW.project_id IS NOT NULL
         AND NOT EXISTS (
             SELECT 1
             FROM projects project
             WHERE project.id = NEW.project_id
               AND project.school_id = NEW.school_id
         )
        THEN RAISE(ABORT, 'policy event project-school mismatch')
    END;
    SELECT CASE
        WHEN NEW.supersedes_event_id IS NOT NULL
         AND NOT EXISTS (
             SELECT 1
             FROM policy_events previous
             WHERE previous.id = NEW.supersedes_event_id
               AND previous.school_id = NEW.school_id
               AND previous.project_id IS NEW.project_id
               AND previous.effective_year = NEW.effective_year
               AND previous.event_type = NEW.event_type
         )
        THEN RAISE(ABORT, 'policy event supersession mismatch')
    END;
END;

CREATE TRIGGER protect_policy_events_update
BEFORE UPDATE ON policy_events
BEGIN
    SELECT RAISE(ABORT, 'policy_events are append-only');
END;

CREATE TRIGGER protect_policy_events_delete
BEFORE DELETE ON policy_events
BEGIN
    SELECT RAISE(ABORT, 'policy_events are append-only');
END;

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
    source.title AS source_title,
    source.institution AS source_institution,
    source.url AS source_url,
    source.document_type AS source_document_type,
    event.source_content_sha256,
    source.applicable_year,
    source.published_date,
    source.retrieved_date,
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
JOIN evidence_sources source ON source.id = event.source_id;
