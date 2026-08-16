CREATE TABLE fact_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_key TEXT NOT NULL UNIQUE,
    data_type TEXT NOT NULL CHECK (data_type IN ('integer', 'decimal', 'text', 'boolean')),
    unit TEXT,
    description TEXT NOT NULL,
    preferred_source_type TEXT NOT NULL
);

INSERT INTO fact_definitions(fact_key, data_type, unit, description, preferred_source_type) VALUES
    ('quota.total_plan', 'integer', '人', '总招生计划', '正式招生目录或计划公告'),
    ('quota.recommendation_actual', 'integer', '人', '推免实际录取人数', '最终推免名单'),
    ('quota.special', 'integer', '人', '专项计划人数', '正式名单或专项公告'),
    ('quota.general_effective', 'integer', '人', '普通统考有效名额', '正式目录与最终名单复算'),
    ('retest.cutoff_total', 'decimal', '分', '同口径复试总分线', '学院复试方案或复试名单'),
    ('retest.entered_count', 'integer', '人', '普通统考实际进入复试人数', '正式复试名单'),
    ('admission.general_count', 'integer', '人', '普通统考最终拟录取人数', '最终拟录取名单'),
    ('score.initial.min', 'decimal', '分', '普通统考拟录取初试最低分', '最终拟录取名单逐人复算'),
    ('score.initial.median', 'decimal', '分', '普通统考拟录取初试中位数', '最终拟录取名单逐人复算'),
    ('score.initial.mean', 'decimal', '分', '普通统考拟录取初试均值', '最终拟录取名单逐人复算'),
    ('weight.initial', 'decimal', '0-1', '初试成绩权重', '学院复试办法'),
    ('weight.retest', 'decimal', '0-1', '复试成绩权重', '学院复试办法'),
    ('weight.machine', 'decimal', '0-1', '机试在综合成绩中的权重', '学院复试办法'),
    ('machine.elimination_line', 'decimal', '分', '机试硬性淘汰线', '学院复试办法'),
    ('tuition.amount', 'decimal', '元', '学费金额', '正式收费公示'),
    ('tuition.basis', 'text', NULL, '学费周期：每年或全程', '正式收费公示'),
    ('study.duration_months', 'integer', '月', '标准学制', '正式招生简章'),
    ('first_choice.protection', 'boolean', NULL, '一志愿是否单独排序或保护', '学院复试调剂办法');

CREATE TABLE fact_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_fingerprint TEXT NOT NULL UNIQUE,
    observation_id INTEGER NOT NULL REFERENCES project_year_observations(id) ON DELETE CASCADE,
    fact_definition_id INTEGER NOT NULL REFERENCES fact_definitions(id),
    population_scope TEXT NOT NULL DEFAULT 'ordinary_general_exam',
    statistic_scope TEXT NOT NULL DEFAULT 'project',
    value_integer INTEGER,
    value_decimal REAL,
    value_text TEXT,
    value_boolean INTEGER CHECK (value_boolean IN (0, 1) OR value_boolean IS NULL),
    source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
    evidence_grade TEXT NOT NULL CHECK (
        evidence_grade IN ('official', 'official_mixed', 'secondary', 'tertiary', 'unknown')
    ),
    note TEXT,
    trace_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (
        (CASE WHEN value_integer IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN value_decimal IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN value_text IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN value_boolean IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX ix_fact_claim_identity
    ON fact_claims(observation_id, fact_definition_id, population_scope, statistic_scope);

CREATE TABLE fact_resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL REFERENCES project_year_observations(id) ON DELETE CASCADE,
    fact_definition_id INTEGER NOT NULL REFERENCES fact_definitions(id),
    population_scope TEXT NOT NULL,
    statistic_scope TEXT NOT NULL,
    selected_claim_id INTEGER REFERENCES fact_claims(id),
    resolution_action TEXT NOT NULL CHECK (resolution_action IN ('accept', 'unresolved')),
    reason TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX ix_fact_resolution_identity
    ON fact_resolutions(observation_id, fact_definition_id, population_scope, statistic_scope, created_at, id);

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

CREATE VIEW v_fact_conflicts AS
SELECT
    fc.observation_id,
    fd.fact_key,
    fc.population_scope,
    fc.statistic_scope,
    COUNT(*) AS claim_count,
    COUNT(DISTINCT (
        CASE
            WHEN fc.value_integer IS NOT NULL THEN 'i:' || CAST(fc.value_integer AS TEXT)
            WHEN fc.value_decimal IS NOT NULL THEN 'd:' || printf('%.12g', fc.value_decimal)
            WHEN fc.value_text IS NOT NULL THEN 't:' || fc.value_text
            ELSE 'b:' || CAST(fc.value_boolean AS TEXT)
        END
    )) AS distinct_value_count
FROM fact_claims fc
JOIN fact_definitions fd ON fd.id = fc.fact_definition_id
GROUP BY fc.observation_id, fd.fact_key, fc.population_scope, fc.statistic_scope
HAVING COUNT(DISTINCT (
    CASE
        WHEN fc.value_integer IS NOT NULL THEN 'i:' || CAST(fc.value_integer AS TEXT)
        WHEN fc.value_decimal IS NOT NULL THEN 'd:' || printf('%.12g', fc.value_decimal)
        WHEN fc.value_text IS NOT NULL THEN 't:' || fc.value_text
        ELSE 'b:' || CAST(fc.value_boolean AS TEXT)
    END
)) > 1;

CREATE VIEW v_current_fact_resolutions AS
SELECT
    fr.id AS resolution_id,
    fr.observation_id,
    fd.fact_key,
    fr.population_scope,
    fr.statistic_scope,
    fr.selected_claim_id,
    fr.resolution_action,
    fr.reason,
    fr.trace_id,
    fr.created_at
FROM fact_resolutions fr
JOIN fact_definitions fd ON fd.id = fr.fact_definition_id
WHERE NOT EXISTS (
    SELECT 1
    FROM fact_resolutions newer
    WHERE newer.observation_id = fr.observation_id
      AND newer.fact_definition_id = fr.fact_definition_id
      AND newer.population_scope = fr.population_scope
      AND newer.statistic_scope = fr.statistic_scope
      AND (newer.created_at > fr.created_at OR (newer.created_at = fr.created_at AND newer.id > fr.id))
);

CREATE TRIGGER protect_fact_claims_update
BEFORE UPDATE ON fact_claims
BEGIN
    SELECT RAISE(ABORT, 'fact_claims are append-only');
END;

CREATE TRIGGER protect_fact_claims_delete
BEFORE DELETE ON fact_claims
BEGIN
    SELECT RAISE(ABORT, 'fact_claims are append-only');
END;

CREATE TRIGGER protect_fact_resolutions_update
BEFORE UPDATE ON fact_resolutions
BEGIN
    SELECT RAISE(ABORT, 'fact_resolutions are append-only');
END;

CREATE TRIGGER protect_fact_resolutions_delete
BEFORE DELETE ON fact_resolutions
BEGIN
    SELECT RAISE(ABORT, 'fact_resolutions are append-only');
END;
