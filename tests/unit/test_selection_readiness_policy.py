from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from tests.support import REPOSITORY_ROOT  # noqa: F401

from chose_school.business.selection_readiness_policy import (
    all_required_selection_gates_pass,
    apply_selection_readiness,
    evaluate_selection_readiness,
    selection_blocking_reasons,
)
from chose_school.domain.enums import (
    PreferenceAcceptanceLevel,
    PreferenceDimension,
    SelectionGateCode,
    SelectionGateStatus,
)
from chose_school.domain.models import (
    AssessmentSummary,
    SelectionGateResult,
    SelectionReadinessFacts,
    Settings,
)


_REQUIRED_DURATIONS = (90, 120, 180)
_PROGRAM_CODES = (
    "085404",
    "085405",
    "085410",
    "085411",
    "085412",
    "085400",
    "145200",
)
_JOINT_TRAINING_KEYS = (
    "enterprise",
    "international",
    "offsite",
    "unknown_assignment",
)
_RETEST_FORMAT_KEYS = (
    "high_weight_interview",
    "machine_test",
    "pure_interview",
    "theory_closed_book",
    "written_test",
)


class SelectionReadinessPolicyTests(unittest.TestCase):
    def test_gate_order_matches_the_complete_eight_gate_contract(self) -> None:
        gates = evaluate_selection_readiness(
            _score_summary(is_ready=False),
            _facts(),
            _settings(),
        )

        self.assertEqual(len(gates), 8)
        self.assertEqual(tuple(gate.code for gate in gates), tuple(SelectionGateCode))

    def test_empty_or_structurally_incomplete_gate_collection_never_passes(self) -> None:
        passed_gates = _all_passed_gates()

        self.assertTrue(all_required_selection_gates_pass(passed_gates))
        self.assertFalse(all_required_selection_gates_pass(()))
        self.assertFalse(all_required_selection_gates_pass(passed_gates[:-1]))
        self.assertFalse(all_required_selection_gates_pass(tuple(reversed(passed_gates))))
        self.assertFalse(
            all_required_selection_gates_pass(
                passed_gates[:-1] + (passed_gates[-2],)
            )
        )
        self.assertFalse(
            all_required_selection_gates_pass(
                (
                    replace(
                        passed_gates[0],
                        blocking_reason="INCONSISTENT_PASSED_GATE",
                    ),
                    *passed_gates[1:],
                )
            )
        )

    def test_blocked_and_not_evaluable_statuses_each_prevent_readiness(self) -> None:
        passed_gates = _all_passed_gates()
        score_index = tuple(SelectionGateCode).index(SelectionGateCode.SCORE_WINDOW)
        catalog_index = tuple(SelectionGateCode).index(
            SelectionGateCode.CANDIDATE_2027_CATALOG
        )

        blocked = list(passed_gates)
        blocked[score_index] = replace(
            blocked[score_index],
            status=SelectionGateStatus.BLOCKED,
            blocking_reason="SCORE_WINDOW_INCOMPLETE",
        )
        not_evaluable = list(passed_gates)
        not_evaluable[catalog_index] = replace(
            not_evaluable[catalog_index],
            status=SelectionGateStatus.NOT_EVALUABLE,
            blocking_reason="CANDIDATE_CATALOG_NOT_EVALUABLE",
        )

        self.assertFalse(all_required_selection_gates_pass(tuple(blocked)))
        self.assertFalse(all_required_selection_gates_pass(tuple(not_evaluable)))

    def test_blocking_reasons_are_stable_deduplicated_and_skip_passed_gates(
        self,
    ) -> None:
        gates = (
            _gate(
                SelectionGateCode.SCORE_WINDOW,
                SelectionGateStatus.BLOCKED,
                "FIRST_REASON",
            ),
            _gate(
                SelectionGateCode.SUBJECT_RISK,
                SelectionGateStatus.NOT_EVALUABLE,
                "SECOND_REASON",
            ),
            _gate(
                SelectionGateCode.CANDIDATE_RETEST_CONTRACT,
                SelectionGateStatus.BLOCKED,
                "FIRST_REASON",
            ),
            _gate(
                SelectionGateCode.PREFERENCE_INPUT_COVERAGE,
                SelectionGateStatus.PASSED,
                "PASSED_REASON_MUST_BE_IGNORED",
            ),
            _gate(
                SelectionGateCode.CANDIDATE_STRUCTURE,
                SelectionGateStatus.BLOCKED,
                None,
            ),
        )

        self.assertEqual(
            selection_blocking_reasons(gates),
            ("FIRST_REASON", "SECOND_REASON"),
        )

    def test_score_gate_tracks_the_window_while_subject_review_stays_fail_closed(
        self,
    ) -> None:
        settings = _settings()
        facts = _facts()

        incomplete = _gates_by_code(
            evaluate_selection_readiness(
                _score_summary(is_ready=False),
                facts,
                settings,
            )
        )
        ready = _gates_by_code(
            evaluate_selection_readiness(
                _score_summary(is_ready=True),
                facts,
                settings,
            )
        )

        self.assertEqual(
            incomplete[SelectionGateCode.SCORE_WINDOW].status,
            SelectionGateStatus.BLOCKED,
        )
        self.assertEqual(
            incomplete[SelectionGateCode.SCORE_WINDOW].blocking_reason,
            "SCORE_WINDOW_INCOMPLETE",
        )
        self.assertEqual(
            incomplete[SelectionGateCode.SUBJECT_RISK].status,
            SelectionGateStatus.BLOCKED,
        )
        self.assertEqual(
            incomplete[SelectionGateCode.SUBJECT_RISK].blocking_reason,
            "SUBJECT_RISK_NOT_REVIEWABLE",
        )

        self.assertEqual(
            ready[SelectionGateCode.SCORE_WINDOW].status,
            SelectionGateStatus.PASSED,
        )
        self.assertIsNone(
            ready[SelectionGateCode.SCORE_WINDOW].blocking_reason
        )
        self.assertEqual(
            ready[SelectionGateCode.SUBJECT_RISK].status,
            SelectionGateStatus.NOT_EVALUABLE,
        )
        self.assertEqual(
            ready[SelectionGateCode.SUBJECT_RISK].blocking_reason,
            "SUBJECT_RISK_REVIEW_NOT_RECORDED",
        )

    def test_machine_measurement_is_deferred_outside_preliminary_selection(self) -> None:
        gates = _gates_by_code(
            evaluate_selection_readiness(
                _score_summary(is_ready=False),
                _facts(),
                _settings(),
            )
        )

        self.assertNotIn("machine_duration_coverage", [code.value for code in gates])
        retest = gates[SelectionGateCode.CANDIDATE_RETEST_CONTRACT]
        self.assertEqual(retest.status, SelectionGateStatus.NOT_EVALUABLE)
        self.assertEqual(
            retest.blocking_reason,
            "CANDIDATE_RETEST_CONTRACT_NOT_RECORDED",
        )
        self.assertFalse(
            retest.details["personal_machine_performance_required_before_preliminary_exam"]
        )
        self.assertEqual(
            retest.details["machine_preparation_stage"],
            "after_preliminary_exam_pass",
        )

    def test_active_candidate_structure_ignores_legacy_rows_but_research_stays_unconfirmed(
        self,
    ) -> None:
        gates = _gates_by_code(
            evaluate_selection_readiness(
                _score_summary(is_ready=False),
                _facts(
                    active_candidate_count=1,
                    active_research_hypothesis_count=1,
                    legacy_snapshot_count=9,
                    legacy_candidate_count=99,
                ),
                _settings(),
            )
        )

        structure = gates[SelectionGateCode.CANDIDATE_STRUCTURE]
        catalog = gates[SelectionGateCode.CANDIDATE_2027_CATALOG]
        self.assertEqual(structure.status, SelectionGateStatus.PASSED)
        self.assertIsNone(structure.blocking_reason)
        self.assertFalse(structure.details["legacy_rows_are_authoritative"])
        self.assertFalse(structure.details["legacy_rows_affect_gate"])
        self.assertEqual(catalog.status, SelectionGateStatus.NOT_EVALUABLE)
        self.assertEqual(
            catalog.blocking_reason,
            "CANDIDATE_CATALOG_NOT_EVALUABLE",
        )
        self.assertEqual(catalog.details["active_research_hypothesis_count"], 1)
        self.assertTrue(catalog.details["research_hypotheses_require_official_binding"])

    def test_catalog_passes_only_when_every_active_candidate_is_official_confirmed(
        self,
    ) -> None:
        settings = _settings()
        score = _score_summary(is_ready=False)
        confirmed = _gates_by_code(
            evaluate_selection_readiness(
                score,
                _facts(
                    active_candidate_count=2,
                    active_official_observation_count=2,
                    active_official_confirmed_count=2,
                ),
                settings,
            )
        )[SelectionGateCode.CANDIDATE_2027_CATALOG]
        one_unconfirmed = _gates_by_code(
            evaluate_selection_readiness(
                score,
                _facts(
                    active_candidate_count=2,
                    active_official_observation_count=2,
                    active_official_confirmed_count=1,
                ),
                settings,
            )
        )[SelectionGateCode.CANDIDATE_2027_CATALOG]
        mixed_with_research = _gates_by_code(
            evaluate_selection_readiness(
                score,
                _facts(
                    active_candidate_count=2,
                    active_research_hypothesis_count=1,
                    active_official_observation_count=1,
                    active_official_confirmed_count=1,
                ),
                settings,
            )
        )[SelectionGateCode.CANDIDATE_2027_CATALOG]

        self.assertEqual(confirmed.status, SelectionGateStatus.PASSED)
        self.assertIsNone(confirmed.blocking_reason)
        self.assertTrue(confirmed.details["all_active_candidates_are_official_confirmed"])
        self.assertEqual(one_unconfirmed.status, SelectionGateStatus.NOT_EVALUABLE)
        self.assertEqual(one_unconfirmed.details["official_candidates_without_confirmation"], 1)
        self.assertEqual(mixed_with_research.status, SelectionGateStatus.NOT_EVALUABLE)
        self.assertEqual(mixed_with_research.details["active_research_hypothesis_count"], 1)

    def test_candidate_basis_count_inconsistency_fails_closed(self) -> None:
        gates = _gates_by_code(
            evaluate_selection_readiness(
                _score_summary(is_ready=False),
                _facts(
                    active_candidate_count=2,
                    active_official_observation_count=1,
                ),
                _settings(),
            )
        )

        structure = gates[SelectionGateCode.CANDIDATE_STRUCTURE]
        self.assertEqual(structure.status, SelectionGateStatus.NOT_EVALUABLE)
        self.assertEqual(
            structure.blocking_reason,
            "CANDIDATE_STRUCTURE_INCONSISTENT",
        )
        self.assertFalse(structure.details["candidate_basis_partition_is_consistent"])

    def test_preference_gate_blocks_missing_and_unknown_but_accepts_complete_input(
        self,
    ) -> None:
        settings = _settings()
        score_summary = _score_summary(is_ready=False)
        complete_preferences = list(_complete_preferences())
        unknown_preferences = [dict(row) for row in complete_preferences]
        target_index = next(
            index
            for index, row in enumerate(unknown_preferences)
            if row["dimension"] == PreferenceDimension.PROGRAM_CODE.value
            and row["subject_key"] == "085404"
        )
        unknown_preferences[target_index]["acceptance_level"] = (
            PreferenceAcceptanceLevel.UNKNOWN.value
        )

        missing_gate = _gates_by_code(
            evaluate_selection_readiness(
                score_summary,
                _facts(),
                settings,
            )
        )[SelectionGateCode.PREFERENCE_INPUT_COVERAGE]
        unknown_gate = _gates_by_code(
            evaluate_selection_readiness(
                score_summary,
                _facts(current_preferences=tuple(unknown_preferences)),
                settings,
            )
        )[SelectionGateCode.PREFERENCE_INPUT_COVERAGE]
        complete_gate = _gates_by_code(
            evaluate_selection_readiness(
                score_summary,
                _facts(current_preferences=tuple(complete_preferences)),
                settings,
            )
        )[SelectionGateCode.PREFERENCE_INPUT_COVERAGE]

        self.assertEqual(missing_gate.status, SelectionGateStatus.BLOCKED)
        self.assertEqual(
            missing_gate.blocking_reason,
            "PERSONAL_PREFERENCES_INCOMPLETE",
        )
        self.assertIn("region:actual_training_scope", missing_gate.details["missing_subjects"])

        self.assertEqual(unknown_gate.status, SelectionGateStatus.BLOCKED)
        self.assertIn(
            "program_code:085404",
            unknown_gate.details["unknown_subjects"],
        )

        self.assertEqual(complete_gate.status, SelectionGateStatus.PASSED)
        self.assertIsNone(complete_gate.blocking_reason)
        self.assertTrue(complete_gate.details["is_preference_intake_complete"])
        self.assertGreater(
            complete_gate.details["answered_subject_count"],
            0,
        )

    def test_apply_readiness_keeps_selection_closed_after_measurable_gates_pass(
        self,
    ) -> None:
        summary = apply_selection_readiness(
            _score_summary(is_ready=True),
            _facts(
                current_preferences=_complete_preferences(),
            ),
            _settings(),
        )
        gates = _gates_by_code(summary.selection_gates)

        self.assertFalse(summary.is_selection_ready)
        self.assertEqual(len(summary.selection_gates), 8)
        self.assertEqual(
            gates[SelectionGateCode.SCORE_WINDOW].status,
            SelectionGateStatus.PASSED,
        )
        self.assertEqual(
            gates[SelectionGateCode.PREFERENCE_INPUT_COVERAGE].status,
            SelectionGateStatus.PASSED,
        )
        self.assertEqual(
            summary.selection_blocking_reasons,
            (
                "SUBJECT_RISK_REVIEW_NOT_RECORDED",
                "ACTIVE_CANDIDATE_SET_EMPTY",
                "CANDIDATE_CATALOG_NOT_EVALUABLE",
                "CANDIDATE_QUOTA_NOT_EVALUABLE",
                "CANDIDATE_RETEST_CONTRACT_NOT_RECORDED",
                "CANDIDATE_FAIRNESS_REVIEW_NOT_RECORDED",
            ),
        )


def _settings() -> Settings:
    root = Path(".").resolve()
    return Settings(
        repository_root=root,
        database_path=root / "test-selection-readiness.sqlite3",
        log_path=root / "test-selection-readiness.jsonl",
        log_level="INFO",
        busy_timeout_ms=5000,
        catalog_member_pattern="*_db_*.csv",
        importer_version="test",
        max_archive_uncompressed_bytes=1,
        max_member_uncompressed_bytes=1,
        max_compression_ratio=1.0,
        strict_politics_code="101",
        strict_english_code="204",
        strict_math_code="302",
        strict_professional_code="408",
        minimum_mock_sessions=5,
        mock_rolling_window_size=5,
        required_machine_durations=_REQUIRED_DURATIONS,
        profile_key="default",
        undergraduate_school="临沂大学",
        undergraduate_major="软件工程",
        target_exam_year=2027,
        target_degree_type="专业学位",
        target_tier="985优先，保留211风险对冲",
    )


def _score_summary(is_ready: bool) -> AssessmentSummary:
    window_ids = (1, 2, 3, 4, 5) if is_ready else ()
    return AssessmentSummary(
        session_count=len(window_ids),
        total_mean=None,
        total_standard_deviation=None,
        conservative_total=None,
        is_decision_ready=is_ready,
        subject_means={},
        required_session_count=5,
        rolling_window_size=5,
        active_comparison_key="101+204+302+408:test" if is_ready else None,
        window_session_ids=window_ids,
        is_score_window_ready=is_ready,
    )


def _facts(
    *,
    current_preferences: Sequence[Mapping[str, Any]] = (),
    active_candidate_count: int = 0,
    active_research_hypothesis_count: int = 0,
    active_official_observation_count: int = 0,
    active_official_confirmed_count: int = 0,
    legacy_snapshot_count: int = 0,
    legacy_candidate_count: int = 0,
) -> SelectionReadinessFacts:
    return SelectionReadinessFacts(
        profile_id=1,
        current_preferences=tuple(current_preferences),
        target_year_observation_count=0,
        official_confirmed_target_year_count=0,
        official_pending_target_year_count=0,
        legacy_snapshot_count=legacy_snapshot_count,
        legacy_candidate_count=legacy_candidate_count,
        active_candidate_count=active_candidate_count,
        active_research_hypothesis_count=active_research_hypothesis_count,
        active_official_observation_count=active_official_observation_count,
        active_official_confirmed_count=active_official_confirmed_count,
        fairness_review_count=0,
        adverse_fairness_review_count=0,
    )


def _complete_preferences() -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = [
        _preference(
            PreferenceDimension.REGION,
            "actual_training_scope",
            PreferenceAcceptanceLevel.ACCEPT,
            {"mode": "mainland"},
        )
    ]
    rows.extend(
        _preference(
            PreferenceDimension.JOINT_TRAINING,
            subject_key,
            PreferenceAcceptanceLevel.REJECT,
        )
        for subject_key in _JOINT_TRAINING_KEYS
    )
    rows.append(
        _preference(
            PreferenceDimension.TUITION_CEILING,
            "default",
            PreferenceAcceptanceLevel.ACCEPT,
            {"mode": "no_hard_cap"},
        )
    )
    rows.extend(
        _preference(
            PreferenceDimension.PROGRAM_CODE,
            subject_key,
            (
                PreferenceAcceptanceLevel.ACCEPT
                if subject_key in {"085404", "085405"}
                else PreferenceAcceptanceLevel.REJECT
            ),
        )
        for subject_key in _PROGRAM_CODES
    )
    rows.append(
        _preference(
            PreferenceDimension.PROGRAM_CODE,
            "any_other_eligible_code",
            PreferenceAcceptanceLevel.ACCEPT,
        )
    )
    rows.extend(
        (
            _preference(
                PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                "211_floor",
                PreferenceAcceptanceLevel.ACCEPT,
            ),
            _preference(
                PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                "non_211_acceptable",
                PreferenceAcceptanceLevel.REJECT,
            ),
        )
    )
    rows.extend(
        _preference(
            PreferenceDimension.RETEST_FORMAT,
            subject_key,
            PreferenceAcceptanceLevel.ACCEPT,
        )
        for subject_key in _RETEST_FORMAT_KEYS
    )
    rows.extend(
        _preference(
            PreferenceDimension.ADMISSION_FAIRNESS,
            subject_key,
            PreferenceAcceptanceLevel.ACCEPT,
        )
        for subject_key in (
            "ordinary_undergraduate_nondiscrimination",
            "evidence_backed_fair_reputation",
        )
    )
    return tuple(rows)


def _preference(
    dimension: PreferenceDimension,
    subject_key: str,
    acceptance_level: PreferenceAcceptanceLevel,
    value: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    return {
        "dimension": dimension.value,
        "subject_key": subject_key,
        "acceptance_level": acceptance_level.value,
        "value": dict(value or {}),
    }


def _all_passed_gates() -> tuple[SelectionGateResult, ...]:
    return tuple(
        _gate(code, SelectionGateStatus.PASSED, None)
        for code in SelectionGateCode
    )


def _gate(
    code: SelectionGateCode,
    status: SelectionGateStatus,
    reason: str | None,
) -> SelectionGateResult:
    return SelectionGateResult(
        code=code,
        status=status,
        blocking_reason=reason,
        details={},
    )


def _gates_by_code(
    gates: Sequence[SelectionGateResult],
) -> Mapping[SelectionGateCode, SelectionGateResult]:
    return {gate.code: gate for gate in gates}


if __name__ == "__main__":
    unittest.main()
