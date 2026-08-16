from __future__ import annotations

import tempfile
import unittest
import uuid
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from tests.support import REAL_ARCHIVE, build_test_application
from tests.integration.test_mock_exam_ledger_v2 import _explicit_bounds, _ledger

from chose_school.domain.enums import (
    EvidenceDocumentType,
    EvidenceGrade,
    MockInvalidReasonCode,
    Strict22408Status,
)
from chose_school.domain.models import (
    CatalogFilter,
    FactClaimInput,
    FactDerivationInput,
    SecondaryProjectObservationInput,
    SubjectVerificationInput,
)
from chose_school.domain.errors import StateConflictError, ValidationError


class VerificationAssessmentExportTest(unittest.TestCase):
    def test_catalog_defaults_to_resolved_facts_and_raw_values_require_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            secondary = application.secondary_observations.add_observation(
                SecondaryProjectObservationInput(
                    school="证据投影测试大学",
                    college="计算机学院",
                    program_code="085404",
                    program_name="计算机技术",
                    admission_year=2026,
                    source_title="二级来源科目摘要",
                    source_url="https://example.com/secondary-subjects",
                    source_institution="测试来源",
                    source_content_sha256="6" * 64,
                    applicable_year=2026,
                    published_date=date(2026, 4, 1),
                    retrieved_date=date(2026, 8, 13),
                    source_excerpt="目标项目列示101、204、302、408。",
                    project_identity_basis="同页列示学校、学院、专业代码和名称。",
                    politics_code="101",
                    english_code="204",
                    math_code="302",
                    professional_code="408",
                    study_mode="全日制",
                ),
                str(uuid.uuid4()),
            )
            raw_subject_id = secondary.observation_id

            raw_rows = application.catalog.list_catalog(
                CatalogFilter(limit=100_000, raw_imported=True)
            )
            resolved_rows = application.catalog.list_catalog(
                CatalogFilter(limit=100_000)
            )
            raw_by_id = {int(row["observation_id"]): row for row in raw_rows}
            resolved_by_id = {
                int(row["observation_id"]): row for row in resolved_rows
            }
            location_row = next(
                row
                for row in raw_rows
                if row["campus"] is not None or row["training_location"] is not None
            )
            location_id = int(location_row["observation_id"])
            self.assertEqual(
                resolved_by_id[location_id]["projection_mode"],
                "evidence_resolved",
            )
            self.assertEqual(
                raw_by_id[location_id]["projection_mode"],
                "raw_imported",
            )
            self.assertIsNone(resolved_by_id[location_id]["campus"])
            self.assertIsNone(resolved_by_id[location_id]["training_location"])
            self.assertIsNone(resolved_by_id[location_id]["evidence_grade"])
            self.assertIsNone(resolved_by_id[location_id]["official_source"])

            quota_row = next(
                row
                for row in raw_rows
                if row["effective_general_exam_quota"] is not None
            )
            observation_id = int(quota_row["observation_id"])
            self.assertIsNone(
                resolved_by_id[observation_id]["effective_general_exam_quota"]
            )
            self.assertIsNotNone(
                raw_by_id[observation_id]["effective_general_exam_quota"]
            )
            self.assertEqual(
                raw_by_id[raw_subject_id]["subject_politics_code"],
                "101",
            )
            self.assertIsNone(
                resolved_by_id[raw_subject_id]["subject_politics_code"]
            )

            first_claim = application.facts.add_claim(
                FactClaimInput(
                    observation_id=observation_id,
                    fact_key="quota.general_effective",
                    raw_value="17",
                    evidence_grade=EvidenceGrade.OFFICIAL,
                    source_title="正式普通统考名额公告",
                    source_url="https://example.edu/quota-17.pdf",
                    source_institution=str(quota_row["school"]),
                    source_document_type=EvidenceDocumentType.OFFICIAL_NOTICE,
                    source_content_sha256="7" * 64,
                    applicable_year=int(quota_row["admission_year"]),
                    published_date=date(2026, 3, 1),
                    retrieved_date=date(2026, 8, 13),
                    population_scope="目标项目普通统考",
                    statistic_scope="正式最终有效名额",
                ),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                first_claim,
                "官方附件直接列示同项目普通统考最终有效名额",
                str(uuid.uuid4()),
            )
            resolved_after_accept = {
                int(row["observation_id"]): row
                for row in application.catalog.list_catalog(
                    CatalogFilter(limit=100_000)
                )
            }
            self.assertEqual(
                resolved_after_accept[observation_id][
                    "effective_general_exam_quota"
                ],
                17,
            )

            second_claim = application.facts.add_claim(
                FactClaimInput(
                    observation_id=observation_id,
                    fact_key="quota.general_effective",
                    raw_value="3",
                    evidence_grade=EvidenceGrade.OFFICIAL,
                    source_title="独立专项名额公告",
                    source_url="https://example.edu/special-quota-3.pdf",
                    source_institution=str(quota_row["school"]),
                    source_document_type=EvidenceDocumentType.OFFICIAL_NOTICE,
                    source_content_sha256="8" * 64,
                    applicable_year=int(quota_row["admission_year"]),
                    published_date=date(2026, 3, 2),
                    retrieved_date=date(2026, 8, 13),
                    population_scope="目标项目独立专项",
                    statistic_scope="专项最终有效名额",
                ),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                second_claim,
                "该值属于另一人群口径，不能与普通统考折叠",
                str(uuid.uuid4()),
            )
            resolved_after_ambiguity = {
                int(row["observation_id"]): row
                for row in application.catalog.list_catalog(
                    CatalogFilter(limit=100_000)
                )
            }
            self.assertIsNone(
                resolved_after_ambiguity[observation_id][
                    "effective_general_exam_quota"
                ]
            )
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["resolved_catalog_subject_without_verification"], 0)
            self.assertEqual(doctor["resolved_catalog_location_without_unique_fact"], 0)
            self.assertEqual(doctor["resolved_catalog_numeric_without_unique_fact"], 0)
            self.assertEqual(doctor["status"], "ok")

    def test_assessment_query_has_no_hidden_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                before = (
                    connection.execute("SELECT COUNT(*) FROM applicant_profiles").fetchone()[0],
                    connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
                )
            summary = application.assessment.summarize()
            with closing(sqlite3.connect(database_path)) as connection:
                after = (
                    connection.execute("SELECT COUNT(*) FROM applicant_profiles").fetchone()[0],
                    connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
                )
            self.assertEqual(summary.session_count, 0)
            self.assertEqual(before, after)

    def test_field_claim_conflict_and_resolution_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            observation_id = int(
                application.catalog.list_catalog(CatalogFilter(limit=1))[0][
                    "observation_id"
                ]
            )
            common = {
                "observation_id": observation_id,
                "fact_key": "admission.general_count",
                "evidence_grade": EvidenceGrade.OFFICIAL,
                "source_institution": "测试大学",
                "source_document_type": EvidenceDocumentType.ADMISSION_LIST,
                "applicable_year": 2026,
                "published_date": date(2026, 4, 1),
                "retrieved_date": date(2026, 8, 1),
                "population_scope": "ordinary_general_exam",
                "statistic_scope": "project",
            }
            first_claim = application.facts.add_claim(
                FactClaimInput(
                    **common,
                    raw_value="107",
                    source_title="拟录取名单A",
                    source_url="https://example.edu/admit-a",
                    source_content_sha256="a" * 64,
                ),
                str(uuid.uuid4()),
            )
            second_claim = application.facts.add_claim(
                FactClaimInput(
                    **common,
                    raw_value="115",
                    source_title="拟录取名单B",
                    source_url="https://example.edu/admit-b",
                    source_content_sha256="b" * 64,
                ),
                str(uuid.uuid4()),
            )
            self.assertEqual(len(application.facts.list_conflicts(10)), 1)

            resolution_id = application.facts.resolve_claim(
                second_claim,
                "逐行排除专项后采用115口径",
                str(uuid.uuid4()),
            )
            self.assertGreater(resolution_id, 0)
            claims = application.facts.list_claims(observation_id)
            current = [row for row in claims if row["is_current_resolution"]]
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["claim_id"], second_claim)
            self.assertNotEqual(first_claim, second_claim)

            unresolve_trace_id = str(uuid.uuid4())
            unresolve_reason = "发现该汇总仍包含专项，等待普通统考口径复核"
            unresolve_resolution_id = application.facts.unresolve_claim(
                first_claim,
                unresolve_reason,
                unresolve_trace_id,
            )
            self.assertGreater(unresolve_resolution_id, resolution_id)
            claims_after_unresolve = application.facts.list_claims(observation_id)
            self.assertEqual(
                {row["claim_id"] for row in claims_after_unresolve},
                {first_claim, second_claim},
            )
            self.assertFalse(
                any(row["is_current_resolution"] for row in claims_after_unresolve)
            )

            with closing(sqlite3.connect(application.database.database_path)) as connection:
                resolution_rows = connection.execute(
                    """
                    SELECT resolution_action, selected_claim_id, reason, trace_id
                    FROM fact_resolutions
                    ORDER BY id
                    """
                ).fetchall()
                remaining_claim_count = connection.execute(
                    "SELECT COUNT(*) FROM fact_claims WHERE id IN (?, ?)",
                    (first_claim, second_claim),
                ).fetchone()[0]
                audit_event = connection.execute(
                    """
                    SELECT event_type, entity_type, entity_id, trace_id, payload_json
                    FROM audit_events
                    WHERE event_type = 'fact_resolution_unresolved'
                    """
                ).fetchone()
            self.assertEqual(
                [row[0] for row in resolution_rows],
                ["accept", "unresolved"],
            )
            self.assertIsNone(resolution_rows[-1][1])
            self.assertEqual(resolution_rows[-1][2], unresolve_reason)
            self.assertEqual(resolution_rows[-1][3], unresolve_trace_id)
            self.assertEqual(remaining_claim_count, 2)
            self.assertEqual(audit_event[0], "fact_resolution_unresolved")
            self.assertEqual(audit_event[1], "fact_resolution")
            self.assertEqual(audit_event[2], str(unresolve_resolution_id))
            self.assertEqual(audit_event[3], unresolve_trace_id)
            self.assertIn(f'"identity_claim_id": {first_claim}', audit_event[4])

            with self.assertRaises(ValidationError) as overclaim:
                application.facts.add_claim(
                    FactClaimInput(
                        observation_id=observation_id,
                        fact_key=(
                            "admission."
                            "final_list_first_choice_fulltime_non_directed_count"
                        ),
                        raw_value="22",
                        evidence_grade=EvidenceGrade.OFFICIAL,
                        source_title="无专项字段的最终名单",
                        source_url="https://example.edu/non-directed-list.pdf",
                        source_institution="测试大学",
                        source_document_type=EvidenceDocumentType.ADMISSION_LIST,
                        source_content_sha256="d" * 64,
                        applicable_year=2026,
                        published_date=date(2026, 4, 2),
                        retrieved_date=date(2026, 8, 13),
                        population_scope="ordinary_general_exam",
                        statistic_scope="project",
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                overclaim.exception.error_code,
                "FACT_SCOPE_OVERCLAIMS_ORDINARY_GENERAL_EXAM",
            )

            with self.assertRaises(ValidationError) as chinese_overclaim:
                application.facts.add_claim(
                    FactClaimInput(
                        observation_id=observation_id,
                        fact_key=(
                            "admission."
                            "final_list_first_choice_fulltime_non_directed_count"
                        ),
                        raw_value="22",
                        evidence_grade=EvidenceGrade.OFFICIAL,
                        source_title="无专项字段的最终名单",
                        source_url="https://example.edu/non-directed-list.pdf",
                        source_institution="测试大学",
                        source_document_type=EvidenceDocumentType.ADMISSION_LIST,
                        source_content_sha256="d" * 64,
                        applicable_year=2026,
                        published_date=date(2026, 4, 2),
                        retrieved_date=date(2026, 8, 13),
                        population_scope="目标项目普通统考拟录取考生",
                        statistic_scope="项目",
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                chinese_overclaim.exception.error_code,
                "FACT_SCOPE_OVERCLAIMS_ORDINARY_GENERAL_EXAM",
            )

            derived_common = {
                "observation_id": observation_id,
                "fact_key": "quota.plan_minus_received_recommendation",
                "raw_value": "22",
                "evidence_grade": EvidenceGrade.OFFICIAL_MIXED,
                "source_title": "同一正式文件中的总计划与已接收推免",
                "source_url": "https://example.edu/retest-plan.pdf",
                "source_institution": "测试大学",
                "source_document_type": EvidenceDocumentType.RETEST_POLICY,
                "source_content_sha256": "e" * 64,
                "applicable_year": 2026,
                "published_date": date(2026, 4, 1),
                "retrieved_date": date(2026, 8, 13),
                "population_scope": "目标项目复试阶段计划（专项未拆分）",
                "statistic_scope": "同一文件列示总计划25与已接收推免3的算术余量",
            }
            first_derived_claim = application.facts.add_claim(
                FactClaimInput(
                    **derived_common,
                    derivation=FactDerivationInput(
                        operator="subtract",
                        left_fact_key="quota.total_plan",
                        left_integer_value=25,
                        right_fact_key="quota.recommendation_received",
                        right_integer_value=3,
                    ),
                    note="25-3=22；两个操作数均来自该复试细则。",
                ),
                str(uuid.uuid4()),
            )
            replayed_derived_claim = application.facts.add_claim(
                FactClaimInput(
                    **derived_common,
                    derivation=FactDerivationInput(
                        operator="subtract",
                        left_fact_key="quota.total_plan",
                        left_integer_value=25,
                        right_fact_key="quota.recommendation_received",
                        right_integer_value=3,
                    ),
                    note="25-3=22；两个操作数均来自该复试细则。",
                ),
                str(uuid.uuid4()),
            )
            corrected_derivation_claim = application.facts.add_claim(
                FactClaimInput(
                    **derived_common,
                    derivation=FactDerivationInput(
                        operator="subtract",
                        left_fact_key="quota.total_plan",
                        left_integer_value=30,
                        right_fact_key="quota.recommendation_received",
                        right_integer_value=8,
                    ),
                    note="30-8=22；这是不同的操作数说明，必须形成新主张。",
                ),
                str(uuid.uuid4()),
            )
            self.assertEqual(replayed_derived_claim, first_derived_claim)
            self.assertNotEqual(corrected_derivation_claim, first_derived_claim)

            derived_rows = application.facts.list_claims(observation_id)
            stored_first = next(
                row for row in derived_rows if row["claim_id"] == first_derived_claim
            )
            self.assertEqual(stored_first["derivation_operator"], "subtract")
            self.assertEqual(
                stored_first["derivation_left_fact_key"],
                "quota.total_plan",
            )
            self.assertEqual(stored_first["derivation_left_value_integer"], 25)
            self.assertEqual(
                stored_first["derivation_right_fact_key"],
                "quota.recommendation_received",
            )
            self.assertEqual(stored_first["derivation_right_value_integer"], 3)

            invalid_derivations = (
                (
                    None,
                    "DERIVED_FACT_METADATA_REQUIRED",
                ),
                (
                    FactDerivationInput(
                        operator="subtract",
                        left_fact_key="quota.total_plan",
                        left_integer_value=25,
                        right_fact_key="quota.recommendation_received",
                        right_integer_value=2,
                    ),
                    "DERIVATION_RESULT_MISMATCH",
                ),
                (
                    FactDerivationInput(
                        operator="add",
                        left_fact_key="quota.total_plan",
                        left_integer_value=25,
                        right_fact_key="quota.recommendation_received",
                        right_integer_value=3,
                    ),
                    "INVALID_DERIVATION_OPERATOR",
                ),
                (
                    FactDerivationInput(
                        operator="subtract",
                        left_fact_key="quota.exam_catalog_plan",
                        left_integer_value=25,
                        right_fact_key="quota.recommendation_received",
                        right_integer_value=3,
                    ),
                    "INVALID_DERIVATION_OPERANDS",
                ),
            )
            for derivation, expected_error_code in invalid_derivations:
                with self.subTest(expected_error_code=expected_error_code):
                    with self.assertRaises(ValidationError) as invalid_formula:
                        application.facts.add_claim(
                            FactClaimInput(
                                **derived_common,
                                derivation=derivation,
                                note="25-3=22；用于拒绝无效结构的测试。",
                            ),
                            str(uuid.uuid4()),
                        )
                    self.assertEqual(
                        invalid_formula.exception.error_code,
                        expected_error_code,
                    )

            with self.assertRaises(ValidationError) as non_derived_metadata:
                application.facts.add_claim(
                    FactClaimInput(
                        **common,
                        raw_value="115",
                        source_title="非推导事实拒绝推导元数据",
                        source_url="https://example.edu/non-derived",
                        source_content_sha256="f" * 64,
                        derivation=FactDerivationInput(
                            operator="subtract",
                            left_fact_key="quota.total_plan",
                            left_integer_value=25,
                            right_fact_key="quota.recommendation_received",
                            right_integer_value=3,
                        ),
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                non_derived_metadata.exception.error_code,
                "NON_DERIVED_FACT_HAS_DERIVATION",
            )

            with self.assertRaises(ValidationError):
                application.facts.add_claim(
                    FactClaimInput(
                        **common,
                        raw_value="115(另一口径107)",
                        source_title="复合值",
                        source_url="https://example.edu/compound",
                        source_content_sha256="c" * 64,
                    ),
                    str(uuid.uuid4()),
                )

    def test_append_only_verification_detects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            first_observation = application.catalog.list_catalog(
                CatalogFilter(limit=1)
            )[0]
            observation_id = int(first_observation["observation_id"])
            observation_school = str(first_observation["school"])
            retrieved = date(2026, 8, 1)

            verification_id, status = application.verification.verify(
                SubjectVerificationInput(
                    observation_id=observation_id,
                    politics_code="101",
                    english_code="204",
                    math_code="302",
                    professional_code="408",
                    source_title="正式目录",
                    source_url="https://example.edu/catalog-1",
                    source_institution=observation_school,
                    source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                    source_content_sha256="1" * 64,
                    applicable_year=int(first_observation["admission_year"]),
                    published_date=retrieved,
                    retrieved_date=retrieved,
                ),
                str(uuid.uuid4()),
            )
            self.assertGreater(verification_id, 0)
            self.assertEqual(status, Strict22408Status.OFFICIAL_CONFIRMED)
            confirmed = application.catalog.list_catalog(
                CatalogFilter(
                    strict_status=Strict22408Status.OFFICIAL_CONFIRMED,
                    limit=10,
                )
            )
            self.assertEqual(len(confirmed), 1)
            self.assertEqual(
                (
                    confirmed[0]["subject_politics_code"],
                    confirmed[0]["subject_english_code"],
                    confirmed[0]["subject_math_code"],
                    confirmed[0]["subject_professional_code"],
                ),
                ("101", "204", "302", "408"),
            )
            summary = application.catalog.get_summary()
            effective_statuses = {
                row["value"]: row["count"]
                for row in summary["evidence_status_distribution"]
            }
            imported_statuses = {
                row["value"]: row["count"]
                for row in summary["imported_evidence_status_distribution"]
            }
            self.assertEqual(effective_statuses["official_confirmed"], 1)
            self.assertNotIn("official_confirmed", imported_statuses)

            application.verification.verify(
                SubjectVerificationInput(
                    observation_id=observation_id,
                    politics_code="101",
                    english_code="204",
                    math_code="302",
                    professional_code="408",
                    source_title="正式目录镜像",
                    source_url="https://example.edu/catalog-same-subjects",
                    source_institution=observation_school,
                    source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                    source_content_sha256="3" * 64,
                    applicable_year=int(first_observation["admission_year"]),
                    published_date=retrieved,
                    retrieved_date=retrieved,
                ),
                str(uuid.uuid4()),
            )
            same_combination = application.catalog.list_catalog(
                CatalogFilter(
                    strict_status=Strict22408Status.OFFICIAL_CONFIRMED,
                    limit=10,
                )
            )
            self.assertEqual(len(same_combination), 1)
            self.assertEqual(
                same_combination[0]["subject_professional_code"],
                "408",
            )

            with self.assertRaises(StateConflictError):
                application.verification.verify(
                    SubjectVerificationInput(
                        observation_id=observation_id,
                        politics_code="101",
                        english_code="201",
                        math_code="301",
                        professional_code="408",
                        source_title="正式目录",
                        source_url="https://example.edu/catalog-1",
                        source_institution=observation_school,
                        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                        source_content_sha256="1" * 64,
                        applicable_year=int(first_observation["admission_year"]),
                        published_date=retrieved,
                        retrieved_date=retrieved,
                    ),
                    str(uuid.uuid4()),
                )

            application.verification.verify(
                SubjectVerificationInput(
                    observation_id=observation_id,
                    politics_code="101",
                    english_code="201",
                    math_code="301",
                    professional_code="408",
                    source_title="另一份正式目录",
                    source_url="https://example.edu/catalog-2",
                    source_institution=observation_school,
                    source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                    source_content_sha256="2" * 64,
                    applicable_year=int(first_observation["admission_year"]),
                    published_date=retrieved,
                    retrieved_date=retrieved,
                ),
                str(uuid.uuid4()),
            )
            conflicted = application.catalog.list_catalog(CatalogFilter(limit=10))
            self.assertEqual(conflicted[0]["strict_22408_status"], "conflict")
            self.assertIsNone(conflicted[0]["subject_politics_code"])
            self.assertIsNone(conflicted[0]["subject_english_code"])
            self.assertIsNone(conflicted[0]["subject_math_code"])
            self.assertIsNone(conflicted[0]["subject_professional_code"])
            conflicts = application.catalog.list_catalog(
                CatalogFilter(strict_status=Strict22408Status.CONFLICT, limit=10)
            )
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0]["observation_id"], observation_id)

    def test_mock_assessment_and_deterministic_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application, _ = build_test_application(root)
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            mock_scores = (
                (date(2026, 9, 1), "卷一", 60, 60, 100, 110),
                (date(2026, 9, 8), "卷二", 60, 65, 105, 110),
                (date(2026, 9, 15), "卷三", 60, 70, 110, 110),
                (date(2026, 9, 22), "卷四", 65, 70, 115, 110),
                (date(2026, 9, 29), "卷五", 65, 75, 120, 110),
            )
            for taken_on, paper, politics, english, math, cs408 in mock_scores:
                application.assessment.add_mock_exam_ledger(
                    _ledger(
                        taken_on,
                        paper,
                        _explicit_bounds((politics, english, math, cs408)),
                    ),
                    str(uuid.uuid4()),
                )
            summary = application.assessment.summarize()
            self.assertEqual(summary.session_count, 5)
            self.assertTrue(summary.is_decision_ready)
            self.assertTrue(summary.is_score_window_ready)
            self.assertFalse(summary.is_selection_ready)
            self.assertEqual(summary.total_mean, 350.0)
            self.assertEqual(summary.total_standard_deviation, 15.81)
            self.assertEqual(summary.conservative_total, 340.0)

            first_export = root / "first.csv"
            second_export = root / "second.csv"
            self.assertEqual(
                application.catalog_export.export_catalog(first_export),
                167,
            )
            self.assertEqual(
                application.catalog_export.export_catalog(second_export),
                167,
            )
            self.assertEqual(first_export.read_bytes(), second_export.read_bytes())

    def test_assessment_uses_latest_five_in_taken_on_and_id_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            strict_scores = (
                (date(2026, 9, 1), "Z卷", 80, 80, 120, 120),
                (date(2026, 9, 4), "A卷", 20, 20, 30, 30),
                (date(2026, 9, 8), "卷三", 40, 40, 60, 60),
                (date(2026, 9, 15), "卷四", 60, 60, 90, 90),
                (date(2026, 9, 22), "卷五", 70, 70, 105, 105),
                (date(2026, 9, 29), "卷六", 80, 80, 110, 110),
            )
            for index, (taken_on, paper, politics, english, math, cs408) in enumerate(
                strict_scores
            ):
                application.assessment.add_mock_exam_ledger(
                    _ledger(
                        taken_on,
                        paper,
                        _explicit_bounds((politics, english, math, cs408)),
                    ),
                    str(uuid.uuid4()),
                )
                if index == 3:
                    incomplete_summary = application.assessment.summarize()
                    self.assertEqual(incomplete_summary.session_count, 4)
                    self.assertFalse(incomplete_summary.is_decision_ready)
                    self.assertIsNone(incomplete_summary.conservative_total)

            application.assessment.add_mock_exam_ledger(
                _ledger(
                    date(2026, 10, 6),
                    "非严格训练卷",
                    _explicit_bounds((100, 100, 150, 150)),
                    strict_timed=False,
                    invalid_reason_code=MockInvalidReasonCode.NOT_STRICT_TIMED,
                    invalid_reason_note="非严格训练卷仅留作训练记录，不进入正式套卷窗口",
                ),
                str(uuid.uuid4()),
            )

            summary = application.assessment.summarize()
            self.assertEqual(summary.session_count, 5)
            self.assertTrue(summary.is_decision_ready)
            self.assertTrue(summary.is_score_window_ready)
            self.assertFalse(summary.is_selection_ready)
            self.assertEqual(summary.total_mean, 266.0)
            self.assertEqual(summary.total_standard_deviation, 115.24)
            self.assertEqual(summary.conservative_total, 200.0)
            self.assertEqual(
                summary.subject_means,
                {
                    "politics_score": 54.0,
                    "english_score": 54.0,
                    "math_score": 79.0,
                    "computer_science_score": 79.0,
                },
            )


if __name__ == "__main__":
    unittest.main()
