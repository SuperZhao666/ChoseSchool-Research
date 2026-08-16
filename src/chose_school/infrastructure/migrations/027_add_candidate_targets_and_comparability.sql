CREATE TABLE candidate_target_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL
        REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    candidate_key TEXT NOT NULL CHECK (
        length(candidate_key) = 77
        AND candidate_key LIKE 'candidate-v1:%'
        AND substr(candidate_key, 14) = identity_canonical_sha256
    ),
    identity_schema TEXT NOT NULL CHECK (
        identity_schema = 'candidate-target-identity-v1'
    ),
    profile_key_snapshot TEXT NOT NULL
        CHECK (length(trim(profile_key_snapshot)) BETWEEN 1 AND 120),
    target_year INTEGER NOT NULL CHECK (target_year BETWEEN 2000 AND 2100),
    school_key TEXT NOT NULL CHECK (length(trim(school_key)) BETWEEN 1 AND 200),
    college_key TEXT NOT NULL CHECK (length(trim(college_key)) BETWEEN 1 AND 200),
    program_code TEXT NOT NULL CHECK (length(trim(program_code)) BETWEEN 1 AND 40),
    program_name TEXT NOT NULL CHECK (length(trim(program_name)) BETWEEN 1 AND 200),
    direction_key TEXT NOT NULL CHECK (length(trim(direction_key)) BETWEEN 1 AND 300),
    campus_key TEXT NOT NULL CHECK (length(trim(campus_key)) BETWEEN 1 AND 200),
    training_location_key TEXT NOT NULL
        CHECK (length(trim(training_location_key)) BETWEEN 1 AND 200),
    study_mode_key TEXT NOT NULL CHECK (length(trim(study_mode_key)) BETWEEN 1 AND 80),
    training_type_key TEXT NOT NULL
        CHECK (length(trim(training_type_key)) BETWEEN 1 AND 120),
    admission_type_key TEXT NOT NULL
        CHECK (length(trim(admission_type_key)) BETWEEN 1 AND 120),
    degree_type_key TEXT NOT NULL CHECK (length(trim(degree_type_key)) BETWEEN 1 AND 120),
    training_arrangement_key TEXT NOT NULL
        CHECK (length(trim(training_arrangement_key)) BETWEEN 1 AND 300),
    target_basis TEXT NOT NULL CHECK (
        target_basis IN ('research_hypothesis', 'official_observation')
    ),
    target_project_id INTEGER REFERENCES projects(id) ON DELETE RESTRICT,
    target_observation_id INTEGER
        REFERENCES project_year_observations(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('active', 'retired')),
    identity_canonical_json TEXT NOT NULL CHECK (
        json_valid(identity_canonical_json)
        AND json_type(identity_canonical_json) = 'object'
        AND json_extract(identity_canonical_json, '$.schema') = identity_schema
        AND json_extract(identity_canonical_json, '$.profile_key') = profile_key_snapshot
        AND json_extract(identity_canonical_json, '$.target_year') = target_year
        AND json_extract(identity_canonical_json, '$.school') = school_key
        AND json_extract(identity_canonical_json, '$.college') = college_key
        AND json_extract(identity_canonical_json, '$.program_code') = program_code
        AND json_extract(identity_canonical_json, '$.program_name') = program_name
        AND json_extract(identity_canonical_json, '$.direction') = direction_key
        AND json_extract(identity_canonical_json, '$.campus') = campus_key
        AND json_extract(identity_canonical_json, '$.training_location') = training_location_key
        AND json_extract(identity_canonical_json, '$.study_mode') = study_mode_key
        AND json_extract(identity_canonical_json, '$.training_type') = training_type_key
        AND json_extract(identity_canonical_json, '$.admission_type') = admission_type_key
        AND json_extract(identity_canonical_json, '$.degree_type') = degree_type_key
        AND json_extract(identity_canonical_json, '$.training_arrangement') = training_arrangement_key
    ),
    identity_canonical_sha256 TEXT NOT NULL CHECK (
        length(identity_canonical_sha256) = 64
        AND identity_canonical_sha256 = lower(identity_canonical_sha256)
        AND identity_canonical_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    supersedes_version_id INTEGER
        REFERENCES candidate_target_versions(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 2000),
    trace_id TEXT NOT NULL CHECK (
        length(trace_id) = 36
        AND trace_id = lower(trace_id)
        AND substr(trace_id, 9, 1) = '-'
        AND substr(trace_id, 14, 1) = '-'
        AND substr(trace_id, 19, 1) = '-'
        AND substr(trace_id, 24, 1) = '-'
        AND length(replace(trace_id, '-', '')) = 32
        AND replace(trace_id, '-', '') NOT GLOB '*[^0-9a-f]*'
    ),
    created_at TEXT NOT NULL CHECK (
        length(trim(created_at)) > 0 AND datetime(created_at) IS NOT NULL
    ),
    CHECK (
        (
            target_basis = 'research_hypothesis'
            AND target_project_id IS NULL
            AND target_observation_id IS NULL
        )
        OR
        (
            target_basis = 'official_observation'
            AND target_project_id IS NOT NULL
            AND target_observation_id IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX ux_candidate_target_versions_sequence
    ON candidate_target_versions(candidate_key, version_number);
CREATE UNIQUE INDEX ux_candidate_target_versions_root
    ON candidate_target_versions(candidate_key)
    WHERE supersedes_version_id IS NULL;
CREATE UNIQUE INDEX ux_candidate_target_versions_successor
    ON candidate_target_versions(supersedes_version_id)
    WHERE supersedes_version_id IS NOT NULL;
CREATE INDEX ix_candidate_target_versions_profile_year
    ON candidate_target_versions(profile_id, target_year, action, id);
CREATE UNIQUE INDEX ux_audit_candidate_target_version_event
    ON audit_events(event_type, entity_type, entity_id)
    WHERE event_type = 'candidate_target_version_added'
      AND entity_type = 'candidate_target_version';

CREATE TRIGGER candidate_target_versions_validate_insert
BEFORE INSERT ON candidate_target_versions
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM json_each(NEW.identity_canonical_json)) != 15
        THEN RAISE(ABORT, 'candidate canonical identity must contain exactly 15 fields')
        WHEN NOT EXISTS (
            SELECT 1 FROM applicant_profiles profile
            WHERE profile.id = NEW.profile_id
              AND profile.profile_key = NEW.profile_key_snapshot
              AND profile.target_exam_year = NEW.target_year
        )
        THEN RAISE(ABORT, 'candidate profile snapshot and target year mismatch')
        WHEN NEW.target_basis = 'official_observation'
         AND NOT EXISTS (
            SELECT 1
            FROM project_year_observations observation
            JOIN projects project ON project.id = observation.project_id
            JOIN schools school ON school.id = project.school_id
            JOIN colleges college ON college.id = project.college_id
            WHERE observation.id = NEW.target_observation_id
              AND observation.project_id = NEW.target_project_id
              AND observation.admission_year = NEW.target_year
              AND school.canonical_name = NEW.school_key
              AND college.canonical_name = NEW.college_key
              AND COALESCE(NULLIF(trim(project.program_code), ''), 'unspecified') = NEW.program_code
              AND COALESCE(NULLIF(trim(project.program_name), ''), 'unspecified') = NEW.program_name
              AND COALESCE(NULLIF(trim(project.direction), ''), 'unspecified') = NEW.direction_key
              AND COALESCE(NULLIF(trim(project.campus), ''), 'unspecified') = NEW.campus_key
              AND COALESCE(NULLIF(trim(project.training_location), ''), 'unspecified') = NEW.training_location_key
              AND COALESCE(NULLIF(trim(project.study_mode), ''), 'unspecified') = NEW.study_mode_key
              AND COALESCE(NULLIF(trim(project.training_type_raw), ''), 'unspecified') = NEW.training_type_key
              AND COALESCE(NULLIF(trim(project.admission_type), ''), 'unspecified') = NEW.admission_type_key
              AND COALESCE(NULLIF(trim(project.degree_type), ''), 'unspecified') = NEW.degree_type_key
              AND COALESCE(NULLIF(trim(project.training_arrangement), ''), 'unspecified') = NEW.training_arrangement_key
              AND EXISTS (
                  SELECT 1
                  FROM observation_sources link
                  JOIN v_evidence_sources_effective source ON source.id = link.source_id
                  WHERE link.observation_id = observation.id
                    AND link.relationship = 'supports'
                    AND source.evidence_grade = 'official'
                    AND source.document_type = 'official_catalog'
                    AND source.applicable_year = NEW.target_year
                    AND length(source.content_sha256) = 64
                    AND source.content_sha256 = lower(source.content_sha256)
                    AND source.content_sha256 NOT GLOB '*[^0-9a-f]*'
                    AND source.url LIKE 'https://%'
              )
        )
        THEN RAISE(ABORT, 'official candidate target must match same-year official catalog observation')
        WHEN NEW.supersedes_version_id IS NULL AND NEW.version_number != 1
        THEN RAISE(ABORT, 'candidate target root must have version number 1')
        WHEN NEW.supersedes_version_id IS NOT NULL
         AND NOT EXISTS (
            SELECT 1 FROM candidate_target_versions predecessor
            WHERE predecessor.id = NEW.supersedes_version_id
              AND predecessor.profile_id = NEW.profile_id
              AND predecessor.candidate_key = NEW.candidate_key
              AND predecessor.identity_canonical_json = NEW.identity_canonical_json
              AND predecessor.identity_canonical_sha256 = NEW.identity_canonical_sha256
              AND predecessor.version_number + 1 = NEW.version_number
        )
        THEN RAISE(ABORT, 'candidate target successor must continue one stable candidate chain')
    END;
END;

CREATE TRIGGER candidate_target_versions_audit_insert
AFTER INSERT ON candidate_target_versions
BEGIN
    INSERT INTO audit_events(
        trace_id, event_type, entity_type, entity_id, payload_json, created_at
    ) VALUES (
        NEW.trace_id,
        'candidate_target_version_added',
        'candidate_target_version',
        CAST(NEW.id AS TEXT),
        json_object(
            'candidate_key', NEW.candidate_key,
            'identity_canonical_sha256', NEW.identity_canonical_sha256,
            'target_year', NEW.target_year,
            'target_basis', NEW.target_basis,
            'target_observation_id', NEW.target_observation_id,
            'action', NEW.action,
            'version_number', NEW.version_number,
            'supersedes_version_id', NEW.supersedes_version_id
        ),
        NEW.created_at
    );
END;

CREATE TRIGGER protect_candidate_target_versions_update
BEFORE UPDATE ON candidate_target_versions BEGIN
    SELECT RAISE(ABORT, 'candidate_target_versions are append-only');
END;
CREATE TRIGGER protect_candidate_target_versions_delete
BEFORE DELETE ON candidate_target_versions BEGIN
    SELECT RAISE(ABORT, 'candidate_target_versions are append-only');
END;

CREATE VIEW v_current_candidate_target_versions AS
SELECT version.*
FROM candidate_target_versions version
WHERE NOT EXISTS (
    SELECT 1 FROM candidate_target_versions successor
    WHERE successor.supersedes_version_id = version.id
);

CREATE VIEW v_active_candidate_targets AS
SELECT * FROM v_current_candidate_target_versions WHERE action = 'active';

CREATE TABLE project_history_comparability_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_target_version_id INTEGER NOT NULL
        REFERENCES candidate_target_versions(id) ON DELETE RESTRICT,
    historical_observation_id INTEGER NOT NULL
        REFERENCES project_year_observations(id) ON DELETE RESTRICT,
    review_contract_version TEXT NOT NULL CHECK (
        review_contract_version = 'project-history-comparability-v1'
    ),
    conclusion TEXT NOT NULL CHECK (
        conclusion IN ('comparable', 'limited', 'rejected', 'insufficient')
    ),
    dimension_contract_json TEXT NOT NULL CHECK (
        json_valid(dimension_contract_json)
        AND json_type(dimension_contract_json) = 'object'
    ),
    dimension_contract_sha256 TEXT NOT NULL CHECK (
        length(dimension_contract_sha256) = 64
        AND dimension_contract_sha256 = lower(dimension_contract_sha256)
        AND dimension_contract_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    evidence_bundle_json TEXT NOT NULL CHECK (
        json_valid(evidence_bundle_json)
        AND json_type(evidence_bundle_json) = 'array'
    ),
    evidence_bundle_sha256 TEXT NOT NULL CHECK (
        length(evidence_bundle_sha256) = 64
        AND evidence_bundle_sha256 = lower(evidence_bundle_sha256)
        AND evidence_bundle_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    review_sequence INTEGER NOT NULL CHECK (review_sequence >= 1),
    supersedes_review_id INTEGER
        REFERENCES project_history_comparability_reviews(id) ON DELETE RESTRICT,
    summary TEXT NOT NULL CHECK (length(trim(summary)) BETWEEN 1 AND 4000),
    trace_id TEXT NOT NULL CHECK (
        length(trace_id) = 36
        AND trace_id = lower(trace_id)
        AND substr(trace_id, 9, 1) = '-'
        AND substr(trace_id, 14, 1) = '-'
        AND substr(trace_id, 19, 1) = '-'
        AND substr(trace_id, 24, 1) = '-'
        AND length(replace(trace_id, '-', '')) = 32
        AND replace(trace_id, '-', '') NOT GLOB '*[^0-9a-f]*'
    ),
    created_at TEXT NOT NULL CHECK (
        length(trim(created_at)) > 0 AND datetime(created_at) IS NOT NULL
    )
);

CREATE UNIQUE INDEX ux_project_history_comparability_sequence
    ON project_history_comparability_reviews(
        candidate_target_version_id, historical_observation_id, review_sequence
    );
CREATE UNIQUE INDEX ux_project_history_comparability_root
    ON project_history_comparability_reviews(
        candidate_target_version_id, historical_observation_id
    ) WHERE supersedes_review_id IS NULL;
CREATE UNIQUE INDEX ux_project_history_comparability_successor
    ON project_history_comparability_reviews(supersedes_review_id)
    WHERE supersedes_review_id IS NOT NULL;
CREATE UNIQUE INDEX ux_audit_project_history_comparability_event
    ON audit_events(event_type, entity_type, entity_id)
    WHERE event_type = 'project_history_comparability_review_added'
      AND entity_type = 'project_history_comparability_review';

CREATE TRIGGER project_history_comparability_reviews_validate_insert
BEFORE INSERT ON project_history_comparability_reviews
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM candidate_target_versions target
            JOIN project_year_observations historical
              ON historical.id = NEW.historical_observation_id
            WHERE target.id = NEW.candidate_target_version_id
              AND historical.admission_year IS NOT NULL
              AND historical.admission_year < target.target_year
        )
        THEN RAISE(ABORT, 'historical observation must be earlier than the exact target version')
        WHEN json_extract(NEW.dimension_contract_json, '$.schema') != 'project-history-dimensions-v1'
          OR json_type(NEW.dimension_contract_json, '$.population_scope') != 'text'
          OR json_type(NEW.dimension_contract_json, '$.statistic_scope') != 'text'
          OR json_type(NEW.dimension_contract_json, '$.special_plan_handling') != 'text'
          OR json_extract(NEW.dimension_contract_json, '$.special_plan_handling')
                NOT IN ('excluded', 'included', 'separate', 'unresolved')
          OR json_type(NEW.dimension_contract_json, '$.fact_keys') != 'array'
          OR json_type(NEW.dimension_contract_json, '$.identity_dimensions') != 'object'
          OR (SELECT COUNT(*) FROM json_each(
                  NEW.dimension_contract_json, '$.identity_dimensions'
             )) != 12
          OR EXISTS (
              SELECT 1
              FROM json_each(
                  NEW.dimension_contract_json, '$.identity_dimensions'
              ) dimension
              WHERE dimension.key NOT IN (
                  'school', 'college', 'program_code', 'program_name',
                  'direction', 'campus', 'training_location', 'study_mode',
                  'training_type', 'admission_type', 'degree_type',
                  'training_arrangement'
              )
                 OR json_extract(dimension.value, '$.conclusion')
                    NOT IN ('match', 'equivalent', 'different', 'unknown')
                 OR json_type(dimension.value, '$.target') != 'text'
                 OR json_type(dimension.value, '$.historical') != 'text'
                 OR json_type(dimension.value, '$.rationale') != 'text'
          )
        THEN RAISE(ABORT, 'comparability dimension contract is incomplete')
        WHEN EXISTS (
            SELECT 1
            FROM json_each(NEW.evidence_bundle_json) item
            WHERE json_type(item.value) != 'object'
               OR json_extract(item.value, '$.role') NOT IN ('target', 'historical')
               OR json_type(item.value, '$.source_id') != 'integer'
               OR json_type(item.value, '$.content_sha256') != 'text'
               OR json_type(item.value, '$.document_type') != 'text'
               OR json_type(item.value, '$.applicable_year') != 'integer'
               OR NOT EXISTS (
                   SELECT 1
                   FROM v_evidence_sources_effective source
                   JOIN candidate_target_versions target
                     ON target.id = NEW.candidate_target_version_id
                   JOIN project_year_observations historical
                     ON historical.id = NEW.historical_observation_id
                   WHERE source.id = json_extract(item.value, '$.source_id')
                     AND source.content_sha256 = json_extract(item.value, '$.content_sha256')
                     AND source.document_type = json_extract(item.value, '$.document_type')
                     AND source.applicable_year = json_extract(item.value, '$.applicable_year')
                     AND source.url IS json_extract(item.value, '$.source_url')
                     AND (
                         (
                             json_extract(item.value, '$.role') = 'target'
                             AND target.target_observation_id IS NOT NULL
                             AND source.applicable_year = target.target_year
                             AND EXISTS (
                                 SELECT 1 FROM observation_sources link
                                 WHERE link.observation_id = target.target_observation_id
                                   AND link.source_id = source.id
                                   AND link.relationship = 'supports'
                             )
                         ) OR (
                             json_extract(item.value, '$.role') = 'historical'
                             AND source.applicable_year = historical.admission_year
                             AND EXISTS (
                                 SELECT 1 FROM observation_sources link
                                 WHERE link.observation_id = historical.id
                                   AND link.source_id = source.id
                                   AND link.relationship = 'supports'
                             )
                         )
                     )
               )
        )
        THEN RAISE(ABORT, 'comparability evidence bundle does not match immutable observation sources')
        WHEN NEW.conclusion = 'comparable' AND (
            NOT EXISTS (
                SELECT 1 FROM candidate_target_versions target
                WHERE target.id = NEW.candidate_target_version_id
                  AND target.target_basis = 'official_observation'
                  AND target.action = 'active'
            )
            OR json_array_length(json_extract(
                NEW.dimension_contract_json, '$.fact_keys'
            )) = 0
            OR json_extract(
                NEW.dimension_contract_json, '$.special_plan_handling'
            ) = 'unresolved'
            OR EXISTS (
                SELECT 1 FROM json_each(
                    NEW.dimension_contract_json, '$.identity_dimensions'
                ) dimension
                WHERE json_extract(dimension.value, '$.conclusion')
                    NOT IN ('match', 'equivalent')
            )
            OR NOT EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_bundle_json) item
                JOIN v_evidence_sources_effective source
                  ON source.id = json_extract(item.value, '$.source_id')
                WHERE json_extract(item.value, '$.role') = 'target'
                  AND source.evidence_grade = 'official'
                  AND source.url LIKE 'https://%'
            )
            OR NOT EXISTS (
                SELECT 1 FROM json_each(NEW.evidence_bundle_json) item
                JOIN v_evidence_sources_effective source
                  ON source.id = json_extract(item.value, '$.source_id')
                WHERE json_extract(item.value, '$.role') = 'historical'
                  AND source.evidence_grade = 'official'
                  AND source.url LIKE 'https://%'
            )
        )
        THEN RAISE(ABORT, 'comparable requires an active official target and complete official evidence contract')
        WHEN NEW.supersedes_review_id IS NULL AND NEW.review_sequence != 1
        THEN RAISE(ABORT, 'comparability review root must have sequence 1')
        WHEN NEW.supersedes_review_id IS NOT NULL
         AND NOT EXISTS (
            SELECT 1 FROM project_history_comparability_reviews predecessor
            WHERE predecessor.id = NEW.supersedes_review_id
              AND predecessor.candidate_target_version_id = NEW.candidate_target_version_id
              AND predecessor.historical_observation_id = NEW.historical_observation_id
              AND predecessor.review_sequence + 1 = NEW.review_sequence
        )
        THEN RAISE(ABORT, 'comparability successor must stay on the exact target version and history observation')
    END;
END;

CREATE TRIGGER project_history_comparability_reviews_audit_insert
AFTER INSERT ON project_history_comparability_reviews
BEGIN
    INSERT INTO audit_events(
        trace_id, event_type, entity_type, entity_id, payload_json, created_at
    ) VALUES (
        NEW.trace_id,
        'project_history_comparability_review_added',
        'project_history_comparability_review',
        CAST(NEW.id AS TEXT),
        json_object(
            'candidate_target_version_id', NEW.candidate_target_version_id,
            'historical_observation_id', NEW.historical_observation_id,
            'review_contract_version', NEW.review_contract_version,
            'conclusion', NEW.conclusion,
            'dimension_contract_sha256', NEW.dimension_contract_sha256,
            'evidence_bundle_sha256', NEW.evidence_bundle_sha256,
            'review_sequence', NEW.review_sequence,
            'supersedes_review_id', NEW.supersedes_review_id
        ),
        NEW.created_at
    );
END;

CREATE TRIGGER protect_project_history_comparability_reviews_update
BEFORE UPDATE ON project_history_comparability_reviews BEGIN
    SELECT RAISE(ABORT, 'project_history_comparability_reviews are append-only');
END;
CREATE TRIGGER protect_project_history_comparability_reviews_delete
BEFORE DELETE ON project_history_comparability_reviews BEGIN
    SELECT RAISE(ABORT, 'project_history_comparability_reviews are append-only');
END;

CREATE VIEW v_current_project_history_comparability_reviews AS
SELECT review.*
FROM project_history_comparability_reviews review
WHERE NOT EXISTS (
    SELECT 1 FROM project_history_comparability_reviews successor
    WHERE successor.supersedes_review_id = review.id
);

CREATE VIEW v_current_resolved_fact_evidence AS
SELECT
    resolution.resolution_id,
    resolution.observation_id,
    observation.project_id,
    observation.admission_year,
    resolution.fact_key,
    definition.data_type,
    definition.unit,
    resolution.population_scope,
    resolution.statistic_scope,
    resolution.resolution_action,
    resolution.selected_claim_id,
    resolution.reason AS resolution_reason,
    resolution.trace_id AS resolution_trace_id,
    resolution.created_at AS resolution_created_at,
    claim.claim_fingerprint,
    claim.value_integer,
    claim.value_decimal,
    claim.value_text,
    claim.value_boolean,
    claim.evidence_grade AS claim_evidence_grade,
    claim.note AS claim_note,
    claim.trace_id AS claim_trace_id,
    claim.created_at AS claim_created_at,
    claim.derivation_operator,
    claim.derivation_left_fact_key,
    claim.derivation_left_value_integer,
    claim.derivation_right_fact_key,
    claim.derivation_right_value_integer,
    claim.sample_size,
    claim.calculation_method_key,
    claim.calculation_input_sha256,
    source.id AS source_id,
    source.content_sha256 AS source_content_sha256,
    source.document_type AS source_document_type,
    source.url AS source_url,
    source.title AS source_title,
    source.institution AS source_institution,
    source.evidence_grade AS source_evidence_grade,
    source.applicable_year AS source_applicable_year,
    source.effective_published_date AS source_published_date,
    source.retrieved_date AS source_retrieved_date
FROM v_current_fact_resolutions resolution
JOIN fact_definitions definition ON definition.fact_key = resolution.fact_key
JOIN project_year_observations observation
  ON observation.id = resolution.observation_id
LEFT JOIN fact_claims claim ON claim.id = resolution.selected_claim_id
LEFT JOIN v_evidence_sources_effective source ON source.id = claim.source_id;
