from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from tests.support import REAL_ARCHIVE, build_test_application

from chose_school.domain.enums import FactDataType
from chose_school.domain.fact_registry import FACT_DATA_TYPES


class MigrationsAndRealImportTest(unittest.TestCase):
    def test_specialized_facts_are_registered_by_forward_migrations(self) -> None:
        migration_012 = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "chose_school"
            / "infrastructure"
            / "migrations"
            / "012_add_machine_test_sessions.sql"
        )
        self.assertEqual(
            hashlib.sha256(migration_012.read_bytes()).hexdigest(),
            "fee0a205bed465fbe3254bcd86f8d968db6181ee9cdaa3328c8435c47a7c8542",
        )
        expected_definitions = {
            (
                "admission.suggested_list_total_count",
                "integer",
                "人",
                "官方建议录取名单总行数；不是最终拟录取人数",
                "学院建议录取名单",
            ),
            (
                "admission.suggested_list_blank_remark_count",
                "integer",
                "人",
                "官方建议录取名单中备注为空的行数；不是普通统考最终人数",
                "学院建议录取名单",
            ),
            (
                "admission.suggested_list_special_count",
                "integer",
                "人",
                "官方建议录取名单中明确专项备注的行数",
                "学院建议录取名单",
            ),
            (
                "admission.final_list_fulltime_blank_remark_count",
                "integer",
                "人",
                "最终拟录取名单中目标项目、全日制且备注为空的行数；不自动等同普通统考录取人数",
                "最终拟录取名单逐行筛选",
            ),
            (
                "score.final_list_fulltime_blank_remark_initial.min",
                "decimal",
                "分",
                "最终拟录取名单中目标项目、全日制且备注为空行的初试总分最低值；不自动等同普通统考最低分",
                "最终拟录取名单逐行复算",
            ),
            (
                "score.final_list_fulltime_blank_remark_initial.median",
                "decimal",
                "分",
                "最终拟录取名单中目标项目、全日制且备注为空行的初试总分中位数；不自动等同普通统考中位数",
                "最终拟录取名单逐行复算",
            ),
            (
                "score.final_list_fulltime_blank_remark_initial.mean",
                "decimal",
                "分",
                "最终拟录取名单中目标项目、全日制且备注为空行的初试总分算术均值；不自动等同普通统考均值",
                "最终拟录取名单逐行复算",
            ),
            (
                "training.city",
                "text",
                None,
                "项目培养城市；必须由项目培养安排明确支持，不能由复试或迎新地点推断",
                "正式招生目录、培养安排或录取通知",
            ),
            (
                "training.campus",
                "text",
                None,
                "项目精确培养校区；必须由项目培养安排明确支持，不能由复试或迎新地点推断",
                "正式招生目录、培养安排或录取通知",
            ),
            (
                "quota.exam_catalog_plan",
                "integer",
                "人",
                "目录阶段公布的考试招生拟招人数；属于计划口径，不等同普通统考有效名额",
                "正式招生目录或官方分专业汇总",
            ),
            (
                "applicant.above_national_line_count",
                "integer",
                "人",
                "初试达到国家线人数；不等同实际进入复试人数",
                "官方分专业报考录取汇总",
            ),
            (
                "admission.exam_fulltime_total_count",
                "integer",
                "人",
                "全日制考试招生录取合计人数；可能包含专项计划，不等同普通统考录取人数",
                "官方分专业报考录取汇总",
            ),
            (
                "retest.roster_count",
                "integer",
                "人",
                "官方复试名单列示的普通统考人数；只证明进入公开名单，不证明通过资格审查或实际参加复试",
                "正式复试名单",
            ),
            (
                "retest.result_published_count",
                "integer",
                "人",
                "官方公开复试结果表中具有完整成绩行的普通统考人数；不自动等同全部实际参加复试人数",
                "正式复试结果表",
            ),
            (
                "score.retest_roster_initial.min",
                "decimal",
                "分",
                "普通统考复试名单中初试总分最低值；不是拟录取最低分",
                "正式复试名单",
            ),
            (
                "score.retest_roster_initial.median",
                "decimal",
                "分",
                "普通统考复试名单中初试总分中位数；不是拟录取中位数",
                "正式复试名单",
            ),
            (
                "score.retest_roster_initial.mean",
                "decimal",
                "分",
                "普通统考复试名单中初试总分算术均值；不是拟录取均值",
                "正式复试名单",
            ),
            (
                "score.retest_roster_initial.max",
                "decimal",
                "分",
                "普通统考复试名单中初试总分最高值；不是拟录取最高分",
                "正式复试名单",
            ),
        }
        expected_definitions = {
            row
            for row in expected_definitions
            if row[0]
            not in {
                "retest.roster_count",
                "retest.result_published_count",
                "score.retest_roster_initial.min",
                "score.retest_roster_initial.median",
                "score.retest_roster_initial.mean",
                "score.retest_roster_initial.max",
            }
        }
        expected_definitions.update(
            {
                (
                    "retest.roster_count",
                    "integer",
                    "人",
                    "官方复试名单按主张限定群体列示的考生行数；不自动等于普通统考、资格审查通过或实际到场人数",
                    "正式复试名单",
                ),
                (
                    "retest.result_published_count",
                    "integer",
                    "人",
                    "官方复试结果表按主张限定群体列示的完整成绩行数；不自动等于普通统考或全部实际参加人数",
                    "正式复试结果表",
                ),
                (
                    "score.retest_roster_initial.min",
                    "decimal",
                    "分",
                    "官方复试名单按主张限定群体计算的初试总分最低值；不自动等于普通统考或拟录取最低分",
                    "正式复试名单",
                ),
                (
                    "score.retest_roster_initial.median",
                    "decimal",
                    "分",
                    "官方复试名单按主张限定群体计算的初试总分中位数；不自动等于普通统考或拟录取中位数",
                    "正式复试名单",
                ),
                (
                    "score.retest_roster_initial.mean",
                    "decimal",
                    "分",
                    "官方复试名单按主张限定群体计算的初试总分算术均值；不自动等于普通统考或拟录取均值",
                    "正式复试名单",
                ),
                (
                    "score.retest_roster_initial.max",
                    "decimal",
                    "分",
                    "官方复试名单按主张限定群体计算的初试总分最高值；不自动等于普通统考或拟录取最高分",
                    "正式复试名单",
                ),
                (
                    "quota.recommendation_planned",
                    "integer",
                    "人",
                    "目录静态发布阶段拟接收推免人数；与后续已接收推免人数分开，不参与最终统考名额推导",
                    "正式招生目录静态版本",
                ),
                (
                    "quota.recommendation_actual",
                    "integer",
                    "人",
                    "最终推免拟录取公示名单按同一项目、同一招生年度逐行筛选得到的项目级行数；表示公示阶段的拟录取名单人数，不是最终报到、入学或学籍注册人数",
                    "最终推免拟录取公示名单逐行统计",
                ),
                (
                    "quota.recommendation_received",
                    "integer",
                    "人",
                    "目录动态页或复试阶段文件明确列示的已接收推免人数；与拟接收计划及最终推免名单统计分开",
                    "正式动态目录或复试细则",
                ),
                (
                    "quota.plan_minus_received_recommendation",
                    "integer",
                    "人",
                    "同一正式文件中的复试阶段总计划减去已接收推免人数得到的透明算术余量；可能包含专项，不等同普通统考有效名额",
                    "正式复试细则及透明算术推导",
                ),
                (
                    "admission.final_list_first_choice_fulltime_non_directed_count",
                    "integer",
                    "人",
                    "一志愿最终名单中目标项目、全日制且拟录取类别为非定向的行数；名单无专项列时不得等同普通统考人数",
                    "一志愿最终拟录取名单逐行筛选",
                ),
                (
                    "score.final_list_first_choice_fulltime_non_directed_initial.min",
                    "decimal",
                    "分",
                    "上述一志愿、全日制、非定向最终名单行的初试总分最低值；专项未拆时不得转存为普通统考最低分",
                    "一志愿最终拟录取名单逐行复算",
                ),
                (
                    "score.final_list_first_choice_fulltime_non_directed_initial.median",
                    "decimal",
                    "分",
                    "上述一志愿、全日制、非定向最终名单行的初试总分中位数；专项未拆时不得转存为普通统考中位数",
                    "一志愿最终拟录取名单逐行复算",
                ),
                (
                    "score.final_list_first_choice_fulltime_non_directed_initial.mean",
                    "decimal",
                    "分",
                    "上述一志愿、全日制、非定向最终名单行的初试总分算术均值；专项未拆时不得转存为普通统考均值",
                    "一志愿最终拟录取名单逐行复算",
                ),
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            with closing(sqlite3.connect(application.database.database_path)) as connection:
                placeholders = ", ".join("?" for _ in expected_definitions)
                definitions = set(
                    connection.execute(
                        f"""
                        SELECT fact_key, data_type, unit, description, preferred_source_type
                        FROM fact_definitions
                        WHERE fact_key IN ({placeholders})
                        """,
                        tuple(row[0] for row in expected_definitions),
                    ).fetchall()
                )
                migration_versions = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                catalog_columns = {
                    row[1]: row[2]
                    for row in connection.execute("PRAGMA table_info(v_catalog)")
                }
                catalog_column_names = [
                    row[1]
                    for row in connection.execute("PRAGMA table_info(v_catalog)")
                ]
                resolved_catalog_columns = {
                    row[1]: row[2]
                    for row in connection.execute(
                        "PRAGMA table_info(v_catalog_evidence_resolved)"
                    )
                }
                resolved_catalog_column_names = [
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(v_catalog_evidence_resolved)"
                    )
                ]

            self.assertEqual(definitions, expected_definitions)
            self.assertEqual(migration_versions, list(range(1, 30)))
            self.assertEqual(
                catalog_column_names,
                [
                    "observation_id",
                    "source_row_number",
                    "archive_member",
                    "school",
                    "college",
                    "program_code",
                    "program_name",
                    "direction",
                    "campus",
                    "training_location",
                    "study_mode",
                    "training_type_raw",
                    "admission_type",
                    "degree_type",
                    "training_arrangement",
                    "admission_year",
                    "strict_22408_claim",
                    "strict_22408_status",
                    "imported_evidence_status",
                    "subject_politics_code",
                    "subject_english_code",
                    "subject_math_code",
                    "subject_professional_code",
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
                    "study_length_years",
                    "first_choice_protection",
                    "evidence_grade",
                    "official_source",
                    "retrieval_date",
                    "notes",
                    "open_issue_count",
                ],
            )
            self.assertEqual(catalog_columns["subject_politics_code"], "TEXT")
            self.assertEqual(catalog_columns["subject_english_code"], "TEXT")
            self.assertEqual(catalog_columns["subject_math_code"], "TEXT")
            self.assertEqual(catalog_columns["subject_professional_code"], "TEXT")
            self.assertEqual(resolved_catalog_column_names, catalog_column_names)
            self.assertEqual(resolved_catalog_columns["campus"], "TEXT")
            self.assertEqual(resolved_catalog_columns["training_location"], "TEXT")
            self.assertEqual(resolved_catalog_columns["strict_22408_status"], "TEXT")
            self.assertEqual(
                resolved_catalog_columns["effective_general_exam_quota"],
                "INT",
            )
            self.assertEqual(resolved_catalog_columns["retest_cutoff"], "REAL")
            self.assertEqual(resolved_catalog_columns["evidence_grade"], "TEXT")
            self.assertEqual(resolved_catalog_columns["open_issue_count"], "INT")
            for fact_key, data_type, *_ in expected_definitions:
                self.assertIs(FACT_DATA_TYPES[fact_key], FactDataType(data_type))
            with closing(sqlite3.connect(application.database.database_path)) as connection:
                all_database_fact_types = {
                    row[0]: FactDataType(row[1])
                    for row in connection.execute(
                        "SELECT fact_key, data_type FROM fact_definitions"
                    )
                }
            self.assertEqual(all_database_fact_types, FACT_DATA_TYPES)

    def test_migrations_are_idempotent_and_real_archive_is_traceable(self) -> None:
        if not REAL_ARCHIVE.exists():
            self.skipTest("本地私有 Kimi 原始归档未提供；仅在受控工作区执行真实导入验收")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application, _ = build_test_application(root)
            self.assertEqual(
                application.database.initialize_database()["applied_migrations"], []
            )

            source_hash = hashlib.sha256(REAL_ARCHIVE.read_bytes()).hexdigest()
            self.assertEqual(
                source_hash,
                "e53bc4d4ddacc850e0553b072b437aa87b3d46533eb6bd48cd3837f3c7cf0e95",
            )
            result = application.catalog_import.import_archive(
                REAL_ARCHIVE,
                batch_id=str(uuid.uuid4()),
                trace_id=str(uuid.uuid4()),
            )
            self.assertEqual(result.source_files, 5)
            self.assertEqual(result.ignored_members, 10)
            self.assertEqual(result.raw_rows, 167)
            self.assertEqual(result.observations, 167)

            summary = application.catalog.get_summary()
            self.assertEqual(summary["counts"]["schools"], 49)
            self.assertEqual(summary["counts"]["raw_rows"], 167)
            self.assertEqual(summary["counts"]["observations"], 167)
            self.assertEqual(
                summary["year_distribution"],
                [
                    {"value": 2022, "count": 4},
                    {"value": 2023, "count": 6},
                    {"value": 2024, "count": 9},
                    {"value": 2025, "count": 11},
                    {"value": 2026, "count": 134},
                    {"value": 2027, "count": 3},
                ],
            )
            self.assertEqual(
                summary["strict_claim_distribution"],
                [{"value": "no", "count": 35}, {"value": "yes", "count": 132}],
            )
            self.assertEqual(application.catalog.doctor()["status"], "ok")

            duplicate = application.catalog_import.import_archive(
                REAL_ARCHIVE,
                batch_id=str(uuid.uuid4()),
                trace_id=str(uuid.uuid4()),
            )
            self.assertEqual(duplicate.status, "duplicate")
            self.assertEqual(application.catalog.get_summary()["counts"]["raw_rows"], 167)

            with closing(sqlite3.connect(application.database.database_path)) as connection:
                repaired = connection.execute(
                    """
                    SELECT COUNT(*) FROM data_quality_issues
                    WHERE issue_code = 'KNOWN_LEGACY_FIELD_SHIFT_REPAIRED'
                    """
                ).fetchone()[0]
                pending_2027 = connection.execute(
                    """
                    SELECT COUNT(*) FROM project_year_observations
                    WHERE admission_year = 2027
                      AND strict_22408_evidence_status = 'official_pending_catalog'
                    """
                ).fetchone()[0]
                missing_sources = connection.execute(
                    """
                    SELECT COUNT(*) FROM data_quality_issues
                    WHERE issue_code = 'MISSING_SOURCE_REFERENCE'
                    """
                ).fetchone()[0]
                composite_codes = connection.execute(
                    """
                    SELECT COUNT(*) FROM data_quality_issues
                    WHERE issue_code = 'COMPOSITE_PROGRAM_CODE'
                    """
                ).fetchone()[0]
                self.assertEqual(repaired, 4)
                self.assertEqual(pending_2027, 3)
                self.assertEqual(missing_sources, 4)
                self.assertEqual(composite_codes, 3)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE raw_catalog_rows SET raw_json = '{}' WHERE id = 1"
                    )


if __name__ == "__main__":
    unittest.main()
