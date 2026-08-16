CREATE INDEX IF NOT EXISTS idx_subject_verifications_observation_verified
    ON subject_verifications(observation_id, verified_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_subject_verifications_observation_subjects
    ON subject_verifications(
        observation_id,
        politics_code,
        english_code,
        math_code,
        professional_code
    );

DROP VIEW v_catalog;

CREATE VIEW v_catalog AS
WITH verification_combinations AS (
    SELECT
        observation_id,
        politics_code,
        english_code,
        math_code,
        professional_code
    FROM subject_verifications
    GROUP BY
        observation_id,
        politics_code,
        english_code,
        math_code,
        professional_code
),
verification_summary AS (
    SELECT
        observation_id,
        COUNT(*) AS distinct_subject_combinations
    FROM verification_combinations
    GROUP BY observation_id
),
latest_verification AS (
    SELECT sv.*
    FROM subject_verifications sv
    WHERE sv.id = (
        SELECT candidate.id
        FROM subject_verifications candidate
        WHERE candidate.observation_id = sv.observation_id
        ORDER BY candidate.verified_at DESC, candidate.id DESC
        LIMIT 1
    )
)
SELECT
    o.id AS observation_id,
    r.source_row_number,
    sf.archive_member,
    s.display_name AS school,
    c.display_name AS college,
    p.program_code,
    p.program_name,
    p.direction,
    p.campus,
    p.training_location,
    p.study_mode,
    p.training_type_raw,
    p.admission_type,
    p.degree_type,
    p.training_arrangement,
    o.admission_year,
    o.strict_22408_claim,
    CASE
        WHEN COALESCE(vs.distinct_subject_combinations, 0) > 1 THEN 'conflict'
        ELSE COALESCE(lv.derived_status, o.strict_22408_evidence_status)
    END AS strict_22408_status,
    o.strict_22408_evidence_status AS imported_evidence_status,
    CAST(
        CASE
            WHEN COALESCE(vs.distinct_subject_combinations, 0) > 1 THEN NULL
            ELSE COALESCE(lv.politics_code, o.subject_politics_code)
        END AS TEXT
    ) AS subject_politics_code,
    CAST(
        CASE
            WHEN COALESCE(vs.distinct_subject_combinations, 0) > 1 THEN NULL
            ELSE COALESCE(lv.english_code, o.subject_english_code)
        END AS TEXT
    ) AS subject_english_code,
    CAST(
        CASE
            WHEN COALESCE(vs.distinct_subject_combinations, 0) > 1 THEN NULL
            ELSE COALESCE(lv.math_code, o.subject_math_code)
        END AS TEXT
    ) AS subject_math_code,
    CAST(
        CASE
            WHEN COALESCE(vs.distinct_subject_combinations, 0) > 1 THEN NULL
            ELSE COALESCE(lv.professional_code, o.subject_professional_code)
        END AS TEXT
    ) AS subject_professional_code,
    o.effective_general_exam_quota,
    o.retest_cutoff,
    o.retest_count,
    o.general_exam_admit_count,
    o.admit_initial_min,
    o.admit_initial_median,
    o.admit_initial_mean,
    o.initial_exam_weight,
    o.retest_weight,
    o.machine_test_weight,
    o.machine_test_elimination_line,
    o.tuition_per_year,
    o.study_length_years,
    o.first_choice_protection,
    o.evidence_grade,
    o.official_source,
    o.retrieval_date,
    o.notes,
    (
        SELECT COUNT(*)
        FROM data_quality_issues q
        WHERE q.observation_id = o.id AND q.status = 'open'
    ) AS open_issue_count
FROM project_year_observations o
JOIN projects p ON p.id = o.project_id
JOIN schools s ON s.id = p.school_id
JOIN colleges c ON c.id = p.college_id
JOIN raw_catalog_rows r ON r.id = o.raw_row_id
JOIN source_files sf ON sf.id = r.source_file_id
LEFT JOIN verification_summary vs ON vs.observation_id = o.id
LEFT JOIN latest_verification lv ON lv.observation_id = o.id;
