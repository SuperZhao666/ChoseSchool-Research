from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from chose_school.domain.models import (
    CatalogArchive,
    CatalogFilter,
    CatalogObservation,
    ImportResult,
    NormalizedRow,
    ValidationIssue,
)
from chose_school.domain.errors import EntityNotFoundError, StateConflictError
from chose_school.infrastructure.database import Database
from chose_school.data_access.candidate_model_integrity import (
    CANDIDATE_MODEL_DOCTOR_METRICS,
    candidate_model_doctor_metrics,
)


CRITICAL_EVIDENCE_FIELDS = (
    "is_strict_22408",
    "total_plan",
    "recommendation_actual",
    "special_plan",
    "effective_general_exam_quota",
    "retest_cutoff",
    "retest_count",
    "general_exam_admit_count",
    "admit_initial_min",
    "admit_initial_median",
    "admit_initial_mean",
    "initial_exam_weight",
    "retest_weight",
    "machine_test_weight",
    "machine_test_elimination_line",
    "tuition_per_year",
    "study_length",
    "first_choice_protection",
)

NORMALIZED_ATTRIBUTE_BY_RAW_FIELD = {
    "is_strict_22408": "strict_claim",
    "study_length": "study_length_years",
}

_URL_PATTERN = re.compile(r"https?://[^\s,;，；]+")

_STATISTICAL_FACT_DOCTOR_ERROR_QUERIES = {
    issue_code: (
        "SELECT COUNT(*) FROM v_statistical_fact_quality_issues "
        f"WHERE issue_code = '{issue_code}'"
    )
    for issue_code in (
        "statistical_fact_metadata_invalid",
        "statistical_fact_count_missing",
        "statistical_fact_count_ambiguous",
        "statistical_fact_sample_size_count_mismatch",
        "statistical_fact_input_inconsistent",
        "statistical_fact_quantile_triplet_incomplete",
        "statistical_fact_quantile_order_invalid",
    )
}

_MOCK_EXAM_DOCTOR_ERROR_QUERIES = {
    "mock_v2_missing_audit": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND NOT EXISTS (
              SELECT 1
              FROM audit_events audit
              WHERE audit.trace_id = session.trace_id
                AND audit.event_type = 'mock_exam_added'
                AND audit.entity_type = 'mock_exam_session'
                AND audit.entity_id = CAST(session.id AS TEXT)
          )
    """,
    "mock_exclusion_missing_audit": """
        SELECT COUNT(*)
        FROM mock_exam_session_exclusions exclusion
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = exclusion.trace_id
              AND audit.event_type = 'mock_exam_excluded'
              AND audit.entity_type = 'mock_exam_session_exclusion'
              AND audit.entity_id = CAST(exclusion.id AS TEXT)
        )
    """,
    "legacy_mock_missing_audit": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 1
          AND (
              (session.trace_id IS NOT NULL
               AND length(trim(session.trace_id)) = 0)
              OR NOT EXISTS (
                  SELECT 1
                  FROM audit_events audit
                  WHERE audit.event_type = 'mock_exam_added'
                    AND audit.entity_type = 'mock_exam_session'
                    AND audit.entity_id = CAST(session.id AS TEXT)
                    AND (
                        session.trace_id IS NULL
                        OR audit.trace_id = session.trace_id
                    )
              )
          )
    """,
    "mock_v2_subject_count_mismatch": """
        SELECT COUNT(*)
        FROM (
            SELECT session.id,
                   COUNT(result.id) AS result_count,
                   COUNT(DISTINCT result.subject_code) AS distinct_subject_count
            FROM mock_exam_sessions session
            LEFT JOIN mock_exam_subject_results result
              ON result.session_id = session.id
            WHERE session.ledger_version = 2
            GROUP BY session.id
        ) counts
        WHERE counts.result_count != 4
           OR counts.distinct_subject_count != 4
    """,
    "mock_v2_subject_code_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        JOIN applicant_profiles profile ON profile.id = session.profile_id
        WHERE session.ledger_version = 2
          AND (
              NOT EXISTS (
                  SELECT 1 FROM mock_exam_subject_results result
                  WHERE result.session_id = session.id
                    AND result.subject_code = profile.politics_code
              )
              OR NOT EXISTS (
                  SELECT 1 FROM mock_exam_subject_results result
                  WHERE result.session_id = session.id
                    AND result.subject_code = profile.english_code
              )
              OR NOT EXISTS (
                  SELECT 1 FROM mock_exam_subject_results result
                  WHERE result.session_id = session.id
                    AND result.subject_code = profile.math_code
              )
              OR NOT EXISTS (
                  SELECT 1 FROM mock_exam_subject_results result
                  WHERE result.session_id = session.id
                    AND result.subject_code = profile.professional_code
              )
              OR EXISTS (
                  SELECT 1 FROM mock_exam_subject_results result
                  WHERE result.session_id = session.id
                    AND result.subject_code NOT IN (
                        profile.politics_code,
                        profile.english_code,
                        profile.math_code,
                        profile.professional_code
                    )
              )
          )
    """,
    "mock_subject_trace_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_subject_results result
        LEFT JOIN mock_exam_sessions session ON session.id = result.session_id
        WHERE session.id IS NULL
           OR session.ledger_version != 2
           OR session.trace_id IS NULL
           OR result.trace_id IS NULL
           OR result.trace_id != session.trace_id
    """,
    "mock_v2_attendance_score_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_subject_results result
        JOIN mock_exam_sessions session ON session.id = result.session_id
        WHERE session.ledger_version = 2
          AND CASE
              WHEN result.attendance_status = 'present_scored'
               AND result.score_lower IS NOT NULL
               AND result.score_upper IS NOT NULL
               AND result.maximum_score > 0
               AND result.score_lower >= 0
               AND result.score_lower <= result.score_upper
               AND result.score_upper <= result.maximum_score
               AND result.started_at IS NOT NULL
               AND result.ended_at IS NOT NULL
               AND result.actual_duration_minutes > 0
              THEN 0
              WHEN result.attendance_status = 'present_blank'
               AND result.score_lower = 0
               AND result.score_upper = 0
               AND result.maximum_score > 0
               AND result.started_at IS NOT NULL
               AND result.ended_at IS NOT NULL
               AND result.actual_duration_minutes > 0
              THEN 0
              WHEN result.attendance_status = 'absent'
               AND result.score_lower IS NULL
               AND result.score_upper IS NULL
               AND result.maximum_score > 0
               AND result.started_at IS NULL
               AND result.ended_at IS NULL
               AND result.actual_duration_minutes IS NULL
              THEN 0
              ELSE 1
          END = 1
    """,
    "mock_v2_validity_reason_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND CASE
              WHEN session.first_exposure = 1
               AND session.complete_paper_set = 1
               AND session.strict_schedule = 1
               AND session.authentic_time_slots = 1
               AND session.strict_timed = 1
               AND session.consulted_materials = 0
               AND session.received_assistance = 0
               AND session.paused_timer = 0
               AND session.reviewed_answers_early = 0
               AND date(session.completed_on) = date(session.taken_on, '+1 day')
               AND session.invalid_reason_code IS NULL
               AND length(trim(COALESCE(session.invalid_reason_note, ''))) = 0
              THEN 0
              WHEN (
                   session.first_exposure = 0
                   OR session.complete_paper_set = 0
                   OR session.strict_schedule = 0
                   OR session.authentic_time_slots = 0
                   OR session.strict_timed = 0
                   OR session.consulted_materials = 1
                   OR session.received_assistance = 1
                   OR session.paused_timer = 1
                   OR session.reviewed_answers_early = 1
                   OR date(session.completed_on) != date(session.taken_on, '+1 day')
               )
               AND session.invalid_reason_code IS NOT NULL
               AND length(trim(COALESCE(session.invalid_reason_note, ''))) > 0
              THEN 0
              ELSE 1
          END = 1
    """,
    "mock_v2_scoring_rule_missing": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND length(trim(COALESCE(session.scoring_rule_key, ''))) = 0
    """,
    "mock_v2_protocol_fact_missing": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND (
              length(trim(COALESCE(session.trace_id, ''))) = 0
              OR length(trim(COALESCE(session.paper_key, ''))) = 0
              OR length(trim(COALESCE(session.paper_source, ''))) = 0
              OR length(trim(COALESCE(session.exam_contract, ''))) = 0
              OR session.completed_on IS NULL
              OR session.first_exposure IS NULL
              OR session.complete_paper_set IS NULL
              OR session.strict_schedule IS NULL
              OR session.authentic_time_slots IS NULL
              OR session.consulted_materials IS NULL
              OR session.received_assistance IS NULL
              OR session.paused_timer IS NULL
              OR session.reviewed_answers_early IS NULL
              OR session.paper_family IS NULL
              OR session.difficulty_label IS NULL
              OR (session.attempt_number > 1 AND session.first_exposure = 1)
          )
    """,
    "mock_v2_subject_schedule_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_subject_results result
        JOIN mock_exam_sessions session ON session.id = result.session_id
        WHERE session.ledger_version = 2
          AND result.attendance_status != 'absent'
          AND CASE
              WHEN julianday(result.started_at) IS NULL
                OR julianday(result.ended_at) IS NULL
              THEN 1
              WHEN julianday(result.ended_at) <= julianday(result.started_at)
              THEN 1
              WHEN CAST(ROUND(
                  (julianday(result.ended_at) - julianday(result.started_at)) * 1440.0
              ) AS INTEGER) != result.actual_duration_minutes
              THEN 1
              WHEN session.authentic_time_slots = 1
               AND (
                   (
                       result.started_at NOT GLOB '*[+-][0-9][0-9]:[0-9][0-9]'
                       AND result.started_at NOT GLOB '*Z'
                   )
                   OR (
                       result.ended_at NOT GLOB '*[+-][0-9][0-9]:[0-9][0-9]'
                       AND result.ended_at NOT GLOB '*Z'
                   )
                   OR date(result.started_at, '+8 hours') != CASE
                       WHEN result.subject_code IN ('101', '204') THEN date(session.taken_on)
                       WHEN result.subject_code IN ('302', '408') THEN date(session.completed_on)
                   END
                   OR date(result.ended_at, '+8 hours') != CASE
                       WHEN result.subject_code IN ('101', '204') THEN date(session.taken_on)
                       WHEN result.subject_code IN ('302', '408') THEN date(session.completed_on)
                   END
                   OR strftime('%H:%M:%f', result.started_at, '+8 hours') !=
                       CASE result.subject_code
                           WHEN '101' THEN '08:30:00.000'
                           WHEN '204' THEN '14:00:00.000'
                           WHEN '302' THEN '08:30:00.000'
                           WHEN '408' THEN '14:00:00.000'
                       END
                   OR strftime('%H:%M:%f', result.ended_at, '+8 hours') !=
                       CASE result.subject_code
                           WHEN '101' THEN '11:30:00.000'
                           WHEN '204' THEN '17:00:00.000'
                           WHEN '302' THEN '11:30:00.000'
                           WHEN '408' THEN '17:00:00.000'
                   END
               )
              THEN 1
              ELSE 0
          END = 1
    """,
    "mock_v2_subject_maximum_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_subject_results result
        JOIN mock_exam_sessions session ON session.id = result.session_id
        WHERE session.ledger_version = 2
          AND result.maximum_score != CASE result.subject_code
              WHEN '101' THEN 100
              WHEN '204' THEN 100
              WHEN '302' THEN 150
              WHEN '408' THEN 150
              ELSE result.maximum_score
          END
    """,
    "mock_v2_calendar_overlap": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND EXISTS (
              SELECT 1
              FROM mock_exam_sessions prior
              WHERE prior.profile_id = session.profile_id
                AND prior.ledger_version = 2
                AND prior.id < session.id
                AND date(session.taken_on) <= date(prior.completed_on)
                AND date(session.completed_on) >= date(prior.taken_on)
          )
    """,
    "mock_v2_paper_key_reuse_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND session.first_exposure = 1
          AND EXISTS (
              SELECT 1
              FROM mock_exam_sessions prior
              WHERE prior.profile_id = session.profile_id
                AND prior.ledger_version = 2
                AND prior.id < session.id
                AND prior.paper_key = session.paper_key
          )
    """,
    "mock_v2_content_hash_reuse_mismatch": """
        SELECT COUNT(*)
        FROM mock_exam_sessions session
        WHERE session.ledger_version = 2
          AND session.first_exposure = 1
          AND session.paper_content_sha256 IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM mock_exam_sessions prior
              WHERE prior.profile_id = session.profile_id
                AND prior.ledger_version = 2
                AND prior.id < session.id
                AND lower(prior.paper_content_sha256) =
                    lower(session.paper_content_sha256)
          )
    """,
}

_POLICY_EVENT_DOCTOR_ERROR_QUERIES = {
    "policy_event_missing_trace": """
        SELECT COUNT(*)
        FROM policy_events event
        WHERE event.trace_id IS NULL OR length(trim(event.trace_id)) = 0
    """,
    "policy_event_missing_fingerprint": """
        SELECT COUNT(*)
        FROM policy_events event
        WHERE event.event_fingerprint IS NULL
           OR length(event.event_fingerprint) != 64
           OR event.event_fingerprint != lower(event.event_fingerprint)
           OR event.event_fingerprint GLOB '*[^0-9a-f]*'
    """,
    "policy_event_missing_audit": """
        SELECT COUNT(*)
        FROM policy_events event
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = event.trace_id
              AND audit.event_type = 'policy_event_added'
              AND audit.entity_type = 'policy_event'
              AND audit.entity_id = CAST(event.id AS TEXT)
        )
    """,
    "policy_event_duplicate_audit": """
        SELECT COUNT(*)
        FROM policy_events event
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = event.trace_id
              AND audit.event_type = 'policy_event_added'
              AND audit.entity_type = 'policy_event'
              AND audit.entity_id = CAST(event.id AS TEXT)
        )
    """,
    "policy_event_source_metadata_invalid": """
        SELECT COUNT(*)
        FROM policy_events event
        LEFT JOIN evidence_sources source ON source.id = event.source_id
        WHERE source.id IS NULL
           OR source.evidence_grade != 'official'
           OR source.document_type != 'official_notice'
           OR source.content_sha256 != event.source_content_sha256
    """,
    "policy_event_missing_source_snapshot": """
        SELECT COUNT(*)
        FROM policy_events event
        LEFT JOIN policy_event_source_snapshots snapshot
          ON snapshot.policy_event_id = event.id
        WHERE snapshot.policy_event_id IS NULL
    """,
    "policy_event_source_snapshot_invalid": """
        SELECT COUNT(*)
        FROM policy_events event
        JOIN policy_event_source_snapshots snapshot
          ON snapshot.policy_event_id = event.id
        WHERE snapshot.source_id != event.source_id
           OR snapshot.source_identity_key IS NULL
           OR length(snapshot.source_identity_key) != 64
           OR snapshot.source_identity_key != lower(snapshot.source_identity_key)
           OR snapshot.source_identity_key GLOB '*[^0-9a-f]*'
           OR snapshot.source_title IS NULL
           OR length(trim(snapshot.source_title)) = 0
           OR snapshot.source_institution IS NULL
           OR length(trim(snapshot.source_institution)) = 0
           OR snapshot.source_url IS NULL
           OR length(trim(snapshot.source_url)) = 0
           OR snapshot.evidence_grade != 'official'
           OR snapshot.source_document_type != 'official_notice'
           OR snapshot.source_content_sha256 IS NOT event.source_content_sha256
           OR snapshot.applicable_year IS NOT event.effective_year
           OR snapshot.trace_id IS NOT event.trace_id
    """,
    "policy_event_source_snapshot_drift": """
        SELECT COUNT(*)
        FROM policy_event_source_snapshots snapshot
        LEFT JOIN evidence_sources source ON source.id = snapshot.source_id
        WHERE source.id IS NULL
           OR source.identity_key IS NOT snapshot.source_identity_key
           OR source.title IS NOT snapshot.source_title
           OR source.institution IS NOT snapshot.source_institution
           OR source.url IS NOT snapshot.source_url
           OR source.evidence_grade IS NOT snapshot.evidence_grade
           OR source.document_type IS NOT snapshot.source_document_type
           OR source.content_sha256 IS NOT snapshot.source_content_sha256
           OR source.applicable_year IS NOT snapshot.applicable_year
           OR source.published_date IS NOT snapshot.published_date
           OR source.retrieved_date IS NOT snapshot.retrieved_date
    """,
    "policy_event_year_mismatch": """
        SELECT COUNT(*)
        FROM policy_events event
        LEFT JOIN evidence_sources source ON source.id = event.source_id
        WHERE source.id IS NULL OR source.applicable_year != event.effective_year
    """,
    "policy_event_binding_mismatch": """
        SELECT COUNT(*)
        FROM policy_events event
        JOIN projects project ON project.id = event.project_id
        WHERE event.project_id IS NOT NULL
          AND project.school_id != event.school_id
    """,
    "policy_event_invalid_supersession": """
        SELECT COUNT(*)
        FROM policy_events event
        LEFT JOIN policy_events previous ON previous.id = event.supersedes_event_id
        WHERE event.supersedes_event_id IS NOT NULL
          AND (
              previous.id IS NULL
              OR previous.school_id != event.school_id
              OR previous.project_id IS NOT event.project_id
              OR previous.effective_year != event.effective_year
              OR previous.event_type != event.event_type
          )
    """,
    "policy_event_status_source_mismatch": """
        SELECT COUNT(*)
        FROM policy_events event
        WHERE event.event_type != 'subject_adjustment_notice'
           OR event.event_status != 'pending_directory'
    """,
}

_RESOLVED_CATALOG_DOCTOR_ERROR_QUERIES = {
    "resolved_catalog_subject_without_verification": """
        SELECT COUNT(*)
        FROM v_catalog_evidence_resolved catalog
        WHERE (
            catalog.subject_politics_code IS NOT NULL
            OR catalog.subject_english_code IS NOT NULL
            OR catalog.subject_math_code IS NOT NULL
            OR catalog.subject_professional_code IS NOT NULL
        )
          AND NOT EXISTS (
              SELECT 1
              FROM subject_verifications verification
              WHERE verification.observation_id = catalog.observation_id
          )
    """,
    "resolved_catalog_location_without_unique_fact": """
        SELECT COUNT(*)
        FROM v_catalog_evidence_resolved catalog
        WHERE (
            catalog.campus IS NOT NULL
            AND 1 != (
                SELECT COUNT(*)
                FROM v_current_fact_resolutions resolution
                WHERE resolution.observation_id = catalog.observation_id
                  AND resolution.fact_key = 'training.campus'
                  AND resolution.resolution_action = 'accept'
            )
        ) OR (
            catalog.training_location IS NOT NULL
            AND 1 != (
                SELECT COUNT(*)
                FROM v_current_fact_resolutions resolution
                WHERE resolution.observation_id = catalog.observation_id
                  AND resolution.fact_key = 'training.city'
                  AND resolution.resolution_action = 'accept'
            )
        )
    """,
    "resolved_catalog_numeric_without_unique_fact": """
        WITH exposed AS (
            SELECT observation_id, 'quota.general_effective' AS fact_key
            FROM v_catalog_evidence_resolved
            WHERE effective_general_exam_quota IS NOT NULL
            UNION ALL
            SELECT observation_id, 'retest.cutoff_total'
            FROM v_catalog_evidence_resolved WHERE retest_cutoff IS NOT NULL
            UNION ALL
            SELECT observation_id, 'retest.entered_count'
            FROM v_catalog_evidence_resolved WHERE retest_count IS NOT NULL
            UNION ALL
            SELECT observation_id, 'admission.general_count'
            FROM v_catalog_evidence_resolved WHERE general_exam_admit_count IS NOT NULL
            UNION ALL
            SELECT observation_id, 'score.initial.min'
            FROM v_catalog_evidence_resolved WHERE admit_initial_min IS NOT NULL
            UNION ALL
            SELECT observation_id, 'score.initial.median'
            FROM v_catalog_evidence_resolved WHERE admit_initial_median IS NOT NULL
            UNION ALL
            SELECT observation_id, 'score.initial.mean'
            FROM v_catalog_evidence_resolved WHERE admit_initial_mean IS NOT NULL
            UNION ALL
            SELECT observation_id, 'weight.initial'
            FROM v_catalog_evidence_resolved WHERE initial_exam_weight IS NOT NULL
            UNION ALL
            SELECT observation_id, 'weight.retest'
            FROM v_catalog_evidence_resolved WHERE retest_weight IS NOT NULL
            UNION ALL
            SELECT observation_id, 'weight.machine'
            FROM v_catalog_evidence_resolved WHERE machine_test_weight IS NOT NULL
            UNION ALL
            SELECT observation_id, 'machine.elimination_line'
            FROM v_catalog_evidence_resolved
            WHERE machine_test_elimination_line IS NOT NULL
            UNION ALL
            SELECT observation_id, 'tuition.amount'
            FROM v_catalog_evidence_resolved WHERE tuition_per_year IS NOT NULL
            UNION ALL
            SELECT observation_id, 'study.duration_months'
            FROM v_catalog_evidence_resolved WHERE study_length_years IS NOT NULL
            UNION ALL
            SELECT observation_id, 'first_choice.protection'
            FROM v_catalog_evidence_resolved WHERE first_choice_protection IS NOT NULL
        )
        SELECT COUNT(*)
        FROM exposed
        WHERE 1 != (
            SELECT COUNT(*)
            FROM v_current_fact_resolutions resolution
            WHERE resolution.observation_id = exposed.observation_id
              AND resolution.fact_key = exposed.fact_key
              AND resolution.resolution_action = 'accept'
        )
    """,
}

_SOURCE_METADATA_CORRECTION_DOCTOR_ERROR_QUERIES = {
    # SQLite does not provide SHA-256.  The metrics helper replaces this
    # placeholder with a Python-side recomputation over the canonical payload.
    "evidence_source_correction_fingerprint_mismatch": "SELECT 0",
    "evidence_source_correction_missing_trace": """
        SELECT COUNT(*)
        FROM evidence_source_metadata_corrections correction
        WHERE correction.trace_id IS NULL
           OR length(trim(correction.trace_id)) = 0
    """,
    "evidence_source_correction_missing_audit": """
        SELECT COUNT(*)
        FROM evidence_source_metadata_corrections correction
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = correction.trace_id
              AND audit.event_type = 'evidence_source_metadata_corrected'
              AND audit.entity_type = 'evidence_source_metadata_correction'
              AND audit.entity_id = CAST(correction.id AS TEXT)
        )
    """,
    "evidence_source_correction_duplicate_audit": """
        SELECT COUNT(*)
        FROM evidence_source_metadata_corrections correction
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = correction.trace_id
              AND audit.event_type = 'evidence_source_metadata_corrected'
              AND audit.entity_type = 'evidence_source_metadata_correction'
              AND audit.entity_id = CAST(correction.id AS TEXT)
        )
    """,
    "evidence_source_correction_audit_invalid": """
        SELECT COUNT(*)
        FROM evidence_source_metadata_corrections correction
        JOIN audit_events audit
          ON audit.event_type = 'evidence_source_metadata_corrected'
         AND audit.entity_type = 'evidence_source_metadata_correction'
         AND audit.entity_id = CAST(correction.id AS TEXT)
        WHERE audit.trace_id IS NOT correction.trace_id
           OR audit.created_at IS NOT correction.created_at
           OR CASE
                WHEN json_valid(audit.payload_json) = 0 THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.correction_fingerprint'
                ) IS NOT correction.correction_fingerprint THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.source_id'
                ) IS NOT correction.source_id THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.source_content_sha256'
                ) IS NOT correction.source_content_sha256 THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.field_name'
                ) IS NOT correction.field_name THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.prior_effective_value'
                ) IS NOT correction.prior_effective_value THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.corrected_value'
                ) IS NOT correction.corrected_value THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.supersedes_correction_id'
                ) IS NOT correction.supersedes_correction_id THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.basis_url'
                ) IS NOT correction.basis_url THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.basis_content_sha256'
                ) IS NOT correction.basis_content_sha256 THEN 1
                WHEN json_extract(
                    audit.payload_json, '$.basis_retrieved_date'
                ) IS NOT correction.basis_retrieved_date THEN 1
                ELSE 0
              END = 1
    """,
    "evidence_source_correction_metadata_invalid": """
        SELECT COUNT(*)
        FROM evidence_source_metadata_corrections correction
        LEFT JOIN evidence_sources source ON source.id = correction.source_id
        WHERE source.id IS NULL
           OR source.content_sha256 IS NOT correction.source_content_sha256
           OR length(correction.correction_fingerprint) != 64
           OR correction.correction_fingerprint != lower(
                correction.correction_fingerprint
           )
           OR correction.correction_fingerprint GLOB '*[^0-9a-f]*'
           OR length(correction.source_content_sha256) != 64
           OR correction.source_content_sha256 != lower(
                correction.source_content_sha256
           )
           OR correction.source_content_sha256 GLOB '*[^0-9a-f]*'
           OR correction.field_name NOT IN ('published_date', 'source_note')
           OR length(trim(correction.corrected_value)) = 0
           OR correction.corrected_value IS correction.prior_effective_value
           OR correction.basis_url NOT LIKE 'https://%'
           OR length(correction.basis_content_sha256) != 64
           OR correction.basis_content_sha256 != lower(correction.basis_content_sha256)
           OR correction.basis_content_sha256 GLOB '*[^0-9a-f]*'
           OR date(correction.basis_retrieved_date) IS NOT correction.basis_retrieved_date
           OR length(trim(correction.reason)) = 0
           OR datetime(correction.created_at) IS NULL
           OR (
                correction.field_name = 'published_date'
                AND date(correction.corrected_value) IS NOT correction.corrected_value
           )
    """,
    "evidence_source_correction_chain_invalid": """
        WITH RECURSIVE
        roots AS (
            SELECT correction.id, correction.source_id, correction.field_name
            FROM evidence_source_metadata_corrections correction
            WHERE correction.supersedes_correction_id IS NULL
        ),
        reachable(id, source_id, field_name) AS (
            SELECT id, source_id, field_name FROM roots
            UNION
            SELECT child.id, child.source_id, child.field_name
            FROM evidence_source_metadata_corrections child
            JOIN reachable parent
              ON child.supersedes_correction_id = parent.id
             AND child.source_id = parent.source_id
             AND child.field_name = parent.field_name
        ),
        row_errors AS (
            SELECT correction.id
            FROM evidence_source_metadata_corrections correction
            JOIN evidence_sources source ON source.id = correction.source_id
            WHERE (
                correction.supersedes_correction_id IS NULL
                AND correction.prior_effective_value IS NOT
                    CASE correction.field_name
                        WHEN 'published_date' THEN source.published_date
                        WHEN 'source_note' THEN source.source_note
                    END
            ) OR (
                correction.supersedes_correction_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM evidence_source_metadata_corrections predecessor
                    WHERE predecessor.id = correction.supersedes_correction_id
                      AND predecessor.source_id = correction.source_id
                      AND predecessor.field_name = correction.field_name
                      AND predecessor.source_content_sha256 =
                          correction.source_content_sha256
                      AND predecessor.corrected_value IS
                          correction.prior_effective_value
                )
            )
        ),
        group_errors AS (
            SELECT correction.source_id, correction.field_name
            FROM evidence_source_metadata_corrections correction
            GROUP BY correction.source_id, correction.field_name
            HAVING SUM(correction.supersedes_correction_id IS NULL) != 1
                OR SUM(NOT EXISTS (
                    SELECT 1
                    FROM evidence_source_metadata_corrections successor
                    WHERE successor.supersedes_correction_id = correction.id
                )) != 1
        )
        SELECT
            (SELECT COUNT(*) FROM row_errors)
            + (SELECT COUNT(*) FROM group_errors)
            + (
                SELECT COUNT(*)
                FROM evidence_source_metadata_corrections correction
                WHERE NOT EXISTS (
                    SELECT 1 FROM reachable WHERE reachable.id = correction.id
                )
            )
    """,
    "evidence_source_correction_effective_mismatch": """
        WITH expected AS (
            SELECT
                source.*,
                published_date.id AS published_date_correction_id,
                published_date.correction_fingerprint
                    AS published_date_correction_fingerprint,
                published_date.source_content_sha256
                    AS published_date_correction_source_content_sha256,
                published_date.prior_effective_value
                    AS published_date_prior_effective_value,
                published_date.supersedes_correction_id
                    AS published_date_supersedes_correction_id,
                published_date.basis_url
                    AS published_date_correction_basis_url,
                published_date.basis_content_sha256
                    AS published_date_correction_basis_content_sha256,
                published_date.basis_retrieved_date
                    AS published_date_correction_basis_retrieved_date,
                published_date.reason AS published_date_correction_reason,
                published_date.trace_id AS published_date_correction_trace_id,
                published_date.created_at
                    AS published_date_correction_created_at,
                source_note.id AS source_note_correction_id,
                source_note.correction_fingerprint
                    AS source_note_correction_fingerprint,
                source_note.source_content_sha256
                    AS source_note_correction_source_content_sha256,
                source_note.prior_effective_value
                    AS source_note_prior_effective_value,
                source_note.supersedes_correction_id
                    AS source_note_supersedes_correction_id,
                source_note.basis_url AS source_note_correction_basis_url,
                source_note.basis_content_sha256
                    AS source_note_correction_basis_content_sha256,
                source_note.basis_retrieved_date
                    AS source_note_correction_basis_retrieved_date,
                source_note.reason AS source_note_correction_reason,
                source_note.trace_id AS source_note_correction_trace_id,
                source_note.created_at AS source_note_correction_created_at,
                COALESCE(published_date.corrected_value, source.published_date)
                    AS expected_published_date,
                COALESCE(source_note.corrected_value, source.source_note)
                    AS expected_source_note
            FROM evidence_sources source
            LEFT JOIN v_current_evidence_source_metadata_corrections published_date
              ON published_date.source_id = source.id
             AND published_date.field_name = 'published_date'
            LEFT JOIN v_current_evidence_source_metadata_corrections source_note
              ON source_note.source_id = source.id
             AND source_note.field_name = 'source_note'
        )
        SELECT
            abs(
                (SELECT COUNT(*) FROM v_evidence_sources_effective)
                - (SELECT COUNT(*) FROM evidence_sources)
            )
            + COUNT(*)
        FROM expected
        LEFT JOIN v_evidence_sources_effective effective
          ON effective.id = expected.id
        WHERE effective.id IS NULL
           OR effective.original_published_date IS NOT expected.published_date
           OR effective.effective_published_date IS NOT expected.expected_published_date
           OR effective.published_date IS NOT expected.expected_published_date
           OR effective.original_source_note IS NOT expected.source_note
           OR effective.effective_source_note IS NOT expected.expected_source_note
           OR effective.source_note IS NOT expected.expected_source_note
           OR effective.published_date_correction_id IS NOT
                expected.published_date_correction_id
           OR effective.published_date_correction_fingerprint IS NOT
                expected.published_date_correction_fingerprint
           OR effective.published_date_correction_source_content_sha256 IS NOT
                expected.published_date_correction_source_content_sha256
           OR effective.published_date_prior_effective_value IS NOT
                expected.published_date_prior_effective_value
           OR effective.published_date_supersedes_correction_id IS NOT
                expected.published_date_supersedes_correction_id
           OR effective.published_date_correction_basis_url IS NOT
                expected.published_date_correction_basis_url
           OR effective.published_date_correction_basis_content_sha256 IS NOT
                expected.published_date_correction_basis_content_sha256
           OR effective.published_date_correction_basis_retrieved_date IS NOT
                expected.published_date_correction_basis_retrieved_date
           OR effective.published_date_correction_reason IS NOT
                expected.published_date_correction_reason
           OR effective.published_date_correction_trace_id IS NOT
                expected.published_date_correction_trace_id
           OR effective.published_date_correction_created_at IS NOT
                expected.published_date_correction_created_at
           OR effective.source_note_correction_id IS NOT
                expected.source_note_correction_id
           OR effective.source_note_correction_fingerprint IS NOT
                expected.source_note_correction_fingerprint
           OR effective.source_note_correction_source_content_sha256 IS NOT
                expected.source_note_correction_source_content_sha256
           OR effective.source_note_prior_effective_value IS NOT
                expected.source_note_prior_effective_value
           OR effective.source_note_supersedes_correction_id IS NOT
                expected.source_note_supersedes_correction_id
           OR effective.source_note_correction_basis_url IS NOT
                expected.source_note_correction_basis_url
           OR effective.source_note_correction_basis_content_sha256 IS NOT
                expected.source_note_correction_basis_content_sha256
           OR effective.source_note_correction_basis_retrieved_date IS NOT
                expected.source_note_correction_basis_retrieved_date
           OR effective.source_note_correction_reason IS NOT
                expected.source_note_correction_reason
           OR effective.source_note_correction_trace_id IS NOT
                expected.source_note_correction_trace_id
           OR effective.source_note_correction_created_at IS NOT
                expected.source_note_correction_created_at
    """,
    "evidence_source_correction_required_backfill_missing": """
        WITH required(
            identity_key,
            source_content_sha256,
            field_name,
            prior_effective_value,
            corrected_value,
            correction_fingerprint
        ) AS (
            VALUES
            (
                'a0f610b3532fa8f89f52bed5bcef29b4080e37deaf7209296e9667211f55e449',
                '92cbb1ec97347292ad9dddf77a3a4aac98900274b47cad439ad59dc34bb64c7c',
                'published_date',
                '2025-10-15',
                '2025-09-30',
                'e93839bf2b6490c9af24002a610c2ce353560ca4473a86e525dae1c2f0c3ef5d'
            ),
            (
                '73b98d3fce8726d8a900c1d3bf8a8a7df68f3fa8a9235beee6a8af84bc78c47b',
                '92cbb1ec97347292ad9dddf77a3a4aac98900274b47cad439ad59dc34bb64c7c',
                'published_date',
                '2025-10-15',
                '2025-09-30',
                '9aac0cf9b5d78711c6246477a99160fac4bbedd0706728ee8f9f26413df1b7a3'
            ),
            (
                'dbced694ad90eb3d222d472351c2f2853abeefaedfd55bec8e8329efe483b02e',
                'a923c330057d4478aae158aae27cf190e07ae7232988e46d9567909364918957',
                'source_note',
                '逐行剔除调剂、非全和专项；本项目名单均为一志愿全日制非定向。',
                '该原件仅能证明名单列示的专业代码、一志愿、全日制和非定向属性；名单无专项计划列，不能据此排除专项。各项目行数须在项目级事实中记录。',
                'd8f216e8296c429ed91830e31763691c94ecb61d5edeee56be829384ad1cdb92'
            )
        )
        SELECT COUNT(*)
        FROM required
        JOIN evidence_sources source
          ON source.identity_key = required.identity_key
         AND source.content_sha256 = required.source_content_sha256
        WHERE CASE required.field_name
                WHEN 'published_date' THEN source.published_date
                WHEN 'source_note' THEN source.source_note
              END IS NOT required.prior_effective_value
           OR NOT EXISTS (
                SELECT 1
                FROM evidence_source_metadata_corrections correction
                WHERE correction.source_id = source.id
                  AND correction.source_content_sha256 =
                      required.source_content_sha256
                  AND correction.field_name = required.field_name
                  AND correction.prior_effective_value IS
                      required.prior_effective_value
                  AND correction.corrected_value = required.corrected_value
                  AND correction.correction_fingerprint =
                      required.correction_fingerprint
                  AND correction.supersedes_correction_id IS NULL
           )
    """,
    "evidence_source_correction_protection_missing": """
        WITH required(type, name) AS (
            VALUES
                ('table', 'evidence_source_metadata_corrections'),
                ('index', 'ux_evidence_source_metadata_corrections_root'),
                ('index', 'ux_evidence_source_metadata_corrections_successor'),
                ('index', 'ux_audit_evidence_source_metadata_correction_event'),
                ('trigger', 'evidence_source_metadata_corrections_validate_insert'),
                ('trigger', 'evidence_source_metadata_corrections_audit_insert'),
                ('trigger', 'protect_evidence_source_metadata_corrections_update'),
                ('trigger', 'protect_evidence_source_metadata_corrections_delete'),
                ('trigger', 'protect_evidence_sources_material_update'),
                ('trigger', 'protect_evidence_sources_delete'),
                ('view', 'v_current_evidence_source_metadata_corrections'),
                ('view', 'v_evidence_sources_effective')
        )
        SELECT COUNT(*)
        FROM required
        WHERE NOT EXISTS (
            SELECT 1
            FROM sqlite_master object
            WHERE object.type = required.type
              AND object.name = required.name
        )
    """,
}

_ACHIEVEMENT_DOCTOR_ERROR_QUERIES = {
    "applicant_evidence_missing_trace": """
        SELECT COUNT(*)
        FROM applicant_evidence_documents document
        WHERE document.trace_id IS NULL OR length(trim(document.trace_id)) = 0
    """,
    "applicant_evidence_missing_audit": """
        SELECT COUNT(*)
        FROM applicant_evidence_documents document
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = document.trace_id
              AND audit.event_type = 'applicant_evidence_document_added'
              AND audit.entity_type = 'applicant_evidence_document'
              AND audit.entity_id = CAST(document.id AS TEXT)
        )
    """,
    "applicant_evidence_duplicate_audit": """
        SELECT COUNT(*)
        FROM applicant_evidence_documents document
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = document.trace_id
              AND audit.event_type = 'applicant_evidence_document_added'
              AND audit.entity_type = 'applicant_evidence_document'
              AND audit.entity_id = CAST(document.id AS TEXT)
        )
    """,
    "applicant_evidence_metadata_invalid": """
        SELECT COUNT(*)
        FROM applicant_evidence_documents document
        WHERE length(document.source_content_sha256) != 64
           OR document.source_content_sha256 != lower(document.source_content_sha256)
           OR document.source_content_sha256 GLOB '*[^0-9a-f]*'
           OR document.source_file_size_bytes <= 0
           OR date(document.source_reviewed_on) < date(document.source_retrieved_on)
           OR (
               document.source_access_scope = 'local_user_file'
               AND document.source_url NOT LIKE 'file:///%'
           )
           OR (
               document.source_access_scope != 'local_user_file'
               AND document.source_url NOT LIKE 'https://%'
           )
           OR (
               document.evidence_status = 'document_visual_confirmed'
               AND document.review_method NOT IN (
                   'full_document_visual_review', 'combined_visual_and_text'
               )
           )
           OR (
               document.evidence_grade = 'official_online_verification'
               AND document.source_access_scope != 'public_web'
           )
    """,
    "applicant_evidence_orphan": """
        SELECT COUNT(*)
        FROM applicant_evidence_documents document
        WHERE NOT EXISTS (
            SELECT 1
            FROM applicant_achievement_evidence_links link
            WHERE link.evidence_document_id = document.id
        )
    """,
    "applicant_achievement_missing_trace": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE event.trace_id IS NULL OR length(trim(event.trace_id)) = 0
    """,
    "applicant_achievement_missing_fingerprint": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE length(event.event_fingerprint) != 64
           OR event.event_fingerprint != lower(event.event_fingerprint)
           OR event.event_fingerprint GLOB '*[^0-9a-f]*'
    """,
    "applicant_achievement_missing_audit": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = event.trace_id
              AND audit.event_type = 'applicant_achievement_event_added'
              AND audit.entity_type = 'applicant_achievement_event'
              AND audit.entity_id = CAST(event.id AS TEXT)
        )
    """,
    "applicant_achievement_duplicate_audit": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = event.trace_id
              AND audit.event_type = 'applicant_achievement_event_added'
              AND audit.entity_type = 'applicant_achievement_event'
              AND audit.entity_id = CAST(event.id AS TEXT)
        )
    """,
    "applicant_achievement_without_support": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE NOT EXISTS (
            SELECT 1
            FROM applicant_achievement_evidence_links link
            WHERE link.achievement_event_id = event.id
              AND link.relationship = 'supports'
        )
    """,
    "applicant_achievement_document_confirmed_without_visual_support": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE event.verification_status = 'document_confirmed'
          AND NOT EXISTS (
              SELECT 1
              FROM applicant_achievement_evidence_links link
              JOIN applicant_achievement_evidence_review_links review_link
                ON review_link.achievement_evidence_link_id = link.id
              JOIN applicant_evidence_review_events review
                ON review.id = review_link.evidence_review_event_id
              WHERE link.achievement_event_id = event.id
                AND link.relationship = 'supports'
                AND review.evidence_status = 'document_visual_confirmed'
                AND review.review_method IN (
                    'full_document_visual_review', 'combined_visual_and_text'
                )
                AND review.evidence_grade = 'primary_document_user_copy'
          )
    """,
    "applicant_achievement_confirmed_with_contradiction": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE event.verification_status = 'document_confirmed'
          AND EXISTS (
              SELECT 1
              FROM applicant_achievement_evidence_links link
              JOIN applicant_achievement_evidence_review_links review_link
                ON review_link.achievement_evidence_link_id = link.id
              JOIN applicant_evidence_review_events review
                ON review.id = review_link.evidence_review_event_id
              WHERE link.achievement_event_id = event.id
                AND (
                    link.relationship = 'contradicts'
                    OR review.evidence_status = 'conflict'
                )
          )
    """,
    "applicant_achievement_invalid_fingerprint_version": """
        SELECT COUNT(*)
        FROM applicant_achievement_events event
        WHERE event.fingerprint_version IS NULL
           OR event.fingerprint_version NOT IN ('v1', 'v2')
    """,
    "applicant_achievement_link_missing_trace": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_links link
        WHERE link.trace_id IS NULL OR length(trim(link.trace_id)) = 0
    """,
    "applicant_achievement_link_missing_audit": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_links link
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = link.trace_id
              AND audit.event_type = 'applicant_achievement_evidence_link_added'
              AND audit.entity_type = 'applicant_achievement_evidence_link'
              AND audit.entity_id = CAST(link.id AS TEXT)
        )
    """,
    "applicant_achievement_link_duplicate_audit": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_links link
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = link.trace_id
              AND audit.event_type = 'applicant_achievement_evidence_link_added'
              AND audit.entity_type = 'applicant_achievement_evidence_link'
              AND audit.entity_id = CAST(link.id AS TEXT)
        )
    """,
    "applicant_achievement_link_profile_mismatch": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_links link
        JOIN applicant_achievement_events event
          ON event.id = link.achievement_event_id
        JOIN applicant_evidence_documents document
          ON document.id = link.evidence_document_id
        WHERE event.profile_id != document.profile_id
    """,
    "applicant_evidence_review_missing_trace": """
        SELECT COUNT(*)
        FROM applicant_evidence_review_events review
        WHERE review.trace_id IS NULL OR length(trim(review.trace_id)) = 0
    """,
    "applicant_evidence_review_missing_audit": """
        SELECT COUNT(*)
        FROM applicant_evidence_review_events review
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = review.trace_id
              AND audit.event_type IN (
                  'applicant_evidence_review_added',
                  'applicant_evidence_review_event_backfilled'
              )
              AND audit.entity_type = 'applicant_evidence_review_event'
              AND audit.entity_id = CAST(review.id AS TEXT)
        )
    """,
    "applicant_evidence_review_duplicate_audit": """
        SELECT COUNT(*)
        FROM applicant_evidence_review_events review
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = review.trace_id
              AND audit.event_type IN (
                  'applicant_evidence_review_added',
                  'applicant_evidence_review_event_backfilled'
              )
              AND audit.entity_type = 'applicant_evidence_review_event'
              AND audit.entity_id = CAST(review.id AS TEXT)
        )
    """,
    "applicant_evidence_review_invalid": """
        SELECT COUNT(*)
        FROM applicant_evidence_review_events review
        JOIN applicant_evidence_documents document
          ON document.id = review.evidence_document_id
        WHERE length(review.review_fingerprint) != 64
           OR review.review_fingerprint != lower(review.review_fingerprint)
           OR review.review_fingerprint GLOB '*[^0-9a-f]*'
           OR date(review.source_reviewed_on) < date(document.source_retrieved_on)
           OR (
               review.evidence_status = 'document_visual_confirmed'
               AND (
                   review.review_method NOT IN (
                       'full_document_visual_review',
                       'combined_visual_and_text'
                   )
                   OR review.evidence_grade != 'primary_document_user_copy'
               )
           )
    """,
    "applicant_evidence_official_online_verification_unsupported": """
        SELECT COUNT(*)
        FROM applicant_evidence_review_events review
        WHERE review.evidence_grade = 'official_online_verification'
    """,
    "applicant_evidence_review_orphan": """
        SELECT COUNT(*)
        FROM applicant_evidence_review_events review
        WHERE NOT EXISTS (
            SELECT 1
            FROM applicant_achievement_evidence_review_links review_link
            WHERE review_link.evidence_review_event_id = review.id
        )
    """,
    "applicant_achievement_review_link_missing": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_links link
        WHERE NOT EXISTS (
            SELECT 1
            FROM applicant_achievement_evidence_review_links review_link
            WHERE review_link.achievement_evidence_link_id = link.id
        )
    """,
    "applicant_achievement_review_link_missing_trace": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_review_links review_link
        WHERE review_link.trace_id IS NULL
           OR length(trim(review_link.trace_id)) = 0
    """,
    "applicant_achievement_review_link_missing_audit": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_review_links review_link
        WHERE NOT EXISTS (
            SELECT 1
            FROM audit_events audit
            WHERE audit.trace_id = review_link.trace_id
              AND audit.event_type IN (
                  'applicant_achievement_evidence_review_link_added',
                  'applicant_achievement_evidence_review_link_backfilled'
              )
              AND audit.entity_type = 'applicant_achievement_evidence_review_link'
              AND audit.entity_id = CAST(review_link.id AS TEXT)
        )
    """,
    "applicant_achievement_review_link_duplicate_audit": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_review_links review_link
        WHERE 1 < (
            SELECT COUNT(*)
            FROM audit_events audit
            WHERE audit.trace_id = review_link.trace_id
              AND audit.event_type IN (
                  'applicant_achievement_evidence_review_link_added',
                  'applicant_achievement_evidence_review_link_backfilled'
              )
              AND audit.entity_type = 'applicant_achievement_evidence_review_link'
              AND audit.entity_id = CAST(review_link.id AS TEXT)
        )
    """,
    "applicant_achievement_review_document_mismatch": """
        SELECT COUNT(*)
        FROM applicant_achievement_evidence_review_links review_link
        JOIN applicant_achievement_evidence_links achievement_link
          ON achievement_link.id = review_link.achievement_evidence_link_id
        JOIN applicant_evidence_review_events review
          ON review.id = review_link.evidence_review_event_id
        WHERE achievement_link.evidence_document_id != review.evidence_document_id
    """,
}


class SqliteCatalogRepository:
    """SQLite implementation of import and query ports."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def find_successful_batch(
        self,
        source_sha256: str,
        importer_version: str,
    ) -> str | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM import_batches
                WHERE source_sha256 = ?
                  AND importer_version = ?
                  AND status = 'succeeded'
                """,
                (source_sha256, importer_version),
            ).fetchone()
        return str(row["id"]) if row else None

    def start_batch(
        self,
        batch_id: str,
        trace_id: str,
        archive_path: Path,
        source_sha256: str,
        importer_version: str,
    ) -> None:
        now = _utc_now()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO import_batches(
                    id, trace_id, source_name, source_path, source_sha256,
                    importer_version, status, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
                """,
                (
                    batch_id,
                    trace_id,
                    archive_path.name,
                    str(archive_path.resolve()),
                    source_sha256,
                    importer_version,
                    now,
                ),
            )
            _insert_audit_event(
                connection,
                trace_id,
                "import_started",
                "import_batch",
                batch_id,
                {"source_sha256": source_sha256},
            )
            connection.commit()

    def record_duplicate_batch(
        self,
        batch_id: str,
        trace_id: str,
        archive_path: Path,
        source_sha256: str,
        importer_version: str,
        duplicate_of: str,
    ) -> ImportResult:
        now = _utc_now()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO import_batches(
                    id, trace_id, source_name, source_path, source_sha256,
                    importer_version, status, duplicate_of, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'duplicate', ?, ?, ?)
                """,
                (
                    batch_id,
                    trace_id,
                    archive_path.name,
                    str(archive_path.resolve()),
                    source_sha256,
                    importer_version,
                    duplicate_of,
                    now,
                    now,
                ),
            )
            _insert_audit_event(
                connection,
                trace_id,
                "import_duplicate",
                "import_batch",
                batch_id,
                {"duplicate_of": duplicate_of},
            )
            connection.commit()
        return ImportResult(
            batch_id=batch_id,
            status="duplicate",
            source_hash=source_sha256,
            source_files=0,
            raw_rows=0,
            observations=0,
            issues=0,
            ignored_members=0,
            duplicate_of=duplicate_of,
        )

    def persist_import(
        self,
        batch_id: str,
        source_sha256: str,
        archive: CatalogArchive,
        normalized_rows: Mapping[tuple[str, int], NormalizedRow],
    ) -> ImportResult:
        raw_row_count = 0
        observation_count = 0
        issue_count = 0
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                batch = connection.execute(
                    "SELECT trace_id FROM import_batches WHERE id = ? AND status = 'running'",
                    (batch_id,),
                ).fetchone()
                if batch is None:
                    raise RuntimeError(f"running import batch not found: {batch_id}")
                trace_id = str(batch["trace_id"])
                last_source_by_school: dict[str, tuple[str, str, int]] = {}

                for source_file in archive.source_files:
                    source_file_id = self._insert_source_file(
                        connection,
                        batch_id,
                        source_file.archive_member,
                        source_file.content_sha256,
                        source_file.header,
                        len(source_file.rows),
                    )
                    for raw_row in source_file.rows:
                        raw_row_count += 1
                        raw_row_id, row_sha256 = self._insert_raw_row(
                            connection,
                            source_file_id,
                            raw_row,
                        )
                        normalized = normalized_rows[
                            (source_file.archive_member, raw_row.row_number)
                        ]
                        observation_id: int | None = None
                        generated_issues = list(normalized.issues)

                        if normalized.observation is not None:
                            project_id = self._get_or_create_project(
                                connection,
                                normalized.observation,
                            )
                            observation_fingerprint = _observation_fingerprint(
                                normalized.observation.raw_values
                            )
                            existing = connection.execute(
                                """
                                SELECT id FROM project_year_observations
                                WHERE observation_fingerprint = ?
                                """,
                                (observation_fingerprint,),
                            ).fetchone()
                            if existing:
                                observation_id = int(existing["id"])
                                connection.execute(
                                    """
                                    INSERT INTO duplicate_observations(
                                        raw_row_id, canonical_observation_id, reason, created_at
                                    ) VALUES (?, ?, 'identical normalized legacy row', ?)
                                    """,
                                    (raw_row_id, observation_id, _utc_now()),
                                )
                                generated_issues.append(
                                    ValidationIssue(
                                        code="DUPLICATE_OBSERVATION",
                                        severity=_info_severity(),
                                        message="identical observation already exists; raw lineage was retained",
                                    )
                                )
                            else:
                                observation_id = self._insert_observation(
                                    connection,
                                    project_id,
                                    raw_row_id,
                                    observation_fingerprint,
                                    normalized.observation,
                                )
                                observation_count += 1

                            school_key = _canonical_text(normalized.observation.school)
                            source_title = normalized.observation.official_source
                            resolved_from: tuple[str, int] | None = None
                            if source_title == "同上":
                                previous = last_source_by_school.get(school_key)
                                if previous is not None:
                                    source_title, previous_member, previous_row = previous
                                    resolved_from = (previous_member, previous_row)
                            elif source_title:
                                last_source_by_school[school_key] = (
                                    source_title,
                                    source_file.archive_member,
                                    raw_row.row_number,
                                )

                            source_id = self._get_or_create_evidence_source(
                                connection,
                                normalized.observation,
                                source_file.archive_member,
                                raw_row.row_number,
                                source_title,
                                resolved_from,
                            )
                            connection.execute(
                                """
                                INSERT OR IGNORE INTO observation_sources(
                                    observation_id, source_id, relationship
                                ) VALUES (?, ?, 'supports')
                                """,
                                (observation_id, source_id),
                            )
                            self._insert_field_evidence(
                                connection,
                                observation_id,
                                source_id,
                                normalized.observation,
                            )

                        for issue in generated_issues:
                            if self._insert_issue(
                                connection,
                                batch_id,
                                raw_row_id,
                                observation_id,
                                row_sha256,
                                issue,
                            ):
                                issue_count += 1

                completed_at = _utc_now()
                connection.execute(
                    """
                    UPDATE import_batches
                    SET status = 'succeeded', completed_at = ?, source_file_count = ?,
                        raw_row_count = ?, observation_count = ?, issue_count = ?,
                        ignored_member_count = ?
                    WHERE id = ?
                    """,
                    (
                        completed_at,
                        len(archive.source_files),
                        raw_row_count,
                        observation_count,
                        issue_count,
                        len(archive.ignored_members),
                        batch_id,
                    ),
                )
                _insert_audit_event(
                    connection,
                    trace_id,
                    "import_completed",
                    "import_batch",
                    batch_id,
                    {
                        "raw_rows": raw_row_count,
                        "observations": observation_count,
                        "issues": issue_count,
                        "ignored_members": len(archive.ignored_members),
                    },
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return ImportResult(
            batch_id=batch_id,
            status="succeeded",
            source_hash=source_sha256,
            source_files=len(archive.source_files),
            raw_rows=raw_row_count,
            observations=observation_count,
            issues=issue_count,
            ignored_members=len(archive.ignored_members),
        )

    def mark_batch_failed(self, batch_id: str, error_message: str) -> None:
        with self._database.connect() as connection:
            batch = connection.execute(
                "SELECT trace_id FROM import_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            if batch is None:
                return
            connection.execute(
                """
                UPDATE import_batches
                SET status = 'failed', completed_at = ?, error_message = ?
                WHERE id = ? AND status = 'running'
                """,
                (_utc_now(), error_message[:2000], batch_id),
            )
            _insert_audit_event(
                connection,
                str(batch["trace_id"]),
                "import_failed",
                "import_batch",
                batch_id,
                {"error": error_message[:500]},
            )
            connection.commit()

    def summary(self) -> Mapping[str, Any]:
        with self._database.connect() as connection:
            counts = {
                "successful_batches": _scalar(
                    connection,
                    "SELECT COUNT(*) FROM import_batches WHERE status = 'succeeded'",
                ),
                "duplicate_batches": _scalar(
                    connection,
                    "SELECT COUNT(*) FROM import_batches WHERE status = 'duplicate'",
                ),
                "source_files": _scalar(connection, "SELECT COUNT(*) FROM source_files"),
                "raw_rows": _scalar(connection, "SELECT COUNT(*) FROM raw_catalog_rows"),
                "observations": _scalar(
                    connection,
                    "SELECT COUNT(*) FROM project_year_observations",
                ),
                "schools": _scalar(connection, "SELECT COUNT(*) FROM schools"),
                "colleges": _scalar(connection, "SELECT COUNT(*) FROM colleges"),
                "projects": _scalar(connection, "SELECT COUNT(*) FROM projects"),
                "open_issues": _scalar(
                    connection,
                    "SELECT COUNT(*) FROM data_quality_issues WHERE status = 'open'",
                ),
            }
            return {
                "counts": counts,
                "year_distribution": _distribution(
                    connection,
                    "project_year_observations",
                    "admission_year",
                ),
                "strict_claim_distribution": _distribution(
                    connection,
                    "project_year_observations",
                    "strict_22408_claim",
                ),
                "evidence_status_distribution": _distribution(
                    connection,
                    "v_catalog",
                    "strict_22408_status",
                ),
                "imported_evidence_status_distribution": _distribution(
                    connection,
                    "project_year_observations",
                    "strict_22408_evidence_status",
                ),
                "evidence_grade_distribution": _distribution(
                    connection,
                    "project_year_observations",
                    "evidence_grade",
                ),
                "issue_severity_distribution": _distribution(
                    connection,
                    "data_quality_issues",
                    "severity",
                    "status = 'open'",
                ),
            }

    def list_catalog(self, catalog_filter: CatalogFilter) -> Sequence[Mapping[str, Any]]:
        conditions = ["1 = 1"]
        parameters: list[Any] = []
        if catalog_filter.admission_year is not None:
            conditions.append("admission_year = ?")
            parameters.append(catalog_filter.admission_year)
        if catalog_filter.strict_status is not None:
            conditions.append("strict_22408_status = ?")
            parameters.append(catalog_filter.strict_status.value)
        if catalog_filter.school_keyword:
            conditions.append("school LIKE ? ESCAPE '\\'")
            escaped_keyword = (
                catalog_filter.school_keyword.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            parameters.append(f"%{escaped_keyword}%")
        parameters.append(catalog_filter.limit)
        catalog_view = (
            "v_catalog" if catalog_filter.raw_imported else "v_catalog_evidence_resolved"
        )
        sql = f"""
            SELECT *
            FROM {catalog_view}
            WHERE {' AND '.join(conditions)}
            ORDER BY school, college, admission_year, program_code, direction,
                     training_location, observation_id
            LIMIT ?
        """
        with self._database.connect() as connection:
            projection_mode = (
                "raw_imported" if catalog_filter.raw_imported else "evidence_resolved"
            )
            return tuple(
                {**dict(row), "projection_mode": projection_mode}
                for row in connection.execute(sql, parameters)
            )

    def list_issues(
        self,
        severity: str | None,
        status: str,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        conditions = ["q.status = ?"]
        parameters: list[Any] = [status]
        if severity:
            conditions.append("q.severity = ?")
            parameters.append(severity)
        parameters.append(limit)
        sql = f"""
            SELECT q.id, q.issue_code, q.severity, q.field_name, q.raw_value,
                   q.message, q.status, q.batch_id, q.observation_id,
                   sf.archive_member, r.source_row_number
            FROM data_quality_issues q
            LEFT JOIN raw_catalog_rows r ON r.id = q.raw_row_id
            LEFT JOIN source_files sf ON sf.id = r.source_file_id
            WHERE {' AND '.join(conditions)}
            ORDER BY CASE q.severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                     q.issue_code, sf.archive_member, r.source_row_number, q.id
            LIMIT ?
        """
        with self._database.connect() as connection:
            return tuple(dict(row) for row in connection.execute(sql, parameters))

    def doctor(self) -> Mapping[str, Any]:
        with self._database.connect() as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_violations = [
                tuple(row) for row in connection.execute("PRAGMA foreign_key_check")
            ]
            missing_lineage = _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM project_year_observations o
                LEFT JOIN raw_catalog_rows r ON r.id = o.raw_row_id
                LEFT JOIN projects p ON p.id = o.project_id
                WHERE r.id IS NULL OR p.id IS NULL
                """,
            )
            running_batches = _scalar(
                connection,
                "SELECT COUNT(*) FROM import_batches WHERE status = 'running'",
            )
            preference_missing_audit = _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM applicant_preference_events preference
                LEFT JOIN audit_events audit
                  ON audit.trace_id = preference.trace_id
                 AND audit.event_type = 'preference_event_added'
                 AND audit.entity_type = 'applicant_preference_event'
                 AND audit.entity_id = CAST(preference.id AS TEXT)
                WHERE audit.id IS NULL
                """,
            )
            context_missing_audit = _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM applicant_context_events context
                LEFT JOIN audit_events audit
                  ON audit.trace_id = context.trace_id
                 AND audit.event_type = 'applicant_context_event_added'
                 AND audit.entity_type = 'applicant_context_event'
                 AND audit.entity_id = CAST(context.id AS TEXT)
                WHERE audit.id IS NULL
                """,
            )
            fairness_review_missing_audit = _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM candidate_fairness_reviews review
                LEFT JOIN audit_events audit
                  ON audit.trace_id = review.trace_id
                 AND audit.event_type = 'candidate_fairness_review_added'
                 AND audit.entity_type = 'candidate_fairness_review'
                 AND audit.entity_id = CAST(review.id AS TEXT)
                WHERE audit.id IS NULL
                """,
            )
            machine_test_missing_audit = _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM machine_test_sessions session
                LEFT JOIN audit_events audit
                  ON audit.trace_id = session.trace_id
                 AND audit.event_type = 'machine_test_added'
                 AND audit.entity_type = 'machine_test_session'
                 AND audit.entity_id = CAST(session.id AS TEXT)
                WHERE audit.id IS NULL
                """,
            )
            mock_exam_checks = _mock_exam_doctor_metrics(connection)
            policy_event_checks = _policy_event_doctor_metrics(connection)
            resolved_catalog_checks = _resolved_catalog_doctor_metrics(connection)
            statistical_fact_checks = _statistical_fact_doctor_metrics(connection)
            source_metadata_correction_checks = (
                _source_metadata_correction_doctor_metrics(connection)
            )
            achievement_checks = _achievement_doctor_metrics(connection)
            candidate_model_checks = candidate_model_doctor_metrics(connection)
            applied_migrations = [
                dict(row)
                for row in connection.execute(
                    "SELECT version, filename, checksum, applied_at FROM schema_migrations ORDER BY version"
                )
            ]
        ok = (
            integrity == "ok"
            and not foreign_key_violations
            and missing_lineage == 0
            and running_batches == 0
            and preference_missing_audit == 0
            and context_missing_audit == 0
            and fairness_review_missing_audit == 0
            and machine_test_missing_audit == 0
            and all(
                mock_exam_checks[name] == 0
                for name in _MOCK_EXAM_DOCTOR_ERROR_QUERIES
            )
            and all(
                policy_event_checks[name] == 0
                for name in _POLICY_EVENT_DOCTOR_ERROR_QUERIES
            )
            and all(
                resolved_catalog_checks[name] == 0
                for name in _RESOLVED_CATALOG_DOCTOR_ERROR_QUERIES
            )
            and all(
                statistical_fact_checks[name] == 0
                for name in _STATISTICAL_FACT_DOCTOR_ERROR_QUERIES
            )
            and all(
                source_metadata_correction_checks[name] == 0
                for name in _SOURCE_METADATA_CORRECTION_DOCTOR_ERROR_QUERIES
            )
            and all(
                achievement_checks[name] == 0
                for name in _ACHIEVEMENT_DOCTOR_ERROR_QUERIES
            )
            and all(
                candidate_model_checks[name] == 0
                for name in CANDIDATE_MODEL_DOCTOR_METRICS
            )
        )
        return {
            "status": "ok" if ok else "error",
            "integrity_check": integrity,
            "foreign_key_violations": foreign_key_violations,
            "missing_lineage": missing_lineage,
            "running_batches": running_batches,
            "preference_missing_audit": preference_missing_audit,
            "context_missing_audit": context_missing_audit,
            "fairness_review_missing_audit": fairness_review_missing_audit,
            "machine_test_missing_audit": machine_test_missing_audit,
            **mock_exam_checks,
            **policy_event_checks,
            **resolved_catalog_checks,
            **statistical_fact_checks,
            **source_metadata_correction_checks,
            **achievement_checks,
            **candidate_model_checks,
            "applied_migrations": applied_migrations,
        }

    def resolve_issue(self, issue_id: int, note: str, trace_id: str) -> None:
        with self._database.connect() as connection:
            issue = connection.execute(
                "SELECT id, status FROM data_quality_issues WHERE id = ?",
                (issue_id,),
            ).fetchone()
            if issue is None:
                raise EntityNotFoundError(
                    "QUALITY_ISSUE_NOT_FOUND",
                    f"data quality issue does not exist: {issue_id}",
                )
            if issue["status"] == "resolved":
                raise StateConflictError(
                    "QUALITY_ISSUE_ALREADY_RESOLVED",
                    f"data quality issue is already resolved: {issue_id}",
                )
            connection.execute(
                """
                UPDATE data_quality_issues
                SET status = 'resolved', resolution_note = ?, resolved_at = ?
                WHERE id = ?
                """,
                (note, _utc_now(), issue_id),
            )
            _insert_audit_event(
                connection,
                trace_id,
                "quality_issue_resolved",
                "data_quality_issue",
                str(issue_id),
                {"resolution_note": note},
            )
            connection.commit()

    @staticmethod
    def _insert_source_file(
        connection: sqlite3.Connection,
        batch_id: str,
        archive_member: str,
        content_sha256: str,
        header: Sequence[str],
        row_count: int,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO source_files(
                batch_id, archive_member, content_sha256, header_json,
                expected_column_count, row_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                archive_member,
                content_sha256,
                json.dumps(header, ensure_ascii=False),
                len(header),
                row_count,
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _insert_raw_row(
        connection: sqlite3.Connection,
        source_file_id: int,
        raw_row: Any,
    ) -> tuple[int, str]:
        raw_json = json.dumps(raw_row.values, ensure_ascii=False, sort_keys=True)
        raw_cells_json = json.dumps(raw_row.cells, ensure_ascii=False)
        row_sha256 = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        cursor = connection.execute(
            """
            INSERT INTO raw_catalog_rows(
                source_file_id, source_row_number, row_sha256, raw_json,
                raw_cells_json, cell_count, expected_cell_count, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_file_id,
                raw_row.row_number,
                row_sha256,
                raw_json,
                raw_cells_json,
                len(raw_row.cells),
                len(raw_row.header),
                _utc_now(),
            ),
        )
        return int(cursor.lastrowid), row_sha256

    @staticmethod
    def _get_or_create_project(
        connection: sqlite3.Connection,
        observation: CatalogObservation,
    ) -> int:
        now = _utc_now()
        school_canonical = _canonical_text(observation.school)
        connection.execute(
            """
            INSERT INTO schools(canonical_name, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(canonical_name) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """,
            (school_canonical, observation.school, now, now),
        )
        school_id = int(
            connection.execute(
                "SELECT id FROM schools WHERE canonical_name = ?",
                (school_canonical,),
            ).fetchone()["id"]
        )

        college_canonical = _canonical_text(observation.college)
        connection.execute(
            """
            INSERT INTO colleges(
                school_id, canonical_name, display_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(school_id, canonical_name) DO UPDATE SET
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """,
            (school_id, college_canonical, observation.college, now, now),
        )
        college_id = int(
            connection.execute(
                "SELECT id FROM colleges WHERE school_id = ? AND canonical_name = ?",
                (school_id, college_canonical),
            ).fetchone()["id"]
        )

        identity_parts = (
            school_canonical,
            college_canonical,
            observation.program_code,
            observation.program_name,
            observation.direction,
            observation.campus,
            observation.training_location,
            observation.study_mode,
            observation.training_type_raw,
            observation.admission_type,
            observation.degree_type,
            observation.training_arrangement,
        )
        identity_key = hashlib.sha256(
            json.dumps(identity_parts, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        connection.execute(
            """
            INSERT INTO projects(
                identity_key, school_id, college_id, program_code, program_name,
                direction, campus, training_location, study_mode, training_type_raw,
                admission_type, degree_type, training_arrangement, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity_key) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (
                identity_key,
                school_id,
                college_id,
                observation.program_code,
                observation.program_name,
                observation.direction,
                observation.campus,
                observation.training_location,
                observation.study_mode,
                observation.training_type_raw,
                observation.admission_type,
                observation.degree_type,
                observation.training_arrangement,
                now,
                now,
            ),
        )
        return int(
            connection.execute(
                "SELECT id FROM projects WHERE identity_key = ?",
                (identity_key,),
            ).fetchone()["id"]
        )

    @staticmethod
    def _insert_observation(
        connection: sqlite3.Connection,
        project_id: int,
        raw_row_id: int,
        observation_fingerprint: str,
        observation: CatalogObservation,
    ) -> int:
        now = _utc_now()
        parameters = {
            "project_id": project_id,
            "raw_row_id": raw_row_id,
            "observation_fingerprint": observation_fingerprint,
            "admission_year": observation.admission_year,
            "strict_claim": observation.strict_claim.value,
            "strict_status": observation.strict_status.value,
            "strict_raw": observation.strict_status_raw,
            "politics": observation.subject_politics_code,
            "english": observation.subject_english_code,
            "math": observation.subject_math_code,
            "professional": observation.subject_professional_code,
            "total_plan": observation.total_plan,
            "recommendation_actual": observation.recommendation_actual,
            "special_plan": observation.special_plan,
            "effective_quota": observation.effective_general_exam_quota,
            "retest_cutoff": observation.retest_cutoff,
            "retest_count": observation.retest_count,
            "admit_count": observation.general_exam_admit_count,
            "admit_min": observation.admit_initial_min,
            "admit_median": observation.admit_initial_median,
            "admit_mean": observation.admit_initial_mean,
            "initial_weight": observation.initial_exam_weight,
            "retest_weight": observation.retest_weight,
            "machine_weight": observation.machine_test_weight,
            "machine_line": observation.machine_test_elimination_line,
            "tuition": observation.tuition_per_year,
            "study_length": observation.study_length_years,
            "first_choice": (
                int(observation.first_choice_protection)
                if observation.first_choice_protection is not None
                else None
            ),
            "evidence_grade": observation.evidence_grade.value,
            "source_level_raw": observation.source_level_raw,
            "official_source": observation.official_source,
            "retrieval_date": (
                observation.retrieval_date.isoformat()
                if observation.retrieval_date
                else None
            ),
            "notes": observation.notes,
            "created_at": now,
            "updated_at": now,
        }
        cursor = connection.execute(
            """
            INSERT INTO project_year_observations(
                project_id, raw_row_id, observation_fingerprint, admission_year,
                strict_22408_claim, strict_22408_evidence_status,
                strict_22408_status_raw, subject_politics_code,
                subject_english_code, subject_math_code, subject_professional_code,
                total_plan, recommendation_actual, special_plan,
                effective_general_exam_quota, retest_cutoff, retest_count,
                general_exam_admit_count, admit_initial_min, admit_initial_median,
                admit_initial_mean, initial_exam_weight, retest_weight,
                machine_test_weight, machine_test_elimination_line, tuition_per_year,
                study_length_years, first_choice_protection, evidence_grade,
                source_level_raw, official_source, retrieval_date, notes,
                created_at, updated_at
            ) VALUES (
                :project_id, :raw_row_id, :observation_fingerprint, :admission_year,
                :strict_claim, :strict_status, :strict_raw, :politics, :english,
                :math, :professional, :total_plan, :recommendation_actual,
                :special_plan, :effective_quota, :retest_cutoff, :retest_count,
                :admit_count, :admit_min, :admit_median, :admit_mean,
                :initial_weight, :retest_weight, :machine_weight, :machine_line,
                :tuition, :study_length, :first_choice, :evidence_grade,
                :source_level_raw, :official_source, :retrieval_date, :notes,
                :created_at, :updated_at
            )
            """,
            parameters,
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _get_or_create_evidence_source(
        connection: sqlite3.Connection,
        observation: CatalogObservation,
        archive_member: str,
        row_number: int,
        resolved_title: str | None,
        resolved_from: tuple[str, int] | None,
    ) -> int:
        title = resolved_title or f"Legacy row {archive_member}:{row_number}"
        match = _URL_PATTERN.search(title)
        url = match.group(0).rstrip(").。]>") if match else None
        identity_payload = (
            title,
            observation.evidence_grade.value,
            observation.retrieval_date.isoformat() if observation.retrieval_date else None,
        )
        identity_key = hashlib.sha256(
            json.dumps(identity_payload, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        now = _utc_now()
        source_note = f"Imported from {archive_member}:{row_number}"
        if resolved_from is not None:
            source_note += f"; resolved '同上' from {resolved_from[0]}:{resolved_from[1]}"
        connection.execute(
            """
            INSERT INTO evidence_sources(
                identity_key, title, url, evidence_grade, retrieved_date,
                source_note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity_key) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (
                identity_key,
                title,
                url,
                observation.evidence_grade.value,
                observation.retrieval_date.isoformat()
                if observation.retrieval_date
                else None,
                source_note,
                now,
                now,
            ),
        )
        return int(
            connection.execute(
                "SELECT id FROM evidence_sources WHERE identity_key = ?",
                (identity_key,),
            ).fetchone()["id"]
        )

    @staticmethod
    def _insert_field_evidence(
        connection: sqlite3.Connection,
        observation_id: int,
        source_id: int,
        observation: CatalogObservation,
    ) -> None:
        now = _utc_now()
        for raw_field in CRITICAL_EVIDENCE_FIELDS:
            raw_value = observation.raw_values.get(raw_field)
            if raw_value is None:
                continue
            attribute = NORMALIZED_ATTRIBUTE_BY_RAW_FIELD.get(raw_field, raw_field)
            normalized_value = getattr(observation, attribute, None)
            if hasattr(normalized_value, "value"):
                normalized_value = normalized_value.value
            connection.execute(
                """
                INSERT INTO field_evidence(
                    observation_id, field_name, raw_value, normalized_value,
                    source_id, verification_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                ON CONFLICT(observation_id, field_name, source_id) DO NOTHING
                """,
                (
                    observation_id,
                    raw_field,
                    raw_value,
                    _stringify(normalized_value),
                    source_id,
                    now,
                    now,
                ),
            )

    @staticmethod
    def _insert_issue(
        connection: sqlite3.Connection,
        batch_id: str,
        raw_row_id: int,
        observation_id: int | None,
        row_sha256: str,
        issue: ValidationIssue,
    ) -> bool:
        fingerprint_payload = (
            row_sha256,
            issue.code,
            issue.field_name,
            issue.raw_value,
            issue.message,
        )
        issue_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        cursor = connection.execute(
            """
            INSERT INTO data_quality_issues(
                issue_fingerprint, batch_id, raw_row_id, observation_id,
                issue_code, severity, field_name, raw_value, message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_fingerprint) DO NOTHING
            """,
            (
                issue_fingerprint,
                batch_id,
                raw_row_id,
                observation_id,
                issue.code,
                issue.severity.value,
                issue.field_name,
                issue.raw_value,
                issue.message,
                _utc_now(),
            ),
        )
        return cursor.rowcount == 1


def _canonical_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _observation_fingerprint(raw_values: Mapping[str, str]) -> str:
    payload = json.dumps(raw_values, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scalar(connection: sqlite3.Connection, sql: str) -> int:
    return int(connection.execute(sql).fetchone()[0])


def _mock_exam_doctor_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    metrics = {
        name: _scalar(connection, query)
        for name, query in _MOCK_EXAM_DOCTOR_ERROR_QUERIES.items()
    }
    metrics["legacy_mock_session_count"] = _scalar(
        connection,
        "SELECT COUNT(*) FROM mock_exam_sessions WHERE ledger_version = 1",
    )
    return metrics


def _policy_event_doctor_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        name: _scalar(connection, query)
        for name, query in _POLICY_EVENT_DOCTOR_ERROR_QUERIES.items()
    }


def _resolved_catalog_doctor_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        name: _scalar(connection, query)
        for name, query in _RESOLVED_CATALOG_DOCTOR_ERROR_QUERIES.items()
    }


def _statistical_fact_doctor_metrics(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    # Public commands reject an outdated schema before reaching the repository.
    # This guard keeps read-only repository diagnostics usable in migration
    # fixtures that intentionally stop before migration 026.
    has_quality_view = connection.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'view' AND name = 'v_statistical_fact_quality_issues'
        """
    ).fetchone()
    if has_quality_view is None:
        return {name: 0 for name in _STATISTICAL_FACT_DOCTOR_ERROR_QUERIES}
    return {
        name: _scalar(connection, query)
        for name, query in _STATISTICAL_FACT_DOCTOR_ERROR_QUERIES.items()
    }


def _source_metadata_correction_doctor_metrics(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    metrics = {
        name: _scalar(connection, query)
        for name, query in _SOURCE_METADATA_CORRECTION_DOCTOR_ERROR_QUERIES.items()
    }
    metrics["evidence_source_correction_fingerprint_mismatch"] = sum(
        row["correction_fingerprint"]
        != _evidence_source_metadata_correction_fingerprint(row)
        for row in connection.execute(
            """
            SELECT
                correction.correction_fingerprint,
                source.identity_key AS source_identity_key,
                correction.source_content_sha256,
                correction.field_name,
                correction.prior_effective_value,
                correction.corrected_value,
                predecessor.correction_fingerprint
                    AS supersedes_correction_fingerprint,
                correction.basis_url,
                correction.basis_content_sha256,
                correction.basis_retrieved_date,
                correction.reason
            FROM evidence_source_metadata_corrections correction
            JOIN evidence_sources source ON source.id = correction.source_id
            LEFT JOIN evidence_source_metadata_corrections predecessor
              ON predecessor.id = correction.supersedes_correction_id
            """
        )
    )
    metrics["evidence_source_metadata_correction_count"] = _scalar(
        connection,
        "SELECT COUNT(*) FROM evidence_source_metadata_corrections",
    )
    return metrics


def _evidence_source_metadata_correction_fingerprint(
    row: Mapping[str, Any],
) -> str:
    payload = {
        "basis_content_sha256": row["basis_content_sha256"],
        "basis_retrieved_date": row["basis_retrieved_date"],
        "basis_url": row["basis_url"],
        "corrected_value": row["corrected_value"],
        "field_name": row["field_name"],
        "fingerprint_version": "evidence-source-metadata-correction/v1",
        "prior_effective_value": row["prior_effective_value"],
        "reason": row["reason"],
        "source_content_sha256": row["source_content_sha256"],
        "source_identity_key": row["source_identity_key"],
        "supersedes_correction_fingerprint": row[
            "supersedes_correction_fingerprint"
        ],
    }
    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _achievement_doctor_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    metrics = {
        name: _scalar(connection, query)
        for name, query in _ACHIEVEMENT_DOCTOR_ERROR_QUERIES.items()
    }
    metrics.update(
        {
            "applicant_achievement_event_count": _scalar(
                connection,
                "SELECT COUNT(*) FROM applicant_achievement_events",
            ),
            "current_applicant_achievement_count": _scalar(
                connection,
                "SELECT COUNT(*) FROM v_current_applicant_achievements",
            ),
            "applicant_evidence_document_count": _scalar(
                connection,
                "SELECT COUNT(*) FROM applicant_evidence_documents",
            ),
            "applicant_evidence_review_event_count": _scalar(
                connection,
                "SELECT COUNT(*) FROM applicant_evidence_review_events",
            ),
            "applicant_achievement_evidence_review_link_count": _scalar(
                connection,
                "SELECT COUNT(*) FROM applicant_achievement_evidence_review_links",
            ),
            "applicant_achievement_conflict_count": _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM v_current_applicant_achievements
                WHERE verification_status = 'conflict'
                """,
            ),
        }
    )
    return metrics


def _distribution(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    where: str | None = None,
) -> list[dict[str, Any]]:
    sql = f"SELECT {column} AS value, COUNT(*) AS count FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += f" GROUP BY {column} ORDER BY {column}"
    return [dict(row) for row in connection.execute(sql)]


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id, event_type, entity_type, entity_id, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            trace_id,
            event_type,
            entity_type,
            entity_id,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            _utc_now(),
        ),
    )


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _info_severity() -> Any:
    from chose_school.domain.enums import IssueSeverity

    return IssueSeverity.INFO
