from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from tests.support import REPOSITORY_ROOT  # ensures src is on sys.path

from chose_school.domain.candidate_model import (
    CandidateIdentityInput,
    CandidateProfileFitDimensionInput,
    CandidateProfileFitGapInput,
    CandidateProfileFitReviewInput,
    CandidateStrategyBucket,
    CandidateTargetAction,
    CandidateTargetBasis,
    CandidateTargetVersionInput,
    ComparabilityConclusion,
    ComparabilityDimensionInput,
    ComparabilityEvidenceReference,
    ComparabilityEvidenceRole,
    IdentityDimensionConclusion,
    IdentityDimensionDecision,
    KnownPreferenceFitConclusion,
    ProfileFitDimensionStatus,
    ProfileFitGapImpact,
    ProfileFitGapStatus,
    ProjectHistoryComparabilityReviewInput,
    SpecialPlanHandling,
)
from chose_school.domain.enums import (
    PreferenceAcceptanceLevel,
    PreferenceDimension,
)
from chose_school.domain.models import PreferenceEventInput
from tests.support import build_test_application


class CandidateModelStructureTests(unittest.TestCase):
    def test_migration_is_empty_and_tall_view_exposes_full_lineage(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            with sqlite3.connect(settings.database_path) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM candidate_target_versions"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM project_history_comparability_reviews"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM candidate_profile_fit_reviews"
                    ).fetchone()[0],
                    0,
                )
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(v_current_resolved_fact_evidence)"
                    )
                }
            self.assertTrue(
                {
                    "source_id",
                    "source_content_sha256",
                    "source_document_type",
                    "source_url",
                    "population_scope",
                    "statistic_scope",
                    "value_integer",
                    "value_decimal",
                    "derivation_operator",
                    "sample_size",
                    "calculation_method_key",
                    "calculation_input_sha256",
                }.issubset(columns)
            )
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["candidate_identity_hash_mismatch"], 0)
            self.assertEqual(doctor["comparability_contract_hash_mismatch"], 0)

    def test_research_identity_is_cross_database_canonical_and_chain_current(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            identity = CandidateIdentityInput(
                school="示例大学",
                college="计算机学院",
                program_code="085404",
                program_name="计算机技术",
                direction="不区分研究方向",
                campus="主校区",
                training_location="示例市",
                study_mode="全日制",
                training_type="普通培养",
                admission_type="硕士",
                degree_type="专业学位",
                training_arrangement="校本部培养",
            )
            first = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=identity,
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.ACTIVE,
                    reason="建立研究池候选，不冒充目标年度官方目录",
                ),
                str(uuid.uuid4()),
            )
            second = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=identity,
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.RETIRED,
                    reason="退出当前研究池但保留历史",
                    supersedes_version_id=first,
                ),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM candidate_target_versions ORDER BY id"
                ).fetchall()
                current = connection.execute(
                    "SELECT id, action FROM v_current_candidate_target_versions"
                ).fetchall()
                active_count = connection.execute(
                    "SELECT COUNT(*) FROM v_active_candidate_targets"
                ).fetchone()[0]
                audit_count = connection.execute(
                    "SELECT COUNT(*) FROM audit_events "
                    "WHERE event_type='candidate_target_version_added'"
                ).fetchone()[0]
            self.assertEqual([row["target_project_id"] for row in rows], [None, None])
            self.assertEqual([row["target_observation_id"] for row in rows], [None, None])
            self.assertEqual(rows[0]["candidate_key"], rows[1]["candidate_key"])
            self.assertEqual(rows[1]["supersedes_version_id"], first)
            self.assertEqual([tuple(row) for row in current], [(second, "retired")])
            self.assertEqual(active_count, 0)
            self.assertEqual(audit_count, 2)
            canonical = json.dumps(
                json.loads(rows[0]["identity_canonical_json"]),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            self.assertEqual(canonical, rows[0]["identity_canonical_json"])
            self.assertEqual(
                hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                rows[0]["identity_canonical_sha256"],
            )
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")

    def test_database_rejects_cross_target_review_chain(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            target_id = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=CandidateIdentityInput(
                        school="示例大学",
                        college="计算机学院",
                        program_code="085404",
                        program_name="计算机技术",
                    ),
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.ACTIVE,
                    reason="只测试版本身份",
                ),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                target = connection.execute(
                    "SELECT * FROM candidate_target_versions WHERE id=?", (target_id,)
                ).fetchone()
                self.assertIsNotNone(target)
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM project_history_comparability_reviews"
                    ).fetchone()[0],
                    0,
                )
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError,
                    "append-only",
                ):
                    connection.execute(
                        "UPDATE candidate_target_versions SET target_project_id=1 WHERE id=?",
                        (target_id,),
                    )

    def test_doctor_recomputes_canonical_hashes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            target_id = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=CandidateIdentityInput(
                        school="示例大学",
                        college="计算机学院",
                        program_code="085404",
                        program_name="计算机技术",
                    ),
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.ACTIVE,
                    reason="验证 Python 侧规范哈希重算",
                ),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                connection.execute("DROP TRIGGER protect_candidate_target_versions_update")
                connection.execute(
                    "UPDATE candidate_target_versions "
                    "SET identity_canonical_sha256=?, candidate_key=? WHERE id=?",
                    ("0" * 64, "candidate-v1:" + "0" * 64, target_id),
                )
                connection.commit()
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "error")
            self.assertEqual(doctor["candidate_identity_hash_mismatch"], 1)

    def test_profile_fit_review_freezes_current_profile_without_assigning_role(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            target_id = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=CandidateIdentityInput(
                        school="示例大学",
                        college="计算机学院",
                        program_code="085404",
                        program_name="计算机技术",
                    ),
                    target_basis=CandidateTargetBasis.RESEARCH_HYPOTHESIS,
                    action=CandidateTargetAction.ACTIVE,
                    reason="建立仅供证据研究的画像适配目标",
                ),
                str(uuid.uuid4()),
            )
            first = application.candidate_model.add_profile_fit_review(
                _profile_fit_review_input(target_id),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                connection.row_factory = sqlite3.Row
                active = connection.execute(
                    "SELECT * FROM v_active_candidate_profile_fit_reviews"
                ).fetchone()
                history_window = connection.execute(
                    "SELECT * FROM v_candidate_history_window_coverage"
                ).fetchone()
            self.assertEqual(active["id"], first)
            self.assertEqual(active["output_scope"], "research_only")
            self.assertEqual(active["probability_status"], "not_estimated")
            self.assertEqual(active["is_input_snapshot_current"], 1)
            self.assertEqual(history_window["history_coverage_status"], "none")
            self.assertEqual(history_window["score_history_support"], 0)
            self.assertEqual(history_window["history_stability_support"], 0)
            self.assertEqual(history_window["admission_role_is_established"], 0)

            application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                    subject_key="985_priority_211_hedge",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    value={},
                    note="测试当前偏好水位变化",
                ),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT is_input_snapshot_current "
                        "FROM v_active_candidate_profile_fit_reviews"
                    ).fetchone()[0],
                    0,
                )
            second = application.candidate_model.add_profile_fit_review(
                _profile_fit_review_input(target_id, supersedes_review_id=first),
                str(uuid.uuid4()),
            )
            current = application.candidate_model.list_profile_fit_reviews(target_id)
            history = application.candidate_model.list_profile_fit_reviews(
                target_id, include_history=True
            )
            self.assertEqual([item["id"] for item in current], [second])
            self.assertEqual([item["id"] for item in history], [first, second])
            self.assertEqual(
                current[0]["input_snapshot"]["preference_event_ids"], [1]
            )
            with sqlite3.connect(settings.database_path) as connection:
                with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                    connection.execute(
                        "UPDATE candidate_profile_fit_reviews SET summary='x' "
                        "WHERE id=?",
                        (second,),
                    )
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["profile_fit_contract_hash_mismatch"], 0)
            self.assertEqual(doctor["profile_fit_missing_audit"], 0)

    def test_comparable_history_without_both_year_strict_22408_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            historical, target_observation, historical_source, target_source = (
                _insert_split_project_observations(
                    settings.database_path,
                    historical_status="unverified",
                )
            )
            identity = _complete_candidate_identity()
            target_id = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=identity,
                    target_basis=CandidateTargetBasis.OFFICIAL_OBSERVATION,
                    target_observation_id=target_observation,
                    action=CandidateTargetAction.ACTIVE,
                    reason="验证跨年四码连续性必须双侧正式确认",
                ),
                str(uuid.uuid4()),
            )
            application.candidate_model.add_comparability_review(
                ProjectHistoryComparabilityReviewInput(
                    candidate_target_version_id=target_id,
                    historical_observation_id=historical,
                    conclusion=ComparabilityConclusion.COMPARABLE,
                    dimensions=_matching_comparability_dimensions(),
                    evidence=(
                        ComparabilityEvidenceReference(
                            source_id=target_source,
                            role=ComparabilityEvidenceRole.TARGET,
                        ),
                        ComparabilityEvidenceReference(
                            source_id=historical_source,
                            role=ComparabilityEvidenceRole.HISTORICAL,
                        ),
                    ),
                    summary="身份字段相同，但历史年度四码并未正式确认。",
                ),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                connection.row_factory = sqlite3.Row
                year = connection.execute(
                    "SELECT * FROM v_candidate_history_year_coverage "
                    "WHERE historical_year=2026"
                ).fetchone()
                window = connection.execute(
                    "SELECT * FROM v_candidate_history_window_coverage"
                ).fetchone()
            self.assertEqual(year["history_year_status"], "invalid_subject_contract")
            self.assertEqual(year["subject_contract_valid"], 0)
            self.assertEqual(window["score_history_support"], 0)
            self.assertEqual(window["history_stability_support"], 0)
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "error")
            self.assertEqual(doctor["comparability_subject_contract_invalid"], 1)

    def test_comparable_can_bridge_split_project_rows_with_explicit_dimensions(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            historical_observation, target_observation, historical_source, target_source = (
                _insert_split_project_observations(settings.database_path)
            )
            identity = CandidateIdentityInput(
                school="示例大学",
                college="计算机学院",
                program_code="085404",
                program_name="计算机技术",
                direction="不区分研究方向",
                campus="主校区",
                training_location="示例市",
                study_mode="全日制",
                training_type="普通培养",
                admission_type="硕士",
                degree_type="专业学位",
                training_arrangement="校本部培养",
            )
            target_id = application.candidate_model.add_candidate_target_version(
                CandidateTargetVersionInput(
                    target_year=settings.target_exam_year,
                    identity=identity,
                    target_basis=CandidateTargetBasis.OFFICIAL_OBSERVATION,
                    target_observation_id=target_observation,
                    action=CandidateTargetAction.ACTIVE,
                    reason="绑定同年度官方招生目录观测",
                ),
                str(uuid.uuid4()),
            )
            review_id = application.candidate_model.add_comparability_review(
                ProjectHistoryComparabilityReviewInput(
                    candidate_target_version_id=target_id,
                    historical_observation_id=historical_observation,
                    conclusion=ComparabilityConclusion.COMPARABLE,
                    dimensions=ComparabilityDimensionInput(
                        population_scope="ordinary_general_exam",
                        statistic_scope="project",
                        special_plan_handling=SpecialPlanHandling.EXCLUDED,
                        fact_keys=("score.initial.q25", "score.initial.median"),
                        identity_decisions=tuple(
                            IdentityDimensionDecision(
                                dimension=dimension,
                                conclusion=IdentityDimensionConclusion.MATCH,
                                rationale="规范字段逐项相同",
                            )
                            for dimension in (
                                "school",
                                "college",
                                "program_code",
                                "program_name",
                                "direction",
                                "campus",
                                "training_location",
                                "study_mode",
                                "training_type",
                                "admission_type",
                                "degree_type",
                                "training_arrangement",
                            )
                        ),
                    ),
                    evidence=(
                        ComparabilityEvidenceReference(
                            source_id=target_source,
                            role=ComparabilityEvidenceRole.TARGET,
                        ),
                        ComparabilityEvidenceReference(
                            source_id=historical_source,
                            role=ComparabilityEvidenceRole.HISTORICAL,
                        ),
                    ),
                    summary="两个本地项目行虽然 ID 不同，但十二项现实身份维度完全一致。",
                ),
                str(uuid.uuid4()),
            )
            with sqlite3.connect(settings.database_path) as connection:
                target_project = connection.execute(
                    "SELECT project_id FROM project_year_observations WHERE id=?",
                    (target_observation,),
                ).fetchone()[0]
                historical_project = connection.execute(
                    "SELECT project_id FROM project_year_observations WHERE id=?",
                    (historical_observation,),
                ).fetchone()[0]
                review = connection.execute(
                    "SELECT * FROM project_history_comparability_reviews WHERE id=?",
                    (review_id,),
                ).fetchone()
            self.assertNotEqual(target_project, historical_project)
            self.assertEqual(review[4], "comparable")
            self.assertEqual(application.catalog.doctor()["status"], "ok")


def _profile_fit_review_input(
    candidate_target_version_id: int,
    *,
    supersedes_review_id: int | None = None,
) -> CandidateProfileFitReviewInput:
    return CandidateProfileFitReviewInput(
        candidate_target_version_id=candidate_target_version_id,
        strategy_bucket=CandidateStrategyBucket.PRIORITY_985_RESEARCH,
        known_preference_fit=KnownPreferenceFitConclusion.CONDITIONAL,
        dimensions=tuple(
            CandidateProfileFitDimensionInput(
                dimension=dimension,
                status=ProfileFitDimensionStatus.NOT_EVALUABLE,
                rationale="测试夹具未提供该维度的候选年度事实。",
            )
            for dimension in (
                "institution",
                "program_code",
                "region",
                "training_location",
                "tuition",
                "joint_training",
                "retest_format",
                "school_tier_strategy",
                "admission_fairness",
                "preparation_timing",
            )
        ),
        evidence_gaps=(
            CandidateProfileFitGapInput(
                code="target_year_catalog",
                status=ProfileFitGapStatus.MISSING,
                impact=ProfileFitGapImpact.SELECTION_GATE,
                rationale="研究假设尚未绑定目标年度正式目录。",
            ),
        ),
        summary="仅确认进入研究池；不产生报考角色或录取概率。",
        supersedes_review_id=supersedes_review_id,
    )


def _complete_candidate_identity() -> CandidateIdentityInput:
    return CandidateIdentityInput(
        school="示例大学",
        college="计算机学院",
        program_code="085404",
        program_name="计算机技术",
        direction="不区分研究方向",
        campus="主校区",
        training_location="示例市",
        study_mode="全日制",
        training_type="普通培养",
        admission_type="硕士",
        degree_type="专业学位",
        training_arrangement="校本部培养",
    )


def _matching_comparability_dimensions() -> ComparabilityDimensionInput:
    return ComparabilityDimensionInput(
        population_scope="ordinary_general_exam",
        statistic_scope="project",
        special_plan_handling=SpecialPlanHandling.EXCLUDED,
        fact_keys=("score.initial.q25", "score.initial.median"),
        identity_decisions=tuple(
            IdentityDimensionDecision(
                dimension=dimension,
                conclusion=IdentityDimensionConclusion.MATCH,
                rationale="规范字段逐项相同",
            )
            for dimension in (
                "school",
                "college",
                "program_code",
                "program_name",
                "direction",
                "campus",
                "training_location",
                "study_mode",
                "training_type",
                "admission_type",
                "degree_type",
                "training_arrangement",
            )
        ),
    )


def _insert_split_project_observations(
    database_path: Path,
    historical_status: str = "official_confirmed",
) -> tuple[int, int, int, int]:
    timestamp = "2026-08-13T00:00:00+00:00"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO import_batches(
                id, trace_id, source_name, source_path, source_sha256,
                importer_version, status, started_at, completed_at
            ) VALUES ('candidate-fixture', ?, 'candidate-fixture', 'memory://fixture',
                      ?, 'test', 'succeeded', ?, ?)
            """,
            (str(uuid.uuid4()), "a" * 64, timestamp, timestamp),
        )
        school_id = connection.execute(
            "INSERT INTO schools(canonical_name, display_name, created_at, updated_at) "
            "VALUES ('示例大学', '示例大学', ?, ?) RETURNING id",
            (timestamp, timestamp),
        ).fetchone()[0]
        college_id = connection.execute(
            "INSERT INTO colleges(school_id, canonical_name, display_name, created_at, updated_at) "
            "VALUES (?, '计算机学院', '计算机学院', ?, ?) RETURNING id",
            (school_id, timestamp, timestamp),
        ).fetchone()[0]
        observations: list[int] = []
        sources: list[int] = []
        for index, year in enumerate((2026, 2027), start=1):
            source_file = connection.execute(
                """
                INSERT INTO source_files(
                    batch_id, archive_member, content_sha256, header_json,
                    expected_column_count, row_count
                ) VALUES ('candidate-fixture', ?, ?, '[]', 1, 1)
                RETURNING id
                """,
                (f"{year}.csv", str(index) * 64),
            ).fetchone()[0]
            raw_id = connection.execute(
                """
                INSERT INTO raw_catalog_rows(
                    source_file_id, source_row_number, row_sha256, raw_json,
                    raw_cells_json, cell_count, expected_cell_count, imported_at
                ) VALUES (?, 2, ?, '{}', '[]', 1, 1, ?)
                RETURNING id
                """,
                (source_file, str(index + 2) * 64, timestamp),
            ).fetchone()[0]
            project_id = connection.execute(
                """
                INSERT INTO projects(
                    identity_key, school_id, college_id, program_code,
                    program_name, direction, campus, training_location,
                    study_mode, training_type_raw, admission_type, degree_type,
                    training_arrangement, created_at, updated_at
                ) VALUES (?, ?, ?, '085404', '计算机技术', '不区分研究方向',
                          '主校区', '示例市', '全日制', '普通培养', '硕士',
                          '专业学位', '校本部培养', ?, ?)
                RETURNING id
                """,
                (f"fixture-project-{year}", school_id, college_id, timestamp, timestamp),
            ).fetchone()[0]
            observation_id = connection.execute(
                """
                INSERT INTO project_year_observations(
                    project_id, raw_row_id, observation_fingerprint,
                    admission_year, strict_22408_claim,
                    strict_22408_evidence_status, evidence_grade,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'yes', ?, 'official', ?, ?)
                RETURNING id
                """,
                (
                    project_id,
                    raw_id,
                    f"fixture-observation-{year}",
                    year,
                    historical_status if year == 2026 else "official_confirmed",
                    timestamp,
                    timestamp,
                ),
            ).fetchone()[0]
            source_id = connection.execute(
                """
                INSERT INTO evidence_sources(
                    identity_key, title, institution, url, evidence_grade,
                    published_date, retrieved_date, source_note, created_at,
                    updated_at, document_type, content_sha256, applicable_year
                ) VALUES (?, ?, '示例大学', ?, 'official', ?, ?, '测试来源',
                          ?, ?, 'official_catalog', ?, ?)
                RETURNING id
                """,
                (
                    f"fixture-source-{year}",
                    f"示例大学{year}招生目录",
                    f"https://example.edu/{year}/catalog.pdf",
                    f"{year}-08-01",
                    "2026-08-13",
                    timestamp,
                    timestamp,
                    str(index + 4) * 64,
                    year,
                ),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO observation_sources(observation_id, source_id, relationship) "
                "VALUES (?, ?, 'supports')",
                (observation_id, source_id),
            )
            observations.append(observation_id)
            sources.append(source_id)
        connection.commit()
    return observations[0], observations[1], sources[0], sources[1]


if __name__ == "__main__":
    unittest.main()
