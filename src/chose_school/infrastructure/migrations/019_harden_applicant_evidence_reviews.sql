ALTER TABLE applicant_achievement_events
    ADD COLUMN fingerprint_version TEXT NOT NULL DEFAULT 'v1'
        CHECK (fingerprint_version IN ('v1', 'v2'));

CREATE TABLE applicant_evidence_review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_document_id INTEGER NOT NULL
        REFERENCES applicant_evidence_documents(id) ON DELETE RESTRICT,
    source_reviewed_on TEXT NOT NULL CHECK (
        length(source_reviewed_on) = 10
        AND date(source_reviewed_on) = source_reviewed_on
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
    review_fingerprint TEXT NOT NULL CHECK (
        length(review_fingerprint) = 64
        AND review_fingerprint = lower(review_fingerprint)
        AND review_fingerprint NOT GLOB '*[^0-9a-f]*'
    ),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    CHECK (
        evidence_status != 'document_visual_confirmed'
        OR review_method IN (
            'full_document_visual_review', 'combined_visual_and_text'
        )
    ),
    UNIQUE (evidence_document_id, review_fingerprint)
);

CREATE INDEX ix_applicant_evidence_reviews_document
    ON applicant_evidence_review_events(evidence_document_id, id DESC);

CREATE INDEX ix_applicant_evidence_reviews_trace
    ON applicant_evidence_review_events(trace_id, created_at);

CREATE TRIGGER applicant_evidence_review_events_validate_insert
BEFORE INSERT ON applicant_evidence_review_events
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM applicant_evidence_documents document
            WHERE document.id = NEW.evidence_document_id
        )
        THEN RAISE(ABORT, 'evidence review document does not exist')
    END;
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM applicant_evidence_documents document
            WHERE document.id = NEW.evidence_document_id
              AND date(NEW.source_reviewed_on)
                  >= date(document.source_retrieved_on)
        )
        THEN RAISE(
            ABORT,
            'evidence review date cannot precede document retrieval'
        )
    END;
END;

CREATE TRIGGER applicant_evidence_review_events_no_update
BEFORE UPDATE ON applicant_evidence_review_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_evidence_review_events are append-only');
END;

CREATE TRIGGER applicant_evidence_review_events_no_delete
BEFORE DELETE ON applicant_evidence_review_events
BEGIN
    SELECT RAISE(ABORT, 'applicant_evidence_review_events are append-only');
END;

CREATE TABLE applicant_achievement_evidence_review_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_evidence_link_id INTEGER NOT NULL
        REFERENCES applicant_achievement_evidence_links(id) ON DELETE RESTRICT,
    evidence_review_event_id INTEGER NOT NULL
        REFERENCES applicant_evidence_review_events(id) ON DELETE RESTRICT,
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL,
    UNIQUE (achievement_evidence_link_id)
);

CREATE INDEX ix_applicant_achievement_evidence_reviews_link
    ON applicant_achievement_evidence_review_links(
        achievement_evidence_link_id,
        id DESC
    );

CREATE INDEX ix_applicant_achievement_evidence_reviews_review
    ON applicant_achievement_evidence_review_links(
        evidence_review_event_id,
        id
    );

CREATE INDEX ix_applicant_achievement_evidence_reviews_trace
    ON applicant_achievement_evidence_review_links(trace_id, created_at);

CREATE TRIGGER applicant_achievement_evidence_review_links_validate_insert
BEFORE INSERT ON applicant_achievement_evidence_review_links
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM applicant_achievement_evidence_links achievement_link
            JOIN applicant_evidence_review_events review
              ON review.id = NEW.evidence_review_event_id
             AND review.evidence_document_id = achievement_link.evidence_document_id
            WHERE achievement_link.id = NEW.achievement_evidence_link_id
        )
        THEN RAISE(
            ABORT,
            'achievement evidence link and review must use the same document'
        )
    END;
END;

CREATE TRIGGER applicant_achievement_evidence_review_links_no_update
BEFORE UPDATE ON applicant_achievement_evidence_review_links
BEGIN
    SELECT RAISE(
        ABORT,
        'applicant_achievement_evidence_review_links are append-only'
    );
END;

CREATE TRIGGER applicant_achievement_evidence_review_links_no_delete
BEFORE DELETE ON applicant_achievement_evidence_review_links
BEGIN
    SELECT RAISE(
        ABORT,
        'applicant_achievement_evidence_review_links are append-only'
    );
END;

INSERT INTO applicant_evidence_review_events(
    evidence_document_id,
    source_reviewed_on,
    review_method,
    evidence_grade,
    evidence_status,
    claim_text,
    note,
    review_fingerprint,
    trace_id,
    created_at
)
SELECT
    document.id,
    document.source_reviewed_on,
    document.review_method,
    document.evidence_grade,
    document.evidence_status,
    document.claim_text,
    document.note,
    document.source_content_sha256,
    'migration-019-legacy-evidence-review-' || document.id,
    document.created_at
FROM applicant_evidence_documents document
ORDER BY document.id;

INSERT INTO audit_events(
    trace_id,
    event_type,
    entity_type,
    entity_id,
    payload_json,
    created_at
)
SELECT
    review.trace_id,
    'applicant_evidence_review_event_backfilled',
    'applicant_evidence_review_event',
    CAST(review.id AS TEXT),
    json_object(
        'evidence_document_id', review.evidence_document_id,
        'review_fingerprint', review.review_fingerprint,
        'backfill_source', 'applicant_evidence_documents'
    ),
    review.created_at
FROM applicant_evidence_review_events review
ORDER BY review.id;

INSERT INTO applicant_achievement_evidence_review_links(
    achievement_evidence_link_id,
    evidence_review_event_id,
    trace_id,
    created_at
)
SELECT
    achievement_link.id,
    review.id,
    'migration-019-legacy-achievement-evidence-review-link-'
        || achievement_link.id,
    achievement_link.created_at
FROM applicant_achievement_evidence_links achievement_link
JOIN applicant_evidence_review_events review
  ON review.evidence_document_id = achievement_link.evidence_document_id
JOIN applicant_evidence_documents document
  ON document.id = achievement_link.evidence_document_id
 AND document.source_content_sha256 = review.review_fingerprint
ORDER BY achievement_link.id;

INSERT INTO audit_events(
    trace_id,
    event_type,
    entity_type,
    entity_id,
    payload_json,
    created_at
)
SELECT
    review_link.trace_id,
    'applicant_achievement_evidence_review_link_backfilled',
    'applicant_achievement_evidence_review_link',
    CAST(review_link.id AS TEXT),
    json_object(
        'achievement_evidence_link_id',
        review_link.achievement_evidence_link_id,
        'evidence_review_event_id',
        review_link.evidence_review_event_id,
        'backfill_source', 'applicant_achievement_evidence_links'
    ),
    review_link.created_at
FROM applicant_achievement_evidence_review_links review_link
ORDER BY review_link.id;

-- 旧行必须原样迁移；迁移完成后，在建立发证方主体、官方域名和在线
-- 核验快照的闭环模型之前，任何新行都不得自报为“官方在线验真”。
CREATE TRIGGER applicant_evidence_review_events_block_official_insert
BEFORE INSERT ON applicant_evidence_review_events
WHEN NEW.evidence_grade = 'official_online_verification'
BEGIN
    SELECT RAISE(
        ABORT,
        'official online verification is not configured'
    );
END;

CREATE TRIGGER applicant_evidence_documents_block_official_insert
BEFORE INSERT ON applicant_evidence_documents
WHEN NEW.evidence_grade = 'official_online_verification'
BEGIN
    SELECT RAISE(
        ABORT,
        'official online verification is not configured'
    );
END;

CREATE TRIGGER applicant_achievement_links_block_confirmed_contradiction
BEFORE INSERT ON applicant_achievement_evidence_links
WHEN NEW.relationship = 'contradicts'
 AND EXISTS (
     SELECT 1
     FROM applicant_achievement_events event
     WHERE event.id = NEW.achievement_event_id
       AND event.verification_status = 'document_confirmed'
 )
BEGIN
    SELECT RAISE(
        ABORT,
        'document-confirmed achievement cannot link contradictory evidence'
    );
END;

CREATE TRIGGER applicant_achievement_review_links_block_confirmed_conflict
BEFORE INSERT ON applicant_achievement_evidence_review_links
WHEN EXISTS (
    SELECT 1
    FROM applicant_achievement_evidence_links achievement_link
    JOIN applicant_achievement_events event
      ON event.id = achievement_link.achievement_event_id
    JOIN applicant_evidence_review_events review
      ON review.id = NEW.evidence_review_event_id
    WHERE achievement_link.id = NEW.achievement_evidence_link_id
      AND event.verification_status = 'document_confirmed'
      AND review.evidence_status = 'conflict'
)
BEGIN
    SELECT RAISE(
        ABORT,
        'document-confirmed achievement cannot use a conflicting review'
    );
END;
