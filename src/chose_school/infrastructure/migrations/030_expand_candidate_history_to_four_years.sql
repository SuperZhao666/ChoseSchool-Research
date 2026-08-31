-- Expand the candidate admission-history gate from three to four completed
-- admission years.  For the 2027 target this means 2023-2026.
--
-- The original migration 028 remains immutable.  Recreate only the derived
-- coverage views so all append-only observations, facts and comparability
-- reviews are preserved.

DROP VIEW v_candidate_history_window_coverage;
DROP VIEW v_candidate_history_year_coverage;
CREATE VIEW v_candidate_history_year_coverage AS
WITH
history_offsets(years_ago) AS (VALUES (4), (3), (2), (1)),
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
        WHEN comparable_year_count + limited_year_count = 4
            THEN 'four_year_reviewed'
        WHEN comparable_year_count + limited_year_count = 3
            THEN 'three_year_reviewed'
        WHEN comparable_year_count + limited_year_count = 2
            THEN 'two_year_reviewed'
        WHEN comparable_year_count + limited_year_count = 1
            THEN 'single_year_reviewed'
        ELSE 'none'
    END AS history_coverage_status,
    CASE
        WHEN comparable_ordinary_pressure_year_count = 4
            THEN 'four_year_comparable'
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
        AND required_year_count = 4
        AND ambiguous_year_count = 0
        AND invalid_subject_contract_year_count = 0
        AND comparable_year_count = 4
        AND ordinary_quota_year_count = 4
        AND comparable_ordinary_pressure_year_count = 4
        AND comparable_pressure_family_count = 1
        AND comparable_pressure_population_scope_count = 1
    THEN 1 ELSE 0 END AS score_history_support,
    0 AS history_stability_support,
    'retest_contract_continuity_not_modeled' AS history_stability_boundary,
    0 AS admission_role_is_established,
    'history_support_never_assigns_admission_role' AS role_boundary
FROM window_rollup;
