CREATE TABLE evidence_source_metadata_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correction_fingerprint TEXT NOT NULL UNIQUE
        CHECK (
            length(correction_fingerprint) = 64
            AND correction_fingerprint = lower(correction_fingerprint)
            AND correction_fingerprint NOT GLOB '*[^0-9a-f]*'
        ),
    source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
    source_content_sha256 TEXT NOT NULL
        CHECK (
            length(source_content_sha256) = 64
            AND source_content_sha256 = lower(source_content_sha256)
            AND source_content_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    field_name TEXT NOT NULL
        CHECK (field_name IN ('published_date', 'source_note')),
    prior_effective_value TEXT,
    corrected_value TEXT NOT NULL
        CHECK (
            length(trim(corrected_value)) > 0
            AND corrected_value IS NOT prior_effective_value
        ),
    supersedes_correction_id INTEGER
        REFERENCES evidence_source_metadata_corrections(id),
    basis_url TEXT NOT NULL CHECK (basis_url LIKE 'https://%'),
    basis_content_sha256 TEXT NOT NULL
        CHECK (
            length(basis_content_sha256) = 64
            AND basis_content_sha256 = lower(basis_content_sha256)
            AND basis_content_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    basis_retrieved_date TEXT NOT NULL
        CHECK (
            length(basis_retrieved_date) = 10
            AND date(basis_retrieved_date) = basis_retrieved_date
        ),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    trace_id TEXT NOT NULL CHECK (length(trim(trace_id)) > 0),
    created_at TEXT NOT NULL
        CHECK (
            length(trim(created_at)) > 0
            AND datetime(created_at) IS NOT NULL
        )
);

CREATE INDEX ix_evidence_source_metadata_corrections_lookup
    ON evidence_source_metadata_corrections(source_id, field_name, id);

CREATE UNIQUE INDEX ux_evidence_source_metadata_corrections_root
    ON evidence_source_metadata_corrections(source_id, field_name)
    WHERE supersedes_correction_id IS NULL;

CREATE UNIQUE INDEX ux_evidence_source_metadata_corrections_successor
    ON evidence_source_metadata_corrections(supersedes_correction_id)
    WHERE supersedes_correction_id IS NOT NULL;

CREATE UNIQUE INDEX ux_audit_evidence_source_metadata_correction_event
    ON audit_events(event_type, entity_type, entity_id)
    WHERE event_type = 'evidence_source_metadata_corrected'
      AND entity_type = 'evidence_source_metadata_correction';

CREATE TRIGGER evidence_source_metadata_corrections_validate_insert
BEFORE INSERT ON evidence_source_metadata_corrections
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM evidence_sources source
            WHERE source.id = NEW.source_id
              AND source.content_sha256 = NEW.source_content_sha256
        )
        THEN RAISE(ABORT, 'correction source hash does not match evidence source')
        WHEN NEW.field_name = 'published_date'
         AND (
            length(NEW.corrected_value) != 10
            OR date(NEW.corrected_value) IS NOT NEW.corrected_value
         )
        THEN RAISE(ABORT, 'corrected published_date must be an ISO date')
        WHEN NEW.supersedes_correction_id IS NULL
         AND EXISTS (
            SELECT 1
            FROM evidence_source_metadata_corrections existing
            WHERE existing.source_id = NEW.source_id
              AND existing.field_name = NEW.field_name
         )
        THEN RAISE(ABORT, 'correction chain already has a root')
        WHEN NEW.supersedes_correction_id IS NULL
         AND NEW.prior_effective_value IS NOT (
            SELECT CASE NEW.field_name
                WHEN 'published_date' THEN source.published_date
                WHEN 'source_note' THEN source.source_note
            END
            FROM evidence_sources source
            WHERE source.id = NEW.source_id
         )
        THEN RAISE(ABORT, 'root correction prior value must match raw source value')
        WHEN NEW.supersedes_correction_id IS NOT NULL
         AND NOT EXISTS (
            SELECT 1
            FROM evidence_source_metadata_corrections predecessor
            WHERE predecessor.id = NEW.supersedes_correction_id
              AND predecessor.source_id = NEW.source_id
              AND predecessor.source_content_sha256 = NEW.source_content_sha256
              AND predecessor.field_name = NEW.field_name
              AND predecessor.corrected_value IS NEW.prior_effective_value
         )
        THEN RAISE(ABORT, 'successor must continue the same correction chain and prior value')
        WHEN NEW.supersedes_correction_id IS NOT NULL
         AND EXISTS (
            SELECT 1
            FROM evidence_source_metadata_corrections successor
            WHERE successor.supersedes_correction_id = NEW.supersedes_correction_id
         )
        THEN RAISE(ABORT, 'correction chain cannot branch')
    END;
END;

CREATE TRIGGER evidence_source_metadata_corrections_audit_insert
AFTER INSERT ON evidence_source_metadata_corrections
BEGIN
    INSERT INTO audit_events(
        trace_id,
        event_type,
        entity_type,
        entity_id,
        payload_json,
        created_at
    ) VALUES (
        NEW.trace_id,
        'evidence_source_metadata_corrected',
        'evidence_source_metadata_correction',
        CAST(NEW.id AS TEXT),
        json_object(
            'correction_fingerprint', NEW.correction_fingerprint,
            'source_id', NEW.source_id,
            'source_content_sha256', NEW.source_content_sha256,
            'field_name', NEW.field_name,
            'prior_effective_value', NEW.prior_effective_value,
            'corrected_value', NEW.corrected_value,
            'supersedes_correction_id', NEW.supersedes_correction_id,
            'basis_url', NEW.basis_url,
            'basis_content_sha256', NEW.basis_content_sha256,
            'basis_retrieved_date', NEW.basis_retrieved_date
        ),
        NEW.created_at
    );
END;

CREATE TRIGGER protect_evidence_source_metadata_corrections_update
BEFORE UPDATE ON evidence_source_metadata_corrections
BEGIN
    SELECT RAISE(ABORT, 'evidence_source_metadata_corrections are append-only');
END;

CREATE TRIGGER protect_evidence_source_metadata_corrections_delete
BEFORE DELETE ON evidence_source_metadata_corrections
BEGIN
    SELECT RAISE(ABORT, 'evidence_source_metadata_corrections are append-only');
END;

CREATE TRIGGER protect_evidence_sources_material_update
BEFORE UPDATE OF
    id,
    identity_key,
    title,
    institution,
    url,
    evidence_grade,
    published_date,
    retrieved_date,
    source_note,
    created_at,
    document_type,
    content_sha256,
    applicable_year
ON evidence_sources
BEGIN
    SELECT RAISE(ABORT, 'evidence_sources material fields are immutable');
END;

CREATE TRIGGER protect_evidence_sources_delete
BEFORE DELETE ON evidence_sources
BEGIN
    SELECT RAISE(ABORT, 'evidence_sources are immutable');
END;

CREATE VIEW v_current_evidence_source_metadata_corrections AS
SELECT correction.*
FROM evidence_source_metadata_corrections correction
WHERE NOT EXISTS (
    SELECT 1
    FROM evidence_source_metadata_corrections successor
    WHERE successor.supersedes_correction_id = correction.id
);

CREATE VIEW v_evidence_sources_effective AS
SELECT
    source.id,
    source.identity_key,
    source.title,
    source.institution,
    source.url,
    source.evidence_grade,
    source.published_date AS original_published_date,
    COALESCE(published_date.corrected_value, source.published_date)
        AS effective_published_date,
    COALESCE(published_date.corrected_value, source.published_date)
        AS published_date,
    source.retrieved_date,
    source.source_note AS original_source_note,
    COALESCE(source_note.corrected_value, source.source_note)
        AS effective_source_note,
    COALESCE(source_note.corrected_value, source.source_note)
        AS source_note,
    source.created_at,
    source.updated_at,
    source.document_type,
    source.content_sha256,
    source.applicable_year,
    published_date.id AS published_date_correction_id,
    published_date.correction_fingerprint AS published_date_correction_fingerprint,
    published_date.source_content_sha256
        AS published_date_correction_source_content_sha256,
    published_date.prior_effective_value
        AS published_date_prior_effective_value,
    published_date.supersedes_correction_id
        AS published_date_supersedes_correction_id,
    published_date.basis_url AS published_date_correction_basis_url,
    published_date.basis_content_sha256
        AS published_date_correction_basis_content_sha256,
    published_date.basis_retrieved_date
        AS published_date_correction_basis_retrieved_date,
    published_date.reason AS published_date_correction_reason,
    published_date.trace_id AS published_date_correction_trace_id,
    published_date.created_at AS published_date_correction_created_at,
    source_note.id AS source_note_correction_id,
    source_note.correction_fingerprint AS source_note_correction_fingerprint,
    source_note.source_content_sha256
        AS source_note_correction_source_content_sha256,
    source_note.prior_effective_value AS source_note_prior_effective_value,
    source_note.supersedes_correction_id AS source_note_supersedes_correction_id,
    source_note.basis_url AS source_note_correction_basis_url,
    source_note.basis_content_sha256
        AS source_note_correction_basis_content_sha256,
    source_note.basis_retrieved_date
        AS source_note_correction_basis_retrieved_date,
    source_note.reason AS source_note_correction_reason,
    source_note.trace_id AS source_note_correction_trace_id,
    source_note.created_at AS source_note_correction_created_at
FROM evidence_sources source
LEFT JOIN v_current_evidence_source_metadata_corrections published_date
  ON published_date.source_id = source.id
 AND published_date.field_name = 'published_date'
LEFT JOIN v_current_evidence_source_metadata_corrections source_note
  ON source_note.source_id = source.id
 AND source_note.field_name = 'source_note';

INSERT INTO evidence_source_metadata_corrections(
    correction_fingerprint,
    source_id,
    source_content_sha256,
    field_name,
    prior_effective_value,
    corrected_value,
    supersedes_correction_id,
    basis_url,
    basis_content_sha256,
    basis_retrieved_date,
    reason,
    trace_id,
    created_at
)
SELECT
    'e93839bf2b6490c9af24002a610c2ce353560ca4473a86e525dae1c2f0c3ef5d',
    source.id,
    source.content_sha256,
    'published_date',
    source.published_date,
    '2025-09-30',
    NULL,
    'https://yjsy.ncu.edu.cn/info/1012/23946.htm',
    'ad7168a8a7f8b1bdb705db9a70be44f272514e50011befe45817ab1f14bab93e',
    '2026-08-13',
    '官网目录落地页发布日期为2025-09-30；原值2025-10-15是PDF元数据创建日，不能冒充网页发布日期。',
    'bb2b775b-56f0-4321-8868-59fe091b70cd',
    '2026-08-13T10:00:00+08:00'
FROM evidence_sources source
WHERE source.identity_key =
        'a0f610b3532fa8f89f52bed5bcef29b4080e37deaf7209296e9667211f55e449'
  AND source.content_sha256 =
        '92cbb1ec97347292ad9dddf77a3a4aac98900274b47cad439ad59dc34bb64c7c'
  AND source.published_date IS '2025-10-15';

INSERT INTO evidence_source_metadata_corrections(
    correction_fingerprint,
    source_id,
    source_content_sha256,
    field_name,
    prior_effective_value,
    corrected_value,
    supersedes_correction_id,
    basis_url,
    basis_content_sha256,
    basis_retrieved_date,
    reason,
    trace_id,
    created_at
)
SELECT
    '9aac0cf9b5d78711c6246477a99160fac4bbedd0706728ee8f9f26413df1b7a3',
    source.id,
    source.content_sha256,
    'published_date',
    source.published_date,
    '2025-09-30',
    NULL,
    'https://yjsy.ncu.edu.cn/info/1012/23946.htm',
    'ad7168a8a7f8b1bdb705db9a70be44f272514e50011befe45817ab1f14bab93e',
    '2026-08-13',
    '官网目录落地页发布日期为2025-09-30；原值2025-10-15是PDF元数据创建日，不能冒充网页发布日期。',
    'a7257f7b-863a-48f4-b398-a6fe618e76dd',
    '2026-08-13T10:00:01+08:00'
FROM evidence_sources source
WHERE source.identity_key =
        '73b98d3fce8726d8a900c1d3bf8a8a7df68f3fa8a9235beee6a8af84bc78c47b'
  AND source.content_sha256 =
        '92cbb1ec97347292ad9dddf77a3a4aac98900274b47cad439ad59dc34bb64c7c'
  AND source.published_date IS '2025-10-15';

INSERT INTO evidence_source_metadata_corrections(
    correction_fingerprint,
    source_id,
    source_content_sha256,
    field_name,
    prior_effective_value,
    corrected_value,
    supersedes_correction_id,
    basis_url,
    basis_content_sha256,
    basis_retrieved_date,
    reason,
    trace_id,
    created_at
)
SELECT
    'd8f216e8296c429ed91830e31763691c94ecb61d5edeee56be829384ad1cdb92',
    source.id,
    source.content_sha256,
    'source_note',
    source.source_note,
    '该原件仅能证明名单列示的专业代码、一志愿、全日制和非定向属性；名单无专项计划列，不能据此排除专项。各项目行数须在项目级事实中记录。',
    NULL,
    'https://grs.lnu.edu.cn/2026ssyzymd.pdf',
    'a923c330057d4478aae158aae27cf190e07ae7232988e46d9567909364918957',
    '2026-08-13',
    '原说明声称已逐行剔除专项，但共享名单来源无专项计划列；纠正为跨项目通用的可直接复核边界，项目筛选结果留在项目级事实。',
    'f779c6db-c5a4-4f50-a262-0b4f5471f6fa',
    '2026-08-13T10:00:02+08:00'
FROM evidence_sources source
WHERE source.identity_key =
        'dbced694ad90eb3d222d472351c2f2853abeefaedfd55bec8e8329efe483b02e'
  AND source.content_sha256 =
        'a923c330057d4478aae158aae27cf190e07ae7232988e46d9567909364918957'
  AND source.source_note IS
        '逐行剔除调剂、非全和专项；本项目名单均为一志愿全日制非定向。';
