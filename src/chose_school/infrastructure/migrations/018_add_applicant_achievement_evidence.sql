CREATE TABLE applicant_evidence_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    source_title TEXT NOT NULL CHECK (
        length(trim(source_title)) BETWEEN 1 AND 500
    ),
    source_url TEXT NOT NULL CHECK (
        (source_access_scope = 'local_user_file' AND source_url LIKE 'file:///%')
        OR (
            source_access_scope != 'local_user_file'
            AND source_url LIKE 'https://%'
        )
    ),
    source_access_scope TEXT NOT NULL CHECK (
        source_access_scope IN ('private_user_drive', 'public_web', 'local_user_file')
    ),
    source_document_type TEXT NOT NULL CHECK (
        source_document_type IN (
            'award_certificate', 'scholarship_certificate',
            'score_certificate', 'award_proof'
        )
    ),
    source_mime_type TEXT NOT NULL CHECK (
        source_mime_type IN ('application/pdf', 'image/jpeg', 'image/png')
    ),
    source_content_sha256 TEXT NOT NULL CHECK (
        length(source_content_sha256) = 64
        AND source_content_sha256 = lower(source_content_sha256)
        AND source_content_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    source_file_size_bytes INTEGER NOT NULL CHECK (source_file_size_bytes > 0),
    source_retrieved_on TEXT NOT NULL CHECK (
        length(source_retrieved_on) = 10
        AND date(source_retrieved_on) = source_retrieved_on
    ),
    source_reviewed_on TEXT NOT NULL CHECK (
        length(source_reviewed_on) = 10
        AND date(source_reviewed_on) = source_reviewed_on
        AND date(source_reviewed_on) >= date(source_retrieved_on)
    ),
    review_method TEXT NOT NULL CHECK (
        review_method IN (
            'full_document_visual_review', 'combined_visual_and_text',
            'ocr_only', 'metadata_only', 'not_reviewed'
        )
    ),
    evidence_grade TEXT NOT NULL CHECK (
        evidence_grade IN (
            'primary_document_user_copy', 'official_online_verification',
            'self_reported', 'unknown'
        )
    ),
    evidence_status TEXT NOT NULL CHECK (
        evidence_status IN (
            'document_visual_confirmed', 'metadata_only',
            'self_reported', 'conflict'
        )
    ),
    claim_text TEXT NOT NULL CHECK (
        length(trim(claim_text)) BETWEEN 1 AND 1000
    ),
    note TEXT CHECK (note IS NULL OR length(note) <= 2000),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    CHECK (
        evidence_status != 'document_visual_confirmed'
        OR review_method IN (
            'full_document_visual_review', 'combined_visual_and_text'
        )
    ),
    CHECK (
        evidence_grade != 'official_online_verification'
        OR source_access_scope = 'public_web'
    ),
    UNIQUE (profile_id, source_content_sha256)
);

CREATE INDEX ix_applicant_evidence_source
    ON applicant_evidence_documents(profile_id, source_content_sha256);

CREATE INDEX ix_applicant_evidence_trace
    ON applicant_evidence_documents(trace_id, created_at);

CREATE TRIGGER applicant_evidence_documents_no_update
BEFORE UPDATE ON applicant_evidence_documents
BEGIN
    SELECT RAISE(ABORT, 'applicant_evidence_documents are append-only');
END;

CREATE TRIGGER applicant_evidence_documents_no_delete
BEFORE DELETE ON applicant_evidence_documents
BEGIN
    SELECT RAISE(ABORT, 'applicant_evidence_documents are append-only');
END;

CREATE TABLE applicant_achievement_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    achievement_key TEXT NOT NULL CHECK (
        length(trim(achievement_key)) BETWEEN 3 AND 160
    ),
    category TEXT NOT NULL CHECK (
        category IN ('competition_award', 'scholarship', 'ability_certificate')
    ),
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 300),
    issuer TEXT NOT NULL CHECK (length(trim(issuer)) BETWEEN 1 AND 300),
    achievement_year INTEGER NOT NULL CHECK (
        achievement_year BETWEEN 2000 AND 2100
    ),
    period_label TEXT NOT NULL CHECK (
        length(trim(period_label)) BETWEEN 1 AND 120
    ),
    awarded_on TEXT CHECK (
        awarded_on IS NULL OR (
            length(awarded_on) = 10
            AND date(awarded_on) = awarded_on
        )
    ),
    scope_level TEXT NOT NULL CHECK (
        scope_level IN (
            'national', 'provincial', 'school',
            'unspecified', 'not_applicable'
        )
    ),
    stage TEXT NOT NULL CHECK (
        stage IN (
            'national_final', 'provincial_round', 'preliminary_round',
            'popularization', 'academic_year', 'assessment'
        )
    ),
    result TEXT NOT NULL CHECK (length(trim(result)) BETWEEN 1 AND 200),
    participation_type TEXT NOT NULL CHECK (
        participation_type IN ('individual', 'team', 'not_applicable', 'unknown')
    ),
    team_name TEXT CHECK (
        team_name IS NULL OR length(trim(team_name)) BETWEEN 1 AND 200
    ),
    details_json TEXT NOT NULL DEFAULT '{}' CHECK (
        json_valid(details_json) AND json_type(details_json) = 'object'
    ),
    verification_status TEXT NOT NULL CHECK (
        verification_status IN (
            'document_confirmed', 'metadata_only', 'self_reported', 'conflict'
        )
    ),
    event_fingerprint TEXT NOT NULL CHECK (
        length(event_fingerprint) = 64
        AND event_fingerprint = lower(event_fingerprint)
        AND event_fingerprint NOT GLOB '*[^0-9a-f]*'
    ),
    note TEXT CHECK (note IS NULL OR length(note) <= 2000),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    CHECK (
        awarded_on IS NULL
        OR CAST(substr(awarded_on, 1, 4) AS INTEGER) = achievement_year
    ),
    CHECK (
        (participation_type = 'team' AND team_name IS NOT NULL)
        OR (participation_type != 'team' AND team_name IS NULL)
    ),
    CHECK (
        category != 'scholarship'
        OR (
            stage = 'academic_year'
            AND participation_type = 'not_applicable'
        )
    ),
    UNIQUE (profile_id, event_fingerprint)
);

CREATE INDEX ix_applicant_achievement_identity
    ON applicant_achievement_events(profile_id, achievement_key, id DESC);

CREATE INDEX ix_applicant_achievement_year_category
    ON applicant_achievement_events(
        profile_id, achievement_year, category, id DESC
    );

CREATE INDEX ix_applicant_achievement_trace
    ON applicant_achievement_events(trace_id, created_at);

CREATE TRIGGER applicant_achievement_events_no_update
BEFORE UPDATE ON applicant_achievement_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_achievement_events are append-only');
END;

CREATE TRIGGER applicant_achievement_events_no_delete
BEFORE DELETE ON applicant_achievement_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_achievement_events are append-only');
END;

CREATE TABLE applicant_achievement_evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_event_id INTEGER NOT NULL
        REFERENCES applicant_achievement_events(id) ON DELETE RESTRICT,
    evidence_document_id INTEGER NOT NULL
        REFERENCES applicant_evidence_documents(id) ON DELETE RESTRICT,
    relationship TEXT NOT NULL CHECK (
        relationship IN ('supports', 'contradicts', 'context')
    ),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    UNIQUE (achievement_event_id, evidence_document_id, relationship)
);

CREATE INDEX ix_applicant_achievement_evidence_document
    ON applicant_achievement_evidence_links(evidence_document_id, id);

CREATE INDEX ix_applicant_achievement_evidence_trace
    ON applicant_achievement_evidence_links(trace_id, created_at);

CREATE TRIGGER applicant_achievement_evidence_links_no_update
BEFORE UPDATE ON applicant_achievement_evidence_links
BEGIN
    SELECT RAISE(ABORT, 'applicant_achievement_evidence_links are append-only');
END;

CREATE TRIGGER applicant_achievement_evidence_links_no_delete
BEFORE DELETE ON applicant_achievement_evidence_links
BEGIN
    SELECT RAISE(ABORT, 'applicant_achievement_evidence_links are append-only');
END;

CREATE VIEW v_current_applicant_achievements AS
SELECT event.*
FROM applicant_achievement_events event
WHERE event.id = (
    SELECT MAX(candidate.id)
    FROM applicant_achievement_events candidate
    WHERE candidate.profile_id = event.profile_id
      AND candidate.achievement_key = event.achievement_key
);
