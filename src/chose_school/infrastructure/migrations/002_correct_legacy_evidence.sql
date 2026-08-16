UPDATE project_year_observations
SET evidence_grade = 'official_mixed',
    updated_at = CURRENT_TIMESTAMP
WHERE source_level_raw LIKE '%A%'
  AND source_level_raw LIKE '%B%'
  AND evidence_grade = 'unknown';

UPDATE evidence_sources
SET evidence_grade = 'official_mixed',
    updated_at = CURRENT_TIMESTAMP
WHERE id IN (
    SELECT os.source_id
    FROM observation_sources os
    JOIN project_year_observations o ON o.id = os.observation_id
    WHERE o.evidence_grade = 'official_mixed'
);

UPDATE project_year_observations
SET strict_22408_evidence_status = 'official_pending_catalog',
    updated_at = CURRENT_TIMESTAMP
WHERE admission_year = 2027
  AND strict_22408_claim = 'yes'
  AND evidence_grade IN ('official', 'official_mixed')
  AND (notes LIKE '%待%' OR notes LIKE '%目录%' OR notes LIKE '%最终%');
