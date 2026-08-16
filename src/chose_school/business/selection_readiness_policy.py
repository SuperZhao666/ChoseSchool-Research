from __future__ import annotations

from dataclasses import asdict, replace

from chose_school.business.preference_service import (
    summarize_preference_readiness,
)
from chose_school.domain.enums import SelectionGateCode, SelectionGateStatus
from chose_school.domain.models import (
    AssessmentSummary,
    SelectionGateResult,
    SelectionReadinessFacts,
    Settings,
)


SELECTION_GATE_VERSION = "selection-readiness-v3"


def apply_selection_readiness(
    score_summary: AssessmentSummary,
    facts: SelectionReadinessFacts,
    settings: Settings,
) -> AssessmentSummary:
    gates = evaluate_selection_readiness(score_summary, facts, settings)
    return replace(
        score_summary,
        is_selection_ready=all_required_selection_gates_pass(gates),
        selection_blocking_reasons=selection_blocking_reasons(gates),
        selection_gate_version=SELECTION_GATE_VERSION,
        selection_gates=gates,
    )


def evaluate_selection_readiness(
    score_summary: AssessmentSummary,
    facts: SelectionReadinessFacts,
    settings: Settings,
) -> tuple[SelectionGateResult, ...]:
    preference_readiness = summarize_preference_readiness(
        facts.current_preferences
    )

    score_gate = _gate(
        SelectionGateCode.SCORE_WINDOW,
        (
            SelectionGateStatus.PASSED
            if score_summary.is_score_window_ready
            else SelectionGateStatus.BLOCKED
        ),
        None if score_summary.is_score_window_ready else "SCORE_WINDOW_INCOMPLETE",
        {
            "actual_session_count": score_summary.session_count,
            "required_session_count": score_summary.required_session_count,
            "active_comparison_key": score_summary.active_comparison_key,
            "window_session_ids": score_summary.window_session_ids,
        },
    )
    subject_gate = _gate(
        SelectionGateCode.SUBJECT_RISK,
        (
            SelectionGateStatus.NOT_EVALUABLE
            if score_summary.is_score_window_ready
            else SelectionGateStatus.BLOCKED
        ),
        (
            "SUBJECT_RISK_REVIEW_NOT_RECORDED"
            if score_summary.is_score_window_ready
            else "SUBJECT_RISK_NOT_REVIEWABLE"
        ),
        {
            "score_window_ready": score_summary.is_score_window_ready,
            "window_session_ids": score_summary.window_session_ids,
            "review_contract_available": False,
        },
    )
    preference_gate = _gate(
        SelectionGateCode.PREFERENCE_INPUT_COVERAGE,
        (
            SelectionGateStatus.PASSED
            if preference_readiness.is_preference_intake_complete
            else SelectionGateStatus.BLOCKED
        ),
        (
            None
            if preference_readiness.is_preference_intake_complete
            else "PERSONAL_PREFERENCES_INCOMPLETE"
        ),
        asdict(preference_readiness),
    )
    candidate_partition_is_consistent = (
        facts.active_candidate_count
        == facts.active_research_hypothesis_count
        + facts.active_official_observation_count
    )
    candidate_structure_is_ready = (
        facts.active_candidate_count > 0
        and candidate_partition_is_consistent
    )
    candidate_structure_reason = None
    if facts.active_candidate_count <= 0:
        candidate_structure_reason = "ACTIVE_CANDIDATE_SET_EMPTY"
    elif not candidate_partition_is_consistent:
        candidate_structure_reason = "CANDIDATE_STRUCTURE_INCONSISTENT"
    candidate_structure_gate = _gate(
        SelectionGateCode.CANDIDATE_STRUCTURE,
        (
            SelectionGateStatus.PASSED
            if candidate_structure_is_ready
            else SelectionGateStatus.NOT_EVALUABLE
        ),
        candidate_structure_reason,
        {
            "candidate_target_schema_available": True,
            "active_candidate_count": facts.active_candidate_count,
            "active_research_hypothesis_count": (
                facts.active_research_hypothesis_count
            ),
            "active_official_observation_count": (
                facts.active_official_observation_count
            ),
            "candidate_basis_partition_is_consistent": (
                candidate_partition_is_consistent
            ),
            "legacy_snapshot_count": facts.legacy_snapshot_count,
            "legacy_candidate_count": facts.legacy_candidate_count,
            "legacy_rows_are_authoritative": False,
            "legacy_rows_affect_gate": False,
        },
    )
    official_candidates_without_confirmation = max(
        0,
        facts.active_official_observation_count
        - facts.active_official_confirmed_count,
    )
    candidate_catalog_is_ready = (
        candidate_structure_is_ready
        and facts.active_research_hypothesis_count == 0
        and facts.active_official_observation_count
        == facts.active_candidate_count
        and facts.active_official_confirmed_count
        == facts.active_official_observation_count
    )
    catalog_gate = _gate(
        SelectionGateCode.CANDIDATE_2027_CATALOG,
        (
            SelectionGateStatus.PASSED
            if candidate_catalog_is_ready
            else SelectionGateStatus.NOT_EVALUABLE
        ),
        None if candidate_catalog_is_ready else "CANDIDATE_CATALOG_NOT_EVALUABLE",
        {
            "target_exam_year": settings.target_exam_year,
            "active_candidate_count": facts.active_candidate_count,
            "active_research_hypothesis_count": (
                facts.active_research_hypothesis_count
            ),
            "active_official_observation_count": (
                facts.active_official_observation_count
            ),
            "active_official_confirmed_count": (
                facts.active_official_confirmed_count
            ),
            "official_candidates_without_confirmation": (
                official_candidates_without_confirmation
            ),
            "all_active_candidates_are_official_confirmed": (
                candidate_catalog_is_ready
            ),
            "research_hypotheses_require_official_binding": True,
            "same_target_year_official_confirmed_required": True,
            "target_year_observation_count": facts.target_year_observation_count,
            "official_confirmed_global_count": (
                facts.official_confirmed_target_year_count
            ),
            "official_pending_global_count": (
                facts.official_pending_target_year_count
            ),
            "global_catalog_counts_are_authoritative": False,
            "authoritative_candidate_set_available": (
                candidate_structure_is_ready
            ),
        },
    )
    quota_gate = _gate(
        SelectionGateCode.CANDIDATE_ORDINARY_QUOTA,
        SelectionGateStatus.NOT_EVALUABLE,
        "CANDIDATE_QUOTA_NOT_EVALUABLE",
        {
            "target_exam_year": settings.target_exam_year,
            "required_fact_key": "quota.general_effective",
            "required_population_scope": "ordinary_general_exam",
            "required_statistic_scope": "project",
            "active_candidate_count": facts.active_candidate_count,
            "candidate_specific_fact_coverage_available": False,
            "authoritative_candidate_set_available": (
                candidate_structure_is_ready
            ),
        },
    )
    retest_gate = _gate(
        SelectionGateCode.CANDIDATE_RETEST_CONTRACT,
        SelectionGateStatus.NOT_EVALUABLE,
        "CANDIDATE_RETEST_CONTRACT_NOT_RECORDED",
        {
            "candidate_specific_retest_contract_available": False,
            "active_candidate_count": facts.active_candidate_count,
            "authoritative_candidate_set_available": (
                candidate_structure_is_ready
            ),
            "required_scope": (
                "format, weight, hard elimination lines, and scoring transparency"
            ),
            "personal_machine_performance_required_before_preliminary_exam": False,
            "machine_preparation_stage": "after_preliminary_exam_pass",
        },
    )
    fairness_gate = _gate(
        SelectionGateCode.CANDIDATE_FAIRNESS_REVIEW,
        SelectionGateStatus.NOT_EVALUABLE,
        "CANDIDATE_FAIRNESS_REVIEW_NOT_RECORDED",
        {
            "review_contract": "candidate-fairness-v1",
            "project_year_review_count": facts.fairness_review_count,
            "adverse_review_count": facts.adverse_fairness_review_count,
            "global_review_counts_are_authoritative": False,
            "candidate_specific_review_coverage_available": False,
            "active_candidate_count": facts.active_candidate_count,
            "authoritative_candidate_set_available": (
                candidate_structure_is_ready
            ),
            "school_wide_reputation_is_not_accepted_as_project_fact": True,
            "ordinary_undergraduate_background_review_required": True,
        },
    )
    return (
        score_gate,
        subject_gate,
        preference_gate,
        candidate_structure_gate,
        catalog_gate,
        quota_gate,
        retest_gate,
        fairness_gate,
    )


def all_required_selection_gates_pass(
    gates: tuple[SelectionGateResult, ...],
) -> bool:
    expected_codes = tuple(SelectionGateCode)
    return (
        len(gates) == len(expected_codes)
        and tuple(gate.code for gate in gates) == expected_codes
        and all(
            gate.status is SelectionGateStatus.PASSED
            and gate.blocking_reason is None
            for gate in gates
        )
    )


def selection_blocking_reasons(
    gates: tuple[SelectionGateResult, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for gate in gates:
        if (
            gate.status is SelectionGateStatus.PASSED
            or gate.blocking_reason is None
            or gate.blocking_reason in reasons
        ):
            continue
        reasons.append(gate.blocking_reason)
    return tuple(reasons)


def _gate(
    code: SelectionGateCode,
    status: SelectionGateStatus,
    blocking_reason: str | None,
    details: dict[str, object],
) -> SelectionGateResult:
    return SelectionGateResult(
        code=code,
        status=status,
        blocking_reason=blocking_reason,
        details=details,
    )
