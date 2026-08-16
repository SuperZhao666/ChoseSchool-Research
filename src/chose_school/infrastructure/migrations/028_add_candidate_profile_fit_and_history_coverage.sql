CREATE TABLE candidate_profile_fit_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL
        REFERENCES applicant_profiles(id) ON DELETE RESTRICT,
    candidate_target_version_id INTEGER NOT NULL
        REFERENCES candidate_target_versions(id) ON DELETE RESTRICT,
    review_contract_version TEXT NOT NULL CHECK (
        review_contract_version = 'candidate-profile-fit-v1'
    ),
    strategy_assignment_basis TEXT NOT NULL CHECK (
        strategy_assignment_basis = 'user_strategy_assignment'
    ),
    strategy_bucket TEXT NOT NULL CHECK (
        strategy_bucket IN (
            '985_priority_research',
            '211_hedge_research',
            'non_211_comparator_research'
        )
    ),
    known_preference_fit TEXT NOT NULL CHECK (
        known_preference_fit IN (
            'compatible', 'conditional', 'conflict', 'insufficient'
        )
    ),
    output_scope TEXT NOT NULL CHECK (output_scope = 'research_only'),
    probability_status TEXT NOT NULL CHECK (
        probability_status = 'not_estimated'
    ),
    input_snapshot_json TEXT NOT NULL CHECK (
        json_valid(input_snapshot_json)
        AND json_type(input_snapshot_json) = 'object'
    ),
    input_snapshot_sha256 TEXT NOT NULL CHECK (
        length(input_snapshot_sha256) = 64
        AND input_snapshot_sha256 = lower(input_snapshot_sha256)
        AND input_snapshot_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    dimension_results_json TEXT NOT NULL CHECK (
        json_valid(dimension_results_json)
        AND json_type(dimension_results_json) = 'object'
    ),
    dimension_results_sha256 TEXT NOT NULL CHECK (
        length(dimension_results_sha256) = 64
        AND dimension_results_sha256 = lower(dimension_results_sha256)
        AND dimension_results_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    evidence_gaps_json TEXT NOT NULL CHECK (
        json_valid(evidence_gaps_json)
        AND json_type(evidence_gaps_json) = 'array'
    ),
    evidence_gaps_sha256 TEXT NOT NULL CHECK (
        length(evidence_gaps_sha256) = 64
        AND evidence_gaps_sha256 = lower(evidence_gaps_sha256)
        AND evidence_gaps_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    review_sequence INTEGER NOT NULL CHECK (review_sequence >= 1),
    supersedes_review_id INTEGER
        REFERENCES candidate_profile_fit_reviews(id) ON DELETE RESTRICT,
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

CREATE UNIQUE INDEX ux_candidate_profile_fit_review_sequence
    ON candidate_profile_fit_reviews(
        candidate_target_version_id, review_sequence
    );
CREATE UNIQUE INDEX ux_candidate_profile_fit_review_root
    ON candidate_profile_fit_reviews(candidate_target_version_id)
    WHERE supersedes_review_id IS NULL;
CREATE UNIQUE INDEX ux_candidate_profile_fit_review_successor
    ON candidate_profile_fit_reviews(supersedes_review_id)
    WHERE supersedes_review_id IS NOT NULL;
CREATE INDEX ix_candidate_profile_fit_profile_bucket
    ON candidate_profile_fit_reviews(
        profile_id, strategy_bucket, known_preference_fit, id
    );
CREATE UNIQUE INDEX ux_audit_candidate_profile_fit_review_event
    ON audit_events(event_type, entity_type, entity_id)
    WHERE event_type = 'candidate_profile_fit_review_added'
      AND entity_type = 'candidate_profile_fit_review';

CREATE TRIGGER candidate_profile_fit_reviews_validate_insert
BEFORE INSERT ON candidate_profile_fit_reviews
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM candidate_target_versions target
            WHERE target.id = NEW.candidate_target_version_id
              AND target.profile_id = NEW.profile_id
        )
        THEN RAISE(ABORT, 'profile fit review must match the exact candidate profile')
        WHEN (SELECT COUNT(*) FROM json_each(NEW.input_snapshot_json)) != 6
          OR json_extract(NEW.input_snapshot_json, '$.schema')
                != 'candidate-profile-input-v1'
          OR json_extract(NEW.input_snapshot_json, '$.profile_id')
                != NEW.profile_id
          OR json_extract(
                NEW.input_snapshot_json, '$.candidate_target_version_id'
             ) != NEW.candidate_target_version_id
          OR json_type(NEW.input_snapshot_json, '$.candidate_key') != 'text'
          OR json_type(
                NEW.input_snapshot_json, '$.preference_event_ids'
             ) != 'array'
          OR json_type(
                NEW.input_snapshot_json, '$.context_event_ids'
             ) != 'array'
          OR NOT EXISTS (
                SELECT 1 FROM candidate_target_versions target
                WHERE target.id = NEW.candidate_target_version_id
                  AND target.candidate_key = json_extract(
                      NEW.input_snapshot_json, '$.candidate_key'
                  )
             )
        THEN RAISE(ABORT, 'profile fit input snapshot contract is invalid')
        WHEN EXISTS (
            SELECT 1
            FROM json_each(
                NEW.input_snapshot_json, '$.preference_event_ids'
            ) item
            WHERE json_type(item.value) != 'integer'
               OR NOT EXISTS (
                   SELECT 1 FROM applicant_preference_events event
                   WHERE event.id = CAST(item.value AS INTEGER)
                     AND event.profile_id = NEW.profile_id
               )
        )
          OR (
              SELECT COUNT(*) FROM json_each(
                  NEW.input_snapshot_json, '$.preference_event_ids'
              )
          ) != (
              SELECT COUNT(DISTINCT CAST(item.value AS INTEGER))
              FROM json_each(
                  NEW.input_snapshot_json, '$.preference_event_ids'
              ) item
          )
          OR EXISTS (
              SELECT 1 FROM v_current_applicant_preferences current
              WHERE current.profile_id = NEW.profile_id
                AND NOT EXISTS (
                    SELECT 1 FROM json_each(
                        NEW.input_snapshot_json, '$.preference_event_ids'
                    ) item
                    WHERE CAST(item.value AS INTEGER) = current.id
                )
          )
          OR EXISTS (
              SELECT 1 FROM json_each(
                  NEW.input_snapshot_json, '$.preference_event_ids'
              ) item
              WHERE NOT EXISTS (
                  SELECT 1 FROM v_current_applicant_preferences current
                  WHERE current.profile_id = NEW.profile_id
                    AND current.id = CAST(item.value AS INTEGER)
              )
          )
        THEN RAISE(ABORT, 'profile fit snapshot must freeze all current preferences')
        WHEN EXISTS (
            SELECT 1
            FROM json_each(
                NEW.input_snapshot_json, '$.context_event_ids'
            ) item
            WHERE json_type(item.value) != 'integer'
               OR NOT EXISTS (
                   SELECT 1 FROM applicant_context_events event
                   WHERE event.id = CAST(item.value AS INTEGER)
                     AND event.profile_id = NEW.profile_id
               )
        )
          OR (
              SELECT COUNT(*) FROM json_each(
                  NEW.input_snapshot_json, '$.context_event_ids'
              )
          ) != (
              SELECT COUNT(DISTINCT CAST(item.value AS INTEGER))
              FROM json_each(
                  NEW.input_snapshot_json, '$.context_event_ids'
              ) item
          )
          OR EXISTS (
              SELECT 1 FROM v_current_applicant_context current
              WHERE current.profile_id = NEW.profile_id
                AND NOT EXISTS (
                    SELECT 1 FROM json_each(
                        NEW.input_snapshot_json, '$.context_event_ids'
                    ) item
                    WHERE CAST(item.value AS INTEGER) = current.id
                )
          )
          OR EXISTS (
              SELECT 1 FROM json_each(
                  NEW.input_snapshot_json, '$.context_event_ids'
              ) item
              WHERE NOT EXISTS (
                  SELECT 1 FROM v_current_applicant_context current
                  WHERE current.profile_id = NEW.profile_id
                    AND current.id = CAST(item.value AS INTEGER)
              )
          )
        THEN RAISE(ABORT, 'profile fit snapshot must freeze all current context events')
        WHEN (SELECT COUNT(*) FROM json_each(NEW.dimension_results_json)) != 2
          OR json_extract(NEW.dimension_results_json, '$.schema')
                != 'candidate-profile-fit-dimensions-v1'
          OR json_type(NEW.dimension_results_json, '$.dimensions') != 'object'
          OR (
              SELECT COUNT(*) FROM json_each(
                  NEW.dimension_results_json, '$.dimensions'
              )
          ) != 10
          OR EXISTS (
              SELECT 1
              FROM json_each(
                  NEW.dimension_results_json, '$.dimensions'
              ) dimension
              WHERE dimension.key NOT IN (
                  'institution', 'program_code', 'region',
                  'training_location', 'tuition', 'joint_training',
                  'retest_format', 'school_tier_strategy',
                  'admission_fairness', 'preparation_timing'
              )
                 OR (
                     SELECT COUNT(*) FROM json_each(dimension.value)
                 ) != 4
                 OR json_extract(dimension.value, '$.status') NOT IN (
                     'pass', 'conditional', 'hard_conflict',
                     'not_evaluable', 'not_applicable'
                 )
                 OR json_type(
                     dimension.value, '$.preference_event_ids'
                 ) != 'array'
                 OR json_type(
                     dimension.value, '$.context_event_ids'
                 ) != 'array'
                 OR json_type(dimension.value, '$.rationale') != 'text'
                 OR length(trim(json_extract(
                     dimension.value, '$.rationale'
                 ))) NOT BETWEEN 1 AND 1000
                 OR (
                     SELECT COUNT(*) FROM json_each(
                         dimension.value, '$.preference_event_ids'
                     )
                 ) != (
                     SELECT COUNT(DISTINCT CAST(reference.value AS INTEGER))
                     FROM json_each(
                         dimension.value, '$.preference_event_ids'
                     ) reference
                 )
                 OR (
                     SELECT COUNT(*) FROM json_each(
                         dimension.value, '$.context_event_ids'
                     )
                 ) != (
                     SELECT COUNT(DISTINCT CAST(reference.value AS INTEGER))
                     FROM json_each(
                         dimension.value, '$.context_event_ids'
                     ) reference
                 )
                 OR (
                     json_extract(dimension.value, '$.status') IN (
                         'pass', 'conditional', 'hard_conflict'
                     )
                     AND json_array_length(json_extract(
                         dimension.value, '$.preference_event_ids'
                     )) + json_array_length(json_extract(
                         dimension.value, '$.context_event_ids'
                     )) = 0
                 )
          )
        THEN RAISE(ABORT, 'profile fit dimension contract is incomplete')
        WHEN EXISTS (
            SELECT 1
            FROM json_each(
                NEW.dimension_results_json, '$.dimensions'
            ) dimension,
            json_each(dimension.value, '$.preference_event_ids') reference
            WHERE json_type(reference.value) != 'integer'
               OR NOT EXISTS (
                   SELECT 1 FROM json_each(
                       NEW.input_snapshot_json, '$.preference_event_ids'
                   ) input
                   WHERE CAST(input.value AS INTEGER) =
                         CAST(reference.value AS INTEGER)
               )
        )
          OR EXISTS (
            SELECT 1
            FROM json_each(
                NEW.dimension_results_json, '$.dimensions'
            ) dimension,
            json_each(dimension.value, '$.context_event_ids') reference
            WHERE json_type(reference.value) != 'integer'
               OR NOT EXISTS (
                   SELECT 1 FROM json_each(
                       NEW.input_snapshot_json, '$.context_event_ids'
                   ) input
                   WHERE CAST(input.value AS INTEGER) =
                         CAST(reference.value AS INTEGER)
               )
        )
        THEN RAISE(ABORT, 'profile fit dimensions reference events outside the snapshot')
        WHEN EXISTS (
            SELECT 1 FROM json_each(NEW.evidence_gaps_json) gap
            WHERE json_type(gap.value) != 'object'
               OR (SELECT COUNT(*) FROM json_each(gap.value)) != 4
               OR json_type(gap.value, '$.code') != 'text'
               OR length(trim(json_extract(gap.value, '$.code'))) NOT BETWEEN 1 AND 80
               OR json_extract(gap.value, '$.status') NOT IN (
                   'missing', 'partial', 'resolved', 'not_applicable'
               )
               OR json_extract(gap.value, '$.impact') NOT IN (
                   'selection_gate', 'research_condition', 'advisory'
               )
               OR json_type(gap.value, '$.rationale') != 'text'
               OR length(trim(json_extract(
                   gap.value, '$.rationale'
               ))) NOT BETWEEN 1 AND 1000
        )
          OR json_array_length(NEW.evidence_gaps_json) != (
              SELECT COUNT(DISTINCT json_extract(gap.value, '$.code'))
              FROM json_each(NEW.evidence_gaps_json) gap
          )
        THEN RAISE(ABORT, 'profile fit evidence gap contract is invalid')
        WHEN NEW.known_preference_fit = 'conflict'
         AND NOT EXISTS (
             SELECT 1 FROM json_each(
                 NEW.dimension_results_json, '$.dimensions'
             ) dimension
             WHERE json_extract(dimension.value, '$.status') = 'hard_conflict'
         )
        THEN RAISE(ABORT, 'conflict conclusion requires a hard preference conflict')
        WHEN NEW.known_preference_fit != 'conflict'
         AND EXISTS (
             SELECT 1 FROM json_each(
                 NEW.dimension_results_json, '$.dimensions'
             ) dimension
             WHERE json_extract(dimension.value, '$.status') = 'hard_conflict'
         )
        THEN RAISE(ABORT, 'hard preference conflict requires conflict conclusion')
        WHEN NEW.known_preference_fit = 'compatible'
         AND (
             EXISTS (
                 SELECT 1 FROM json_each(
                     NEW.dimension_results_json, '$.dimensions'
                 ) dimension
                 WHERE json_extract(dimension.value, '$.status') NOT IN (
                     'pass', 'not_applicable'
                 )
             )
             OR EXISTS (
                 SELECT 1 FROM json_each(NEW.evidence_gaps_json) gap
                 WHERE json_extract(gap.value, '$.impact') = 'selection_gate'
                   AND json_extract(gap.value, '$.status') IN ('missing', 'partial')
             )
         )
        THEN RAISE(ABORT, 'compatible conclusion requires no unresolved hard dimension')
        WHEN NEW.known_preference_fit = 'conditional'
         AND NOT EXISTS (
             SELECT 1 FROM json_each(
                 NEW.dimension_results_json, '$.dimensions'
             ) dimension
             WHERE json_extract(dimension.value, '$.status') IN (
                 'conditional', 'not_evaluable'
             )
             UNION ALL
             SELECT 1 FROM json_each(NEW.evidence_gaps_json) gap
             WHERE json_extract(gap.value, '$.status') IN ('missing', 'partial')
         )
        THEN RAISE(ABORT, 'conditional conclusion requires an explicit unresolved condition')
        WHEN NEW.known_preference_fit = 'insufficient'
         AND NOT EXISTS (
             SELECT 1 FROM json_each(
                 NEW.dimension_results_json, '$.dimensions'
             ) dimension
             WHERE json_extract(dimension.value, '$.status') = 'not_evaluable'
         )
        THEN RAISE(ABORT, 'insufficient conclusion requires a non-evaluable dimension')
        WHEN NEW.supersedes_review_id IS NULL AND NEW.review_sequence != 1
        THEN RAISE(ABORT, 'profile fit review root must have sequence 1')
        WHEN NEW.supersedes_review_id IS NOT NULL
         AND NOT EXISTS (
             SELECT 1 FROM candidate_profile_fit_reviews predecessor
             WHERE predecessor.id = NEW.supersedes_review_id
               AND predecessor.profile_id = NEW.profile_id
               AND predecessor.candidate_target_version_id =
                   NEW.candidate_target_version_id
               AND predecessor.review_sequence + 1 = NEW.review_sequence
         )
        THEN RAISE(ABORT, 'profile fit successor must remain on the exact candidate version')
    END;
END;

CREATE TRIGGER candidate_profile_fit_reviews_audit_insert
AFTER INSERT ON candidate_profile_fit_reviews
BEGIN
    INSERT INTO audit_events(
        trace_id, event_type, entity_type, entity_id, payload_json, created_at
    ) VALUES (
        NEW.trace_id,
        'candidate_profile_fit_review_added',
        'candidate_profile_fit_review',
        CAST(NEW.id AS TEXT),
        json_object(
            'profile_id', NEW.profile_id,
            'candidate_target_version_id', NEW.candidate_target_version_id,
            'review_contract_version', NEW.review_contract_version,
            'strategy_assignment_basis', NEW.strategy_assignment_basis,
            'strategy_bucket', NEW.strategy_bucket,
            'known_preference_fit', NEW.known_preference_fit,
            'input_snapshot_sha256', NEW.input_snapshot_sha256,
            'dimension_results_sha256', NEW.dimension_results_sha256,
            'evidence_gaps_sha256', NEW.evidence_gaps_sha256,
            'review_sequence', NEW.review_sequence,
            'supersedes_review_id', NEW.supersedes_review_id,
            'output_scope', NEW.output_scope,
            'probability_status', NEW.probability_status
        ),
        NEW.created_at
    );
END;

CREATE TRIGGER protect_candidate_profile_fit_reviews_update
BEFORE UPDATE ON candidate_profile_fit_reviews BEGIN
    SELECT RAISE(ABORT, 'candidate_profile_fit_reviews are append-only');
END;
CREATE TRIGGER protect_candidate_profile_fit_reviews_delete
BEFORE DELETE ON candidate_profile_fit_reviews BEGIN
    SELECT RAISE(ABORT, 'candidate_profile_fit_reviews are append-only');
END;

CREATE VIEW v_current_candidate_profile_fit_reviews AS
SELECT review.*
FROM candidate_profile_fit_reviews review
WHERE NOT EXISTS (
    SELECT 1 FROM candidate_profile_fit_reviews successor
    WHERE successor.supersedes_review_id = review.id
);

CREATE VIEW v_active_candidate_profile_fit_reviews AS
SELECT
    review.*,
    target.candidate_key,
    target.target_year,
    target.school_key,
    target.college_key,
    target.program_code,
    target.program_name,
    target.target_basis,
    CASE WHEN
        json_array_length(json_extract(
            review.input_snapshot_json, '$.preference_event_ids'
        )) = (
            SELECT COUNT(*) FROM v_current_applicant_preferences current
            WHERE current.profile_id = review.profile_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM v_current_applicant_preferences current
            WHERE current.profile_id = review.profile_id
              AND NOT EXISTS (
                  SELECT 1 FROM json_each(
                      review.input_snapshot_json, '$.preference_event_ids'
                  ) item
                  WHERE CAST(item.value AS INTEGER) = current.id
              )
        )
        AND json_array_length(json_extract(
            review.input_snapshot_json, '$.context_event_ids'
        )) = (
            SELECT COUNT(*) FROM v_current_applicant_context current
            WHERE current.profile_id = review.profile_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM v_current_applicant_context current
            WHERE current.profile_id = review.profile_id
              AND NOT EXISTS (
                  SELECT 1 FROM json_each(
                      review.input_snapshot_json, '$.context_event_ids'
                  ) item
                  WHERE CAST(item.value AS INTEGER) = current.id
              )
        )
    THEN 1 ELSE 0 END AS is_input_snapshot_current
FROM v_current_candidate_profile_fit_reviews review
JOIN v_active_candidate_targets target
  ON target.id = review.candidate_target_version_id
 AND target.profile_id = review.profile_id;

-- This view is deliberately anchored only on explicit migration-027
-- comparability reviews.  Similar-looking school/program text never binds a
-- historical observation automatically.
CREATE VIEW v_candidate_history_year_coverage AS
WITH
history_offsets(years_ago) AS (VALUES (3), (2), (1)),
candidate_years AS (
    SELECT
        target.id AS candidate_target_version_id,
        target.profile_id,
        target.candidate_key,
        target.target_year,
        target.target_basis,
        target.target_observation_id,
        target.school_key,
        target.college_key,
        target.program_code,
        target.program_name,
        target.target_year - history_offsets.years_ago AS historical_year
    FROM v_active_candidate_targets target
    CROSS JOIN history_offsets
),
review_rollup AS (
    SELECT
        review.candidate_target_version_id,
        observation.admission_year AS historical_year,
        COUNT(*) AS review_count,
        SUM(CASE WHEN review.conclusion = 'comparable' THEN 1 ELSE 0 END)
            AS comparable_review_count,
        SUM(CASE WHEN review.conclusion = 'limited' THEN 1 ELSE 0 END)
            AS limited_review_count,
        SUM(CASE WHEN review.conclusion = 'rejected' THEN 1 ELSE 0 END)
            AS rejected_review_count,
        SUM(CASE WHEN review.conclusion = 'insufficient' THEN 1 ELSE 0 END)
            AS insufficient_review_count,
        SUM(CASE WHEN review.conclusion IN ('comparable', 'limited')
                 THEN 1 ELSE 0 END) AS potentially_usable_review_count,
        MAX(CASE WHEN review.conclusion IN ('comparable', 'limited')
                 THEN review.id END) AS potentially_usable_review_id
    FROM v_current_project_history_comparability_reviews review
    JOIN project_year_observations observation
      ON observation.id = review.historical_observation_id
    GROUP BY review.candidate_target_version_id, observation.admission_year
),
bound_review AS (
    SELECT
        rollup.candidate_target_version_id,
        rollup.historical_year,
        review.id AS review_id,
        review.historical_observation_id,
        review.conclusion,
        review.dimension_contract_json,
        json_extract(
            review.dimension_contract_json, '$.population_scope'
        ) AS population_scope,
        json_extract(
            review.dimension_contract_json, '$.statistic_scope'
        ) AS statistic_scope
    FROM review_rollup rollup
    JOIN v_current_project_history_comparability_reviews review
      ON review.id = rollup.potentially_usable_review_id
    WHERE rollup.potentially_usable_review_count = 1
),
pressure_groups AS (
    SELECT
        statistic.observation_id,
        statistic.statistic_family,
        statistic.count_fact_key,
        statistic.population_scope,
        statistic.statistic_scope,
        statistic.sample_size,
        statistic.calculation_input_sha256,
        COUNT(DISTINCT statistic.statistic_name) AS statistic_count,
        MAX(CASE WHEN statistic.statistic_name = 'q25' THEN 1 ELSE 0 END)
            AS has_q25,
        MAX(CASE WHEN statistic.statistic_name = 'q50' THEN 1 ELSE 0 END)
            AS has_q50,
        MAX(CASE WHEN statistic.statistic_name = 'q75' THEN 1 ELSE 0 END)
            AS has_q75,
        MAX(CASE WHEN statistic.statistic_name = 'min' THEN 1 ELSE 0 END)
            AS has_min,
        MAX(CASE WHEN statistic.statistic_name = 'mean' THEN 1 ELSE 0 END)
            AS has_mean,
        MAX(CASE WHEN statistic.statistic_name = 'max' THEN 1 ELSE 0 END)
            AS has_max
    FROM v_current_structured_score_statistics statistic
    GROUP BY
        statistic.observation_id,
        statistic.statistic_family,
        statistic.count_fact_key,
        statistic.population_scope,
        statistic.statistic_scope,
        statistic.sample_size,
        statistic.calculation_input_sha256
),
complete_pressure_groups AS (
    SELECT pressure.*
    FROM pressure_groups pressure
    WHERE (
        (
            pressure.statistic_family IN (
                'ordinary_general_admission_initial',
                'final_list_fulltime_blank_remark_initial',
                'final_list_first_choice_fulltime_non_directed_initial'
            )
            AND pressure.has_q25 = 1
            AND pressure.has_q50 = 1
            AND pressure.has_q75 = 1
        ) OR (
            pressure.statistic_family = 'retest_roster_initial'
            AND pressure.has_min = 1
            AND pressure.has_q50 = 1
            AND pressure.has_mean = 1
            AND pressure.has_max = 1
        )
    )
      AND NOT EXISTS (
          SELECT 1 FROM v_statistical_fact_quality_issues issue
          WHERE issue.observation_id = pressure.observation_id
            AND issue.statistic_family = pressure.statistic_family
            AND issue.population_scope = pressure.population_scope
            AND issue.statistic_scope = pressure.statistic_scope
      )
),
review_pressure_groups AS (
    SELECT
        bound.review_id,
        pressure.*
    FROM bound_review bound
    JOIN complete_pressure_groups pressure
     ON pressure.observation_id = bound.historical_observation_id
     AND pressure.population_scope = bound.population_scope
     AND pressure.statistic_scope = bound.statistic_scope
    WHERE EXISTS (
        SELECT 1
        FROM json_each(
            bound.dimension_contract_json, '$.fact_keys'
        ) declared
        WHERE CAST(declared.value AS TEXT) = pressure.count_fact_key
    )
      AND NOT EXISTS (
        SELECT 1
        FROM v_current_structured_score_statistics statistic
        WHERE statistic.observation_id = pressure.observation_id
          AND statistic.statistic_family = pressure.statistic_family
          AND statistic.population_scope = pressure.population_scope
          AND statistic.statistic_scope = pressure.statistic_scope
          AND statistic.sample_size = pressure.sample_size
          AND statistic.calculation_input_sha256 =
              pressure.calculation_input_sha256
          AND (
              (
                  pressure.statistic_family IN (
                      'ordinary_general_admission_initial',
                      'final_list_fulltime_blank_remark_initial',
                      'final_list_first_choice_fulltime_non_directed_initial'
                  )
                  AND statistic.statistic_name IN ('q25', 'q50', 'q75')
              ) OR (
                  pressure.statistic_family = 'retest_roster_initial'
                  AND statistic.statistic_name IN (
                      'min', 'q50', 'mean', 'max'
                  )
              )
          )
          AND NOT EXISTS (
              SELECT 1
              FROM json_each(
                  bound.dimension_contract_json, '$.fact_keys'
              ) declared
              WHERE CAST(declared.value AS TEXT) = statistic.fact_key
          )
    )
),
year_metrics AS (
    SELECT
        candidate_years.*,
        COALESCE(rollup.review_count, 0) AS review_count,
        COALESCE(rollup.comparable_review_count, 0)
            AS comparable_review_count,
        COALESCE(rollup.limited_review_count, 0) AS limited_review_count,
        COALESCE(rollup.rejected_review_count, 0) AS rejected_review_count,
        COALESCE(rollup.insufficient_review_count, 0)
            AS insufficient_review_count,
        COALESCE(rollup.potentially_usable_review_count, 0)
            AS potentially_usable_review_count,
        bound.review_id AS bound_comparability_review_id,
        bound.historical_observation_id AS bound_historical_observation_id,
        bound.conclusion AS bound_conclusion,
        bound.population_scope AS bound_population_scope,
        bound.statistic_scope AS bound_statistic_scope,
        (
            SELECT catalog.strict_22408_status
            FROM v_catalog catalog
            WHERE catalog.observation_id = candidate_years.target_observation_id
              AND catalog.admission_year = candidate_years.target_year
        ) AS target_strict_22408_status,
        (
            SELECT catalog.strict_22408_status
            FROM v_catalog catalog
            WHERE catalog.observation_id = bound.historical_observation_id
              AND catalog.admission_year = candidate_years.historical_year
        ) AS historical_strict_22408_status,
        CASE WHEN
            candidate_years.target_basis = 'official_observation'
            AND (
                SELECT catalog.strict_22408_status
                FROM v_catalog catalog
                WHERE catalog.observation_id =
                    candidate_years.target_observation_id
                  AND catalog.admission_year = candidate_years.target_year
            ) = 'official_confirmed'
            AND (
                SELECT catalog.strict_22408_status
                FROM v_catalog catalog
                WHERE catalog.observation_id =
                    bound.historical_observation_id
                  AND catalog.admission_year = candidate_years.historical_year
            ) = 'official_confirmed'
        THEN 1 ELSE 0 END AS subject_contract_valid,
        COALESCE((
            SELECT COUNT(*)
            FROM json_each(
                bound.dimension_contract_json, '$.fact_keys'
            ) fact_key
            WHERE CAST(fact_key.value AS TEXT) LIKE 'score.%'
        ), 0) AS declared_score_fact_count,
        COALESCE((
            SELECT COUNT(*)
            FROM v_current_resolved_fact_evidence fact
            WHERE fact.observation_id = bound.historical_observation_id
              AND fact.resolution_action = 'accept'
        ), 0) AS accepted_fact_count,
        COALESCE((
            SELECT COUNT(*)
            FROM v_current_resolved_fact_evidence fact
            WHERE fact.observation_id = bound.historical_observation_id
              AND fact.resolution_action = 'accept'
               AND fact.fact_key = 'quota.general_effective'
               AND fact.population_scope = bound.population_scope
               AND fact.statistic_scope = bound.statistic_scope
               AND EXISTS (
                   SELECT 1 FROM json_each(
                       bound.dimension_contract_json, '$.fact_keys'
                   ) declared
                   WHERE CAST(declared.value AS TEXT) =
                       'quota.general_effective'
               )
        ), 0) AS accepted_ordinary_quota_fact_count,
        COALESCE((
            SELECT COUNT(*)
            FROM v_current_structured_score_statistics statistic
            WHERE statistic.observation_id = bound.historical_observation_id
               AND statistic.population_scope = bound.population_scope
               AND statistic.statistic_scope = bound.statistic_scope
        ), 0) AS structured_statistic_count,
        COALESCE((
            SELECT COUNT(*)
            FROM complete_pressure_groups pressure
            WHERE pressure.observation_id = bound.historical_observation_id
              AND pressure.population_scope = bound.population_scope
              AND pressure.statistic_scope = bound.statistic_scope
        ), 0) AS available_complete_pressure_group_count,
        COALESCE((
            SELECT COUNT(*)
            FROM review_pressure_groups pressure
            WHERE pressure.review_id = bound.review_id
        ), 0) AS complete_pressure_group_count,
        (
            SELECT MAX(pressure.statistic_family)
            FROM review_pressure_groups pressure
            WHERE pressure.review_id = bound.review_id
        ) AS pressure_statistic_family,
        (
            SELECT MAX(pressure.sample_size)
            FROM review_pressure_groups pressure
            WHERE pressure.review_id = bound.review_id
        ) AS pressure_sample_size,
        (
            SELECT MAX(pressure.calculation_input_sha256)
            FROM review_pressure_groups pressure
            WHERE pressure.review_id = bound.review_id
        ) AS pressure_input_sha256
    FROM candidate_years
    LEFT JOIN review_rollup rollup
      ON rollup.candidate_target_version_id =
            candidate_years.candidate_target_version_id
     AND rollup.historical_year = candidate_years.historical_year
    LEFT JOIN bound_review bound
      ON bound.candidate_target_version_id =
            candidate_years.candidate_target_version_id
     AND bound.historical_year = candidate_years.historical_year
)
SELECT
    year_metrics.*,
    CASE
        WHEN review_count = 0 THEN 'unreviewed'
        WHEN potentially_usable_review_count > 1 THEN 'ambiguous'
        WHEN comparable_review_count = 1 AND subject_contract_valid = 0
            THEN 'invalid_subject_contract'
        WHEN comparable_review_count = 1 AND limited_review_count = 0
            THEN 'comparable'
        WHEN comparable_review_count = 0 AND limited_review_count = 1
            THEN 'limited'
        WHEN comparable_review_count = 0 AND limited_review_count = 0
             AND insufficient_review_count > 0 THEN 'insufficient'
        ELSE 'rejected'
    END AS history_year_status,
    CASE
        WHEN bound_conclusion = 'comparable' AND subject_contract_valid = 0
            THEN 'invalid_subject_contract'
        WHEN available_complete_pressure_group_count = 0 THEN 'missing'
        WHEN declared_score_fact_count = 0 THEN 'not_declared_by_review'
        WHEN complete_pressure_group_count = 0
            THEN 'not_fully_declared_by_review'
        WHEN complete_pressure_group_count > 1 THEN 'ambiguous'
        WHEN bound_conclusion = 'comparable' THEN 'comparable_complete'
        WHEN bound_conclusion = 'limited' THEN 'limited_context_only'
        ELSE 'not_usable'
    END AS pressure_evidence_status,
    CASE
        WHEN pressure_statistic_family = 'ordinary_general_admission_initial'
            THEN 'ordinary_general_admission'
        WHEN pressure_statistic_family IN (
            'final_list_fulltime_blank_remark_initial',
            'final_list_first_choice_fulltime_non_directed_initial'
        ) THEN 'proxy_population'
        WHEN pressure_statistic_family = 'retest_roster_initial'
            THEN 'retest_roster'
        ELSE 'none'
    END AS pressure_population_class
FROM year_metrics;

CREATE VIEW v_candidate_history_window_coverage AS
WITH window_rollup AS (
    SELECT
        candidate_target_version_id,
        profile_id,
        candidate_key,
        target_year,
        target_basis,
        school_key,
        college_key,
        program_code,
        program_name,
        MIN(historical_year) AS window_start_year,
        MAX(historical_year) AS window_end_year,
        COUNT(*) AS required_year_count,
        SUM(CASE WHEN history_year_status != 'unreviewed' THEN 1 ELSE 0 END)
            AS reviewed_year_count,
        SUM(CASE WHEN history_year_status = 'comparable' THEN 1 ELSE 0 END)
            AS comparable_year_count,
        SUM(CASE WHEN history_year_status = 'limited' THEN 1 ELSE 0 END)
            AS limited_year_count,
        SUM(CASE WHEN history_year_status = 'ambiguous' THEN 1 ELSE 0 END)
            AS ambiguous_year_count,
        SUM(CASE WHEN history_year_status = 'invalid_subject_contract'
                 THEN 1 ELSE 0 END) AS invalid_subject_contract_year_count,
        SUM(CASE WHEN accepted_ordinary_quota_fact_count = 1
                 THEN 1 ELSE 0 END) AS ordinary_quota_year_count,
        SUM(CASE WHEN complete_pressure_group_count = 1
                      AND declared_score_fact_count > 0
                 THEN 1 ELSE 0 END)
            AS reproducible_pressure_context_year_count,
        SUM(CASE WHEN pressure_evidence_status = 'comparable_complete'
                      AND pressure_population_class =
                          'ordinary_general_admission'
                 THEN 1 ELSE 0 END)
            AS comparable_ordinary_pressure_year_count,
        COUNT(DISTINCT CASE
            WHEN pressure_evidence_status = 'comparable_complete'
            THEN pressure_statistic_family END
        ) AS comparable_pressure_family_count,
        COUNT(DISTINCT CASE
            WHEN pressure_evidence_status = 'comparable_complete'
            THEN bound_population_scope END
        ) AS comparable_pressure_population_scope_count
    FROM v_candidate_history_year_coverage
    GROUP BY
        candidate_target_version_id,
        profile_id,
        candidate_key,
        target_year,
        target_basis,
        school_key,
        college_key,
        program_code,
        program_name
)
SELECT
    window_rollup.*,
    CASE
        WHEN ambiguous_year_count > 0 THEN 'ambiguous'
        WHEN invalid_subject_contract_year_count > 0
            THEN 'invalid_subject_contract'
        WHEN comparable_year_count + limited_year_count = 3
            THEN 'three_year_reviewed'
        WHEN comparable_year_count + limited_year_count = 2
            THEN 'two_year_reviewed'
        WHEN comparable_year_count + limited_year_count = 1
            THEN 'single_year_reviewed'
        ELSE 'none'
    END AS history_coverage_status,
    CASE
        WHEN comparable_ordinary_pressure_year_count = 3
            THEN 'three_year_comparable'
        WHEN reproducible_pressure_context_year_count >= 2
            THEN 'multi_year_context_only'
        WHEN reproducible_pressure_context_year_count = 1
            THEN 'single_year_only'
        ELSE 'none'
    END AS pressure_coverage_status,
    CASE WHEN
        target_basis = 'official_observation'
        AND required_year_count = 3
        AND ambiguous_year_count = 0
        AND invalid_subject_contract_year_count = 0
        AND comparable_year_count = 3
        AND ordinary_quota_year_count = 3
        AND comparable_ordinary_pressure_year_count = 3
        AND comparable_pressure_family_count = 1
        AND comparable_pressure_population_scope_count = 1
    THEN 1 ELSE 0 END AS score_history_support,
    0 AS history_stability_support,
    'retest_contract_continuity_not_modeled' AS history_stability_boundary,
    0 AS admission_role_is_established,
    'history_support_never_assigns_admission_role' AS role_boundary
FROM window_rollup;
