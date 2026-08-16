from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.candidate_model import (
    CandidateIdentityInput,
    CandidateTargetAction,
    CandidateTargetBasis,
    CandidateTargetVersionInput,
)
from chose_school.domain.enums import (
    EvidenceDocumentType,
    SelectionGateCode,
    SelectionGateStatus,
    Strict22408Status,
)
from chose_school.domain.models import OfficialProjectObservationInput


EXPECTED_EMPTY_BLOCKERS = (
    "SCORE_WINDOW_INCOMPLETE",
    "SUBJECT_RISK_NOT_REVIEWABLE",
    "PERSONAL_PREFERENCES_INCOMPLETE",
    "ACTIVE_CANDIDATE_SET_EMPTY",
    "CANDIDATE_CATALOG_NOT_EVALUABLE",
    "CANDIDATE_QUOTA_NOT_EVALUABLE",
    "CANDIDATE_RETEST_CONTRACT_NOT_RECORDED",
    "CANDIDATE_FAIRNESS_REVIEW_NOT_RECORDED",
)


class SelectionReadinessIntegrationTest(unittest.TestCase):
    def test_empty_database_exposes_all_eight_selection_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))

            summary = application.assessment.summarize()

            self.assertFalse(summary.is_decision_ready)
            self.assertFalse(summary.is_score_window_ready)
            self.assertFalse(summary.is_selection_ready)
            self.assertEqual(summary.selection_gate_version, "selection-readiness-v3")
            self.assertEqual(
                tuple(gate.code for gate in summary.selection_gates),
                tuple(SelectionGateCode),
            )
            self.assertEqual(
                tuple(gate.status for gate in summary.selection_gates),
                (
                    SelectionGateStatus.BLOCKED,
                    SelectionGateStatus.BLOCKED,
                    SelectionGateStatus.BLOCKED,
                    SelectionGateStatus.NOT_EVALUABLE,
                    SelectionGateStatus.NOT_EVALUABLE,
                    SelectionGateStatus.NOT_EVALUABLE,
                    SelectionGateStatus.NOT_EVALUABLE,
                    SelectionGateStatus.NOT_EVALUABLE,
                ),
            )
            self.assertEqual(
                summary.selection_blocking_reasons,
                EXPECTED_EMPTY_BLOCKERS,
            )
            self.assertEqual(
                tuple(
                    gate.blocking_reason
                    for gate in summary.selection_gates
                    if gate.status is not SelectionGateStatus.PASSED
                ),
                summary.selection_blocking_reasons,
            )
            self.assertEqual(
                _gate(summary, SelectionGateCode.CANDIDATE_STRUCTURE).details,
                {
                    "candidate_target_schema_available": True,
                    "active_candidate_count": 0,
                    "active_research_hypothesis_count": 0,
                    "active_official_observation_count": 0,
                    "candidate_basis_partition_is_consistent": True,
                    "legacy_snapshot_count": 0,
                    "legacy_candidate_count": 0,
                    "legacy_rows_are_authoritative": False,
                    "legacy_rows_affect_gate": False,
                },
            )
            catalog_gate = _gate(
                summary,
                SelectionGateCode.CANDIDATE_2027_CATALOG,
            )
            self.assertEqual(catalog_gate.details["target_year_observation_count"], 0)
            self.assertEqual(catalog_gate.details["official_confirmed_global_count"], 0)
            self.assertFalse(
                catalog_gate.details["authoritative_candidate_set_available"]
            )

    def test_assessment_is_read_only_with_an_initialized_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            before = _table_row_counts(settings.database_path)

            first = application.assessment.summarize()
            middle = _table_row_counts(settings.database_path)
            second = application.assessment.summarize()
            after = _table_row_counts(settings.database_path)

            self.assertEqual(before, middle)
            self.assertEqual(middle, after)
            self.assertEqual(
                _gate_contract(first),
                _gate_contract(second),
            )
            self.assertEqual(
                first.selection_blocking_reasons,
                second.selection_blocking_reasons,
            )

    def test_legacy_decision_rows_never_satisfy_candidate_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            profile_id = application.assessment.initialize_default_profile(
                str(uuid.uuid4())
            )
            _insert_legacy_decision_rows(settings.database_path, profile_id)

            summary = application.assessment.summarize()
            structure_gate = _gate(
                summary,
                SelectionGateCode.CANDIDATE_STRUCTURE,
            )

            self.assertEqual(
                structure_gate.status,
                SelectionGateStatus.NOT_EVALUABLE,
            )
            self.assertEqual(
                structure_gate.blocking_reason,
                "ACTIVE_CANDIDATE_SET_EMPTY",
            )
            self.assertEqual(structure_gate.details["legacy_snapshot_count"], 1)
            self.assertEqual(structure_gate.details["legacy_candidate_count"], 1)
            self.assertFalse(structure_gate.details["legacy_rows_are_authoritative"])
            self.assertFalse(summary.is_score_window_ready)
            self.assertFalse(summary.is_selection_ready)
            self.assertIn(
                "ACTIVE_CANDIDATE_SET_EMPTY",
                summary.selection_blocking_reasons,
            )

    def test_research_candidate_passes_structure_but_not_catalog_and_retired_is_excluded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            identity = _candidate_identity()
            active_id = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=identity,
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.ACTIVE,
                    reason="只进入研究池，不冒充目标年度正式目录",
                ),
                str(uuid.uuid4()),
            )

            active_summary = application.assessment.summarize()
            active_structure = _gate(
                active_summary,
                SelectionGateCode.CANDIDATE_STRUCTURE,
            )
            active_catalog = _gate(
                active_summary,
                SelectionGateCode.CANDIDATE_2027_CATALOG,
            )
            self.assertEqual(active_structure.status, SelectionGateStatus.PASSED)
            self.assertEqual(active_structure.details["active_candidate_count"], 1)
            self.assertEqual(
                active_structure.details["active_research_hypothesis_count"],
                1,
            )
            self.assertEqual(active_catalog.status, SelectionGateStatus.NOT_EVALUABLE)
            self.assertEqual(active_catalog.details["active_official_confirmed_count"], 0)

            application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=identity,
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.RETIRED,
                    reason="退出当前研究池，历史版本仍保留",
                    supersedes_version_id=active_id,
                ),
                str(uuid.uuid4()),
            )
            retired_summary = application.assessment.summarize()
            retired_structure = _gate(
                retired_summary,
                SelectionGateCode.CANDIDATE_STRUCTURE,
            )
            self.assertEqual(
                retired_structure.status,
                SelectionGateStatus.NOT_EVALUABLE,
            )
            self.assertEqual(retired_structure.details["active_candidate_count"], 0)
            self.assertEqual(
                retired_structure.blocking_reason,
                "ACTIVE_CANDIDATE_SET_EMPTY",
            )

    def test_each_active_official_candidate_must_be_same_year_official_confirmed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            result = application.official_observations.add_observation(
                _official_2027_observation(),
                str(uuid.uuid4()),
            )
            self.assertEqual(result.strict_status, Strict22408Status.OFFICIAL_CONFIRMED)
            application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=_candidate_identity(),
                    target_basis=CandidateTargetBasis.OFFICIAL_OBSERVATION,
                    target_observation_id=result.observation_id,
                    action=CandidateTargetAction.ACTIVE,
                    reason="逐候选绑定目标年度正式目录观测",
                ),
                str(uuid.uuid4()),
            )

            summary = application.assessment.summarize()
            catalog = _gate(summary, SelectionGateCode.CANDIDATE_2027_CATALOG)
            self.assertEqual(
                _gate(summary, SelectionGateCode.CANDIDATE_STRUCTURE).status,
                SelectionGateStatus.PASSED,
            )
            self.assertEqual(catalog.status, SelectionGateStatus.PASSED)
            self.assertIsNone(catalog.blocking_reason)
            self.assertEqual(catalog.details["active_official_confirmed_count"], 1)
            self.assertFalse(summary.is_selection_ready)
            self.assertEqual(
                _gate(summary, SelectionGateCode.CANDIDATE_ORDINARY_QUOTA).status,
                SelectionGateStatus.NOT_EVALUABLE,
            )
            self.assertEqual(
                _gate(summary, SelectionGateCode.CANDIDATE_RETEST_CONTRACT).status,
                SelectionGateStatus.NOT_EVALUABLE,
            )
            self.assertEqual(
                _gate(summary, SelectionGateCode.CANDIDATE_FAIRNESS_REVIEW).status,
                SelectionGateStatus.NOT_EVALUABLE,
            )

    def test_official_candidate_with_non_strict_catalog_does_not_pass_catalog_gate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            observation = _official_2027_observation(english_code="201")
            result = application.official_observations.add_observation(
                observation,
                str(uuid.uuid4()),
            )
            self.assertEqual(result.strict_status, Strict22408Status.OFFICIAL_NON_STRICT)
            application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=_candidate_identity(),
                    target_basis=CandidateTargetBasis.OFFICIAL_OBSERVATION,
                    target_observation_id=result.observation_id,
                    action=CandidateTargetAction.ACTIVE,
                    reason="验证非22408正式目录不能通过候选目录门禁",
                ),
                str(uuid.uuid4()),
            )

            summary = application.assessment.summarize()
            catalog = _gate(summary, SelectionGateCode.CANDIDATE_2027_CATALOG)
            self.assertEqual(catalog.status, SelectionGateStatus.NOT_EVALUABLE)
            self.assertEqual(catalog.details["active_official_observation_count"], 1)
            self.assertEqual(catalog.details["active_official_confirmed_count"], 0)
            self.assertEqual(catalog.details["official_candidates_without_confirmation"], 1)

    def test_global_2027_official_confirmation_cannot_pass_candidate_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            result = application.official_observations.add_observation(
                _official_2027_observation(),
                str(uuid.uuid4()),
            )
            self.assertEqual(result.strict_status, Strict22408Status.OFFICIAL_CONFIRMED)

            summary = application.assessment.summarize()
            catalog_gate = _gate(
                summary,
                SelectionGateCode.CANDIDATE_2027_CATALOG,
            )

            self.assertEqual(
                catalog_gate.status,
                SelectionGateStatus.NOT_EVALUABLE,
            )
            self.assertEqual(
                catalog_gate.blocking_reason,
                "CANDIDATE_CATALOG_NOT_EVALUABLE",
            )
            self.assertEqual(catalog_gate.details["target_year_observation_count"], 1)
            self.assertEqual(catalog_gate.details["official_confirmed_global_count"], 1)
            self.assertEqual(catalog_gate.details["official_pending_global_count"], 0)
            self.assertFalse(
                catalog_gate.details["authoritative_candidate_set_available"]
            )
            self.assertFalse(summary.is_selection_ready)
            self.assertIn(
                "CANDIDATE_CATALOG_NOT_EVALUABLE",
                summary.selection_blocking_reasons,
            )


def _gate(summary, code: SelectionGateCode):
    matches = tuple(gate for gate in summary.selection_gates if gate.code is code)
    if len(matches) != 1:
        raise AssertionError(f"门禁{code.value}数量异常：{len(matches)}")
    return matches[0]


def _gate_contract(summary) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            gate.code,
            gate.status,
            gate.blocking_reason,
            dict(gate.details),
        )
        for gate in summary.selection_gates
    )


def _table_row_counts(database_path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(database_path)) as connection:
        table_names = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        )
        return {
            table_name: int(
                connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            )
            for table_name in table_names
        }


def _insert_legacy_decision_rows(database_path: Path, profile_id: int) -> None:
    now = "2026-08-02T00:00:00+00:00"
    with closing(sqlite3.connect(database_path)) as connection:
        school_id = int(
            connection.execute(
                """
                INSERT INTO schools(
                    canonical_name, display_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                ("legacy快照测试大学", "legacy快照测试大学", now, now),
            ).lastrowid
        )
        college_id = int(
            connection.execute(
                """
                INSERT INTO colleges(
                    school_id, canonical_name, display_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (school_id, "计算机学院", "计算机学院", now, now),
            ).lastrowid
        )
        project_id = int(
            connection.execute(
                """
                INSERT INTO projects(
                    identity_key, school_id, college_id, program_code,
                    program_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-decision-project",
                    school_id,
                    college_id,
                    "085404",
                    "计算机技术",
                    now,
                    now,
                ),
            ).lastrowid
        )
        snapshot_id = int(
            connection.execute(
                """
                INSERT INTO decision_snapshots(
                    profile_id, created_at, rule_version, mock_session_count,
                    total_mean, total_standard_deviation, conservative_total,
                    machine_test_level, official_catalog_as_of, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    now,
                    "legacy-untrusted",
                    99,
                    500.0,
                    0.0,
                    500.0,
                    "expert",
                    "2099-12-31",
                    "故意伪造得很完整，也不得成为权威候选结构",
                ),
            ).lastrowid
        )
        connection.execute(
            """
            INSERT INTO decision_candidates(
                snapshot_id, project_id, tier, reason, status
            ) VALUES (?, ?, 'match', ?, 'selected')
            """,
            (snapshot_id, project_id, "legacy候选行不可授权selection readiness"),
        )
        connection.commit()


def _candidate_identity() -> CandidateIdentityInput:
    return CandidateIdentityInput(
        school="测试大学",
        college="计算机学院",
        program_code="085404",
        program_name="计算机技术",
        study_mode="全日制",
    )


def _official_2027_observation(
    *,
    english_code: str = "204",
) -> OfficialProjectObservationInput:
    return OfficialProjectObservationInput(
        school="测试大学",
        college="计算机学院",
        program_code="085404",
        program_name="计算机技术",
        admission_year=2027,
        politics_code="101",
        english_code=english_code,
        math_code="302",
        professional_code="408",
        source_title="测试大学2027年硕士研究生招生专业目录",
        source_url="https://example.edu.cn/2027-catalog.pdf",
        source_institution="测试大学",
        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
        source_content_sha256=hashlib.sha256(b"synthetic-2027-catalog").hexdigest(),
        applicable_year=2027,
        published_date=date(2026, 8, 2),
        retrieved_date=date(2026, 8, 2),
        study_mode="全日制",
    )


if __name__ == "__main__":
    unittest.main()
