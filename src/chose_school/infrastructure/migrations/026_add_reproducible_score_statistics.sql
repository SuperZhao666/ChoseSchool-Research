ALTER TABLE fact_claims
ADD COLUMN sample_size INTEGER;

ALTER TABLE fact_claims
ADD COLUMN calculation_method_key TEXT;

ALTER TABLE fact_claims
ADD COLUMN calculation_input_sha256 TEXT;

INSERT INTO fact_definitions(
    fact_key,
    data_type,
    unit,
    description,
    preferred_source_type
) VALUES
    (
        'score.initial.q25',
        'decimal',
        '分',
        '普通统考拟录取者初试总分的 25% 分位数；按 percentile_inc_type7_v1 计算',
        '最终拟录取名单逐人复算'
    ),
    (
        'score.initial.q75',
        'decimal',
        '分',
        '普通统考拟录取者初试总分的 75% 分位数；按 percentile_inc_type7_v1 计算',
        '最终拟录取名单逐人复算'
    ),
    (
        'score.final_list_fulltime_blank_remark_initial.q25',
        'decimal',
        '分',
        '最终名单中目标项目、全日制且备注空白行初试总分的 25% 分位数；不自动等于普通统考',
        '最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_fulltime_blank_remark_initial.q75',
        'decimal',
        '分',
        '最终名单中目标项目、全日制且备注空白行初试总分的 75% 分位数；不自动等于普通统考',
        '最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_first_choice_fulltime_non_directed_initial.q25',
        'decimal',
        '分',
        '一志愿、全日制、非定向最终名单限定行初试总分的 25% 分位数；专项未拆时不得转存为普通统考',
        '一志愿最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_first_choice_fulltime_non_directed_initial.q75',
        'decimal',
        '分',
        '一志愿、全日制、非定向最终名单限定行初试总分的 75% 分位数；专项未拆时不得转存为普通统考',
        '一志愿最终拟录取名单逐行复算'
    );

-- 迁移前的统计主张保持三列 NULL，不回填、不改写。
-- 从本迁移起新增的成绩分布主张必须冻结样本数、算法版本和匿名输入集哈希。
CREATE TRIGGER validate_score_statistical_metadata_insert
BEFORE INSERT ON fact_claims
WHEN (
    SELECT fact_key
    FROM fact_definitions
    WHERE id = NEW.fact_definition_id
) IN (
    'score.initial.min',
    'score.initial.q25',
    'score.initial.median',
    'score.initial.mean',
    'score.initial.q75',
    'score.final_list_fulltime_blank_remark_initial.min',
    'score.final_list_fulltime_blank_remark_initial.q25',
    'score.final_list_fulltime_blank_remark_initial.median',
    'score.final_list_fulltime_blank_remark_initial.mean',
    'score.final_list_fulltime_blank_remark_initial.q75',
    'score.final_list_first_choice_fulltime_non_directed_initial.min',
    'score.final_list_first_choice_fulltime_non_directed_initial.q25',
    'score.final_list_first_choice_fulltime_non_directed_initial.median',
    'score.final_list_first_choice_fulltime_non_directed_initial.mean',
    'score.final_list_first_choice_fulltime_non_directed_initial.q75',
    'score.retest_roster_initial.min',
    'score.retest_roster_initial.median',
    'score.retest_roster_initial.mean',
    'score.retest_roster_initial.max'
)
AND NOT COALESCE(
    (
        typeof(NEW.sample_size) = 'integer'
        AND NEW.sample_size > 0
        AND NEW.calculation_method_key = CASE
            WHEN (
                SELECT fact_key
                FROM fact_definitions
                WHERE id = NEW.fact_definition_id
            ) LIKE '%.min' THEN 'sample_min_v1'
            WHEN (
                SELECT fact_key
                FROM fact_definitions
                WHERE id = NEW.fact_definition_id
            ) LIKE '%.mean' THEN 'arithmetic_mean_v1'
            WHEN (
                SELECT fact_key
                FROM fact_definitions
                WHERE id = NEW.fact_definition_id
            ) LIKE '%.max' THEN 'sample_max_v1'
            ELSE 'percentile_inc_type7_v1'
        END
        AND length(NEW.calculation_input_sha256) = 64
        AND NEW.calculation_input_sha256 = lower(NEW.calculation_input_sha256)
        AND NEW.calculation_input_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    0
)
BEGIN
    SELECT RAISE(ABORT, 'invalid score statistical calculation metadata');
END;

CREATE TRIGGER forbid_statistical_metadata_on_non_score_fact_insert
BEFORE INSERT ON fact_claims
WHEN COALESCE(
    (
        SELECT fact_key
        FROM fact_definitions
        WHERE id = NEW.fact_definition_id
    ),
    ''
) NOT IN (
    'score.initial.min',
    'score.initial.q25',
    'score.initial.median',
    'score.initial.mean',
    'score.initial.q75',
    'score.final_list_fulltime_blank_remark_initial.min',
    'score.final_list_fulltime_blank_remark_initial.q25',
    'score.final_list_fulltime_blank_remark_initial.median',
    'score.final_list_fulltime_blank_remark_initial.mean',
    'score.final_list_fulltime_blank_remark_initial.q75',
    'score.final_list_first_choice_fulltime_non_directed_initial.min',
    'score.final_list_first_choice_fulltime_non_directed_initial.q25',
    'score.final_list_first_choice_fulltime_non_directed_initial.median',
    'score.final_list_first_choice_fulltime_non_directed_initial.mean',
    'score.final_list_first_choice_fulltime_non_directed_initial.q75',
    'score.retest_roster_initial.min',
    'score.retest_roster_initial.median',
    'score.retest_roster_initial.mean',
    'score.retest_roster_initial.max'
)
AND (
    NEW.sample_size IS NOT NULL
    OR NEW.calculation_method_key IS NOT NULL
    OR NEW.calculation_input_sha256 IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'statistical metadata is forbidden for this fact key');
END;

CREATE INDEX ix_fact_claim_statistical_input
    ON fact_claims(calculation_input_sha256, sample_size)
    WHERE calculation_input_sha256 IS NOT NULL;

DROP VIEW v_fact_claims;

CREATE VIEW v_fact_claims AS
SELECT
    fc.id AS claim_id,
    fc.observation_id,
    fd.fact_key,
    fd.data_type,
    fd.unit,
    fc.population_scope,
    fc.statistic_scope,
    fc.value_integer,
    fc.value_decimal,
    fc.value_text,
    fc.value_boolean,
    fc.derivation_operator,
    fc.derivation_left_fact_key,
    fc.derivation_left_value_integer,
    fc.derivation_right_fact_key,
    fc.derivation_right_value_integer,
    fc.sample_size,
    fc.calculation_method_key,
    fc.calculation_input_sha256,
    fc.evidence_grade,
    es.title AS source_title,
    es.institution AS source_institution,
    es.url AS source_url,
    fc.note,
    fc.trace_id,
    fc.created_at
FROM fact_claims fc
JOIN fact_definitions fd ON fd.id = fc.fact_definition_id
JOIN evidence_sources es ON es.id = fc.source_id;

CREATE VIEW v_current_structured_score_statistics AS
SELECT
    cr.resolution_id,
    fc.id AS claim_id,
    fc.observation_id,
    fd.fact_key,
    CASE
        WHEN fd.fact_key LIKE 'score.initial.%'
            THEN 'ordinary_general_admission_initial'
        WHEN fd.fact_key LIKE 'score.final_list_fulltime_blank_remark_initial.%'
            THEN 'final_list_fulltime_blank_remark_initial'
        WHEN fd.fact_key LIKE 'score.final_list_first_choice_fulltime_non_directed_initial.%'
            THEN 'final_list_first_choice_fulltime_non_directed_initial'
        ELSE 'retest_roster_initial'
    END AS statistic_family,
    CASE
        WHEN fd.fact_key LIKE 'score.initial.%'
            THEN 'admission.general_count'
        WHEN fd.fact_key LIKE 'score.final_list_fulltime_blank_remark_initial.%'
            THEN 'admission.final_list_fulltime_blank_remark_count'
        WHEN fd.fact_key LIKE 'score.final_list_first_choice_fulltime_non_directed_initial.%'
            THEN 'admission.final_list_first_choice_fulltime_non_directed_count'
        ELSE 'retest.roster_count'
    END AS count_fact_key,
    CASE
        WHEN fd.fact_key LIKE '%.q25' THEN 'q25'
        WHEN fd.fact_key LIKE '%.median' THEN 'q50'
        WHEN fd.fact_key LIKE '%.q75' THEN 'q75'
        WHEN fd.fact_key LIKE '%.min' THEN 'min'
        WHEN fd.fact_key LIKE '%.mean' THEN 'mean'
        ELSE 'max'
    END AS statistic_name,
    fc.population_scope,
    fc.statistic_scope,
    fc.value_decimal,
    fc.sample_size,
    fc.calculation_method_key,
    fc.calculation_input_sha256
FROM v_current_fact_resolutions cr
JOIN fact_claims fc ON fc.id = cr.selected_claim_id
JOIN fact_definitions fd ON fd.id = fc.fact_definition_id
WHERE cr.resolution_action = 'accept'
  AND fd.fact_key IN (
      'score.initial.min',
      'score.initial.q25',
      'score.initial.median',
      'score.initial.mean',
      'score.initial.q75',
      'score.final_list_fulltime_blank_remark_initial.min',
      'score.final_list_fulltime_blank_remark_initial.q25',
      'score.final_list_fulltime_blank_remark_initial.median',
      'score.final_list_fulltime_blank_remark_initial.mean',
      'score.final_list_fulltime_blank_remark_initial.q75',
      'score.final_list_first_choice_fulltime_non_directed_initial.min',
      'score.final_list_first_choice_fulltime_non_directed_initial.q25',
      'score.final_list_first_choice_fulltime_non_directed_initial.median',
      'score.final_list_first_choice_fulltime_non_directed_initial.mean',
      'score.final_list_first_choice_fulltime_non_directed_initial.q75',
      'score.retest_roster_initial.min',
      'score.retest_roster_initial.median',
      'score.retest_roster_initial.mean',
      'score.retest_roster_initial.max'
  )
  AND (
      fc.sample_size IS NOT NULL
      OR fc.calculation_method_key IS NOT NULL
      OR fc.calculation_input_sha256 IS NOT NULL
  );

-- 跨行约束不放入 INSERT 触发器：多条主张逐次追加时尚未形成完整组。
-- 该视图使 doctor 对已裁决的结构化统计 fail closed。
CREATE VIEW v_statistical_fact_quality_issues AS
SELECT
    'statistical_fact_metadata_invalid' AS issue_code,
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    s.statistic_scope,
    s.claim_id AS reference_claim_id
FROM v_current_structured_score_statistics s
WHERE s.sample_size IS NULL
   OR typeof(s.sample_size) <> 'integer'
   OR s.sample_size <= 0
   OR s.calculation_method_key IS NULL
   OR s.calculation_input_sha256 IS NULL
   OR length(s.calculation_input_sha256) <> 64
   OR s.calculation_input_sha256 <> lower(s.calculation_input_sha256)
   OR s.calculation_input_sha256 GLOB '*[^0-9a-f]*'
   OR s.calculation_method_key <> CASE
       WHEN s.statistic_name = 'min' THEN 'sample_min_v1'
       WHEN s.statistic_name = 'mean' THEN 'arithmetic_mean_v1'
       WHEN s.statistic_name = 'max' THEN 'sample_max_v1'
       ELSE 'percentile_inc_type7_v1'
   END

UNION ALL

SELECT
    'statistical_fact_count_missing',
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    MIN(s.statistic_scope),
    MIN(s.claim_id)
FROM v_current_structured_score_statistics s
WHERE (
    SELECT COUNT(*)
    FROM v_current_fact_resolutions count_resolution
    JOIN fact_claims count_claim
      ON count_claim.id = count_resolution.selected_claim_id
    JOIN fact_definitions count_definition
      ON count_definition.id = count_claim.fact_definition_id
    WHERE count_resolution.resolution_action = 'accept'
      AND count_resolution.observation_id = s.observation_id
      AND count_resolution.population_scope = s.population_scope
      AND count_definition.fact_key = s.count_fact_key
      AND count_claim.value_integer IS NOT NULL
) = 0
GROUP BY
    s.observation_id,
    s.statistic_family,
    s.population_scope

UNION ALL

SELECT
    'statistical_fact_count_ambiguous',
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    MIN(s.statistic_scope),
    MIN(s.claim_id)
FROM v_current_structured_score_statistics s
WHERE (
    SELECT COUNT(*)
    FROM v_current_fact_resolutions count_resolution
    JOIN fact_claims count_claim
      ON count_claim.id = count_resolution.selected_claim_id
    JOIN fact_definitions count_definition
      ON count_definition.id = count_claim.fact_definition_id
    WHERE count_resolution.resolution_action = 'accept'
      AND count_resolution.observation_id = s.observation_id
      AND count_resolution.population_scope = s.population_scope
      AND count_definition.fact_key = s.count_fact_key
      AND count_claim.value_integer IS NOT NULL
) > 1
GROUP BY
    s.observation_id,
    s.statistic_family,
    s.population_scope

UNION ALL

SELECT
    'statistical_fact_sample_size_count_mismatch',
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    MIN(s.statistic_scope),
    MIN(s.claim_id)
FROM v_current_structured_score_statistics s
JOIN v_current_fact_resolutions count_resolution
  ON count_resolution.observation_id = s.observation_id
 AND count_resolution.population_scope = s.population_scope
 AND count_resolution.resolution_action = 'accept'
JOIN fact_claims count_claim
  ON count_claim.id = count_resolution.selected_claim_id
JOIN fact_definitions count_definition
  ON count_definition.id = count_claim.fact_definition_id
 AND count_definition.fact_key = s.count_fact_key
WHERE count_claim.value_integer IS NULL
   OR s.sample_size IS NULL
   OR count_claim.value_integer <> s.sample_size
GROUP BY
    s.observation_id,
    s.statistic_family,
    s.population_scope
HAVING COUNT(DISTINCT count_claim.id) = 1

UNION ALL

SELECT
    'statistical_fact_input_inconsistent',
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    MIN(s.statistic_scope),
    MIN(s.claim_id)
FROM v_current_structured_score_statistics s
GROUP BY
    s.observation_id,
    s.statistic_family,
    s.population_scope
HAVING COUNT(DISTINCT (
    CAST(s.sample_size AS TEXT) || ':' || s.calculation_input_sha256
)) > 1

UNION ALL

SELECT
    'statistical_fact_quantile_triplet_incomplete',
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    MIN(s.statistic_scope),
    MIN(s.claim_id)
FROM v_current_structured_score_statistics s
WHERE s.statistic_family IN (
    'ordinary_general_admission_initial',
    'final_list_fulltime_blank_remark_initial',
    'final_list_first_choice_fulltime_non_directed_initial'
)
  AND s.statistic_name IN ('q25', 'q50', 'q75')
GROUP BY
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    s.sample_size,
    s.calculation_input_sha256
HAVING COUNT(DISTINCT s.statistic_name) <> 3

UNION ALL

SELECT
    'statistical_fact_quantile_order_invalid',
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    MIN(s.statistic_scope),
    MIN(s.claim_id)
FROM v_current_structured_score_statistics s
WHERE s.statistic_family IN (
    'ordinary_general_admission_initial',
    'final_list_fulltime_blank_remark_initial',
    'final_list_first_choice_fulltime_non_directed_initial'
)
  AND s.statistic_name IN ('q25', 'q50', 'q75')
GROUP BY
    s.observation_id,
    s.statistic_family,
    s.population_scope,
    s.sample_size,
    s.calculation_input_sha256
HAVING COUNT(DISTINCT s.statistic_name) = 3
   AND NOT (
       MAX(CASE WHEN s.statistic_name = 'q25' THEN s.value_decimal END)
       <= MAX(CASE WHEN s.statistic_name = 'q50' THEN s.value_decimal END)
       AND MAX(CASE WHEN s.statistic_name = 'q50' THEN s.value_decimal END)
       <= MAX(CASE WHEN s.statistic_name = 'q75' THEN s.value_decimal END)
   );
