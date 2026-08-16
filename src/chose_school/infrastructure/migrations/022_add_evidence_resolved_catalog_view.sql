INSERT INTO fact_definitions(
    fact_key,
    data_type,
    unit,
    description,
    preferred_source_type
) VALUES
    (
        'admission.final_list_fulltime_blank_remark_count',
        'integer',
        '人',
        '最终拟录取名单中目标项目、全日制且备注为空的行数；不自动等同普通统考录取人数',
        '最终拟录取名单逐行筛选'
    ),
    (
        'score.final_list_fulltime_blank_remark_initial.min',
        'decimal',
        '分',
        '最终拟录取名单中目标项目、全日制且备注为空行的初试总分最低值；不自动等同普通统考最低分',
        '最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_fulltime_blank_remark_initial.median',
        'decimal',
        '分',
        '最终拟录取名单中目标项目、全日制且备注为空行的初试总分中位数；不自动等同普通统考中位数',
        '最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_fulltime_blank_remark_initial.mean',
        'decimal',
        '分',
        '最终拟录取名单中目标项目、全日制且备注为空行的初试总分算术均值；不自动等同普通统考均值',
        '最终拟录取名单逐行复算'
    ),
    (
        'training.city',
        'text',
        NULL,
        '项目培养城市；必须由项目培养安排明确支持，不能由复试或迎新地点推断',
        '正式招生目录、培养安排或录取通知'
    ),
    (
        'training.campus',
        'text',
        NULL,
        '项目精确培养校区；必须由项目培养安排明确支持，不能由复试或迎新地点推断',
        '正式招生目录、培养安排或录取通知'
    );

CREATE VIEW v_catalog_evidence_resolved AS
WITH current_accepted AS (
    SELECT
        resolution.observation_id,
        resolution.fact_key,
        claim.value_integer,
        claim.value_decimal,
        claim.value_text,
        claim.value_boolean,
        COUNT(*) OVER (
            PARTITION BY resolution.observation_id, resolution.fact_key
        ) AS current_scope_count
    FROM v_current_fact_resolutions resolution
    JOIN fact_claims claim ON claim.id = resolution.selected_claim_id
    WHERE resolution.resolution_action = 'accept'
),
unique_current AS (
    SELECT *
    FROM current_accepted
    WHERE current_scope_count = 1
),
resolved_values AS (
    SELECT
        observation_id,
        MAX(CASE WHEN fact_key = 'quota.general_effective'
            THEN value_integer END) AS effective_general_exam_quota,
        MAX(CASE WHEN fact_key = 'retest.cutoff_total'
            THEN value_decimal END) AS retest_cutoff,
        MAX(CASE WHEN fact_key = 'retest.entered_count'
            THEN value_integer END) AS retest_count,
        MAX(CASE WHEN fact_key = 'admission.general_count'
            THEN value_integer END) AS general_exam_admit_count,
        MAX(CASE WHEN fact_key = 'score.initial.min'
            THEN value_decimal END) AS admit_initial_min,
        MAX(CASE WHEN fact_key = 'score.initial.median'
            THEN value_decimal END) AS admit_initial_median,
        MAX(CASE WHEN fact_key = 'score.initial.mean'
            THEN value_decimal END) AS admit_initial_mean,
        MAX(CASE WHEN fact_key = 'weight.initial'
            THEN value_decimal END) AS initial_exam_weight,
        MAX(CASE WHEN fact_key = 'weight.retest'
            THEN value_decimal END) AS retest_weight,
        MAX(CASE WHEN fact_key = 'weight.machine'
            THEN value_decimal END) AS machine_test_weight,
        MAX(CASE WHEN fact_key = 'machine.elimination_line'
            THEN value_decimal END) AS machine_test_elimination_line,
        MAX(CASE WHEN fact_key = 'tuition.amount'
            THEN value_decimal END) AS tuition_amount,
        MAX(CASE WHEN fact_key = 'tuition.basis'
            THEN value_text END) AS tuition_basis,
        MAX(CASE WHEN fact_key = 'study.duration_months'
            THEN value_integer END) AS study_duration_months,
        MAX(CASE WHEN fact_key = 'first_choice.protection'
            THEN value_boolean END) AS first_choice_protection,
        MAX(CASE WHEN fact_key = 'training.city'
            THEN value_text END) AS training_city,
        MAX(CASE WHEN fact_key = 'training.campus'
            THEN value_text END) AS training_campus
    FROM unique_current
    GROUP BY observation_id
)
SELECT
    catalog.observation_id,
    catalog.source_row_number,
    catalog.archive_member,
    catalog.school,
    catalog.college,
    catalog.program_code,
    catalog.program_name,
    catalog.direction,
    CAST(resolved.training_campus AS TEXT) AS campus,
    CAST(resolved.training_city AS TEXT) AS training_location,
    catalog.study_mode,
    catalog.training_type_raw,
    catalog.admission_type,
    catalog.degree_type,
    catalog.training_arrangement,
    catalog.admission_year,
    catalog.strict_22408_claim,
    CAST(catalog.strict_22408_status AS TEXT) AS strict_22408_status,
    catalog.imported_evidence_status,
    CAST(
        CASE WHEN EXISTS (
            SELECT 1 FROM subject_verifications verification
            WHERE verification.observation_id = catalog.observation_id
        ) THEN catalog.subject_politics_code ELSE NULL END
        AS TEXT
    ) AS subject_politics_code,
    CAST(
        CASE WHEN EXISTS (
            SELECT 1 FROM subject_verifications verification
            WHERE verification.observation_id = catalog.observation_id
        ) THEN catalog.subject_english_code ELSE NULL END
        AS TEXT
    ) AS subject_english_code,
    CAST(
        CASE WHEN EXISTS (
            SELECT 1 FROM subject_verifications verification
            WHERE verification.observation_id = catalog.observation_id
        ) THEN catalog.subject_math_code ELSE NULL END
        AS TEXT
    ) AS subject_math_code,
    CAST(
        CASE WHEN EXISTS (
            SELECT 1 FROM subject_verifications verification
            WHERE verification.observation_id = catalog.observation_id
        ) THEN catalog.subject_professional_code ELSE NULL END
        AS TEXT
    ) AS subject_professional_code,
    CAST(resolved.effective_general_exam_quota AS INTEGER)
        AS effective_general_exam_quota,
    CAST(resolved.retest_cutoff AS REAL) AS retest_cutoff,
    CAST(resolved.retest_count AS INTEGER) AS retest_count,
    CAST(resolved.general_exam_admit_count AS INTEGER)
        AS general_exam_admit_count,
    CAST(resolved.admit_initial_min AS REAL) AS admit_initial_min,
    CAST(resolved.admit_initial_median AS REAL) AS admit_initial_median,
    CAST(resolved.admit_initial_mean AS REAL) AS admit_initial_mean,
    CAST(resolved.initial_exam_weight AS REAL) AS initial_exam_weight,
    CAST(resolved.retest_weight AS REAL) AS retest_weight,
    CAST(resolved.machine_test_weight AS REAL) AS machine_test_weight,
    CAST(resolved.machine_test_elimination_line AS REAL)
        AS machine_test_elimination_line,
    CAST(
        CASE
            WHEN resolved.tuition_basis IN ('每年', '每学年', '每生每学年')
                THEN resolved.tuition_amount
            ELSE NULL
        END AS REAL
    ) AS tuition_per_year,
    CAST(
        CASE
            WHEN resolved.study_duration_months IS NOT NULL
                THEN resolved.study_duration_months / 12.0
            ELSE NULL
        END AS REAL
    ) AS study_length_years,
    CAST(resolved.first_choice_protection AS INTEGER)
        AS first_choice_protection,
    CAST(NULL AS TEXT) AS evidence_grade,
    CAST(NULL AS TEXT) AS official_source,
    CAST(NULL AS TEXT) AS retrieval_date,
    CAST(NULL AS TEXT) AS notes,
    CAST(catalog.open_issue_count AS INTEGER) AS open_issue_count
FROM v_catalog catalog
LEFT JOIN resolved_values resolved
  ON resolved.observation_id = catalog.observation_id;
