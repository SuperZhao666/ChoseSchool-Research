-- Keep the ordinary-admission fact family fail-closed.  A source may be
-- official while the population is mixed or rule-derived; that is not enough
-- to populate an ordinary_general_exam machine field.

INSERT INTO fact_definitions(
    fact_key, data_type, unit, description, preferred_source_type
) VALUES
    (
        'admission.suggested_list_total_count', 'integer', '人',
        '官方建议录取名单总行数；不是最终拟录取人数',
        '学院建议录取名单'
    ),
    (
        'admission.suggested_list_blank_remark_count', 'integer', '人',
        '官方建议录取名单中备注为空的行数；不是普通统考最终人数',
        '学院建议录取名单'
    ),
    (
        'admission.suggested_list_special_count', 'integer', '人',
        '官方建议录取名单中明确专项备注的行数',
        '学院建议录取名单'
    );

CREATE TRIGGER fact_claims_reject_nonofficial_ordinary_machine_fact
BEFORE INSERT ON fact_claims
WHEN NEW.evidence_grade <> 'official'
 AND EXISTS (
     SELECT 1
     FROM fact_definitions definition
     WHERE definition.id = NEW.fact_definition_id
       AND definition.fact_key IN (
           'admission.general_count',
           'score.initial.min',
           'score.initial.q25',
           'score.initial.median',
           'score.initial.mean',
           'score.initial.q75'
       )
 )
BEGIN
    SELECT RAISE(
        ABORT,
        'ordinary machine facts require evidence_grade=official'
    );
END;

CREATE VIEW v_current_accepted_fact_evidence AS
SELECT *
FROM v_current_resolved_fact_evidence
WHERE resolution_action = 'accept'
  AND selected_claim_id IS NOT NULL;

CREATE VIEW v_current_unresolved_fact_evidence AS
SELECT *
FROM v_current_resolved_fact_evidence
WHERE resolution_action = 'unresolved'
   OR selected_claim_id IS NULL;
