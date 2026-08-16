ALTER TABLE fact_claims
ADD COLUMN derivation_operator TEXT;

ALTER TABLE fact_claims
ADD COLUMN derivation_left_fact_key TEXT;

ALTER TABLE fact_claims
ADD COLUMN derivation_left_value_integer INTEGER;

ALTER TABLE fact_claims
ADD COLUMN derivation_right_fact_key TEXT;

ALTER TABLE fact_claims
ADD COLUMN derivation_right_value_integer INTEGER;

-- 只有“复试阶段总计划 - 已接收推免”这一事实键可以携带推导元数据。
-- 旧主张在本迁移后五列均为 NULL；它们保持原样，不被追溯改写。
CREATE TRIGGER validate_plan_minus_received_recommendation_insert
BEFORE INSERT ON fact_claims
WHEN (
    SELECT fact_key
    FROM fact_definitions
    WHERE id = NEW.fact_definition_id
) = 'quota.plan_minus_received_recommendation'
AND NOT COALESCE(
    (
        NEW.derivation_operator = 'subtract'
        AND NEW.derivation_left_fact_key = 'quota.total_plan'
        AND NEW.derivation_left_value_integer IS NOT NULL
        AND NEW.derivation_left_value_integer >= 0
        AND NEW.derivation_right_fact_key = 'quota.recommendation_received'
        AND NEW.derivation_right_value_integer IS NOT NULL
        AND NEW.derivation_right_value_integer >= 0
        AND NEW.value_integer IS NOT NULL
        AND NEW.value_integer >= 0
        AND NEW.value_integer = (
            NEW.derivation_left_value_integer - NEW.derivation_right_value_integer
        )
    ),
    0
)
BEGIN
    SELECT RAISE(
        ABORT,
        'invalid quota.plan_minus_received_recommendation derivation'
    );
END;

CREATE TRIGGER forbid_derivation_metadata_on_non_derived_fact_insert
BEFORE INSERT ON fact_claims
WHEN COALESCE(
    (
        SELECT fact_key
        FROM fact_definitions
        WHERE id = NEW.fact_definition_id
    ),
    ''
) <> 'quota.plan_minus_received_recommendation'
AND (
    NEW.derivation_operator IS NOT NULL
    OR NEW.derivation_left_fact_key IS NOT NULL
    OR NEW.derivation_left_value_integer IS NOT NULL
    OR NEW.derivation_right_fact_key IS NOT NULL
    OR NEW.derivation_right_value_integer IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'derivation metadata is forbidden for this fact key');
END;

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

UPDATE fact_definitions
SET
    description = (
        '最终推免拟录取公示名单按同一项目、同一招生年度逐行筛选得到的项目级行数；'
        || '表示公示阶段的拟录取名单人数，不是最终报到、入学或学籍注册人数'
    ),
    preferred_source_type = '最终推免拟录取公示名单逐行统计'
WHERE fact_key = 'quota.recommendation_actual';
