INSERT INTO data_quality_issues(
    issue_fingerprint, batch_id, raw_row_id, observation_id, issue_code,
    severity, field_name, raw_value, message, status, created_at
)
SELECT
    'migration005:missing-source:' || o.id,
    sf.batch_id,
    o.raw_row_id,
    o.id,
    'MISSING_SOURCE_REFERENCE',
    'warning',
    'official_source',
    NULL,
    'record has no source reference and cannot be independently audited',
    'open',
    CURRENT_TIMESTAMP
FROM project_year_observations o
JOIN raw_catalog_rows r ON r.id = o.raw_row_id
JOIN source_files sf ON sf.id = r.source_file_id
WHERE o.official_source IS NULL;

INSERT INTO data_quality_issues(
    issue_fingerprint, batch_id, raw_row_id, observation_id, issue_code,
    severity, field_name, raw_value, message, status, created_at
)
SELECT
    'migration005:composite-code:' || o.id,
    sf.batch_id,
    o.raw_row_id,
    o.id,
    'COMPOSITE_PROGRAM_CODE',
    'warning',
    'program_code',
    p.program_code,
    'multiple program codes share one aggregate row and were not split automatically',
    'open',
    CURRENT_TIMESTAMP
FROM project_year_observations o
JOIN projects p ON p.id = o.project_id
JOIN raw_catalog_rows r ON r.id = o.raw_row_id
JOIN source_files sf ON sf.id = r.source_file_id
WHERE p.program_code LIKE '%/%';
