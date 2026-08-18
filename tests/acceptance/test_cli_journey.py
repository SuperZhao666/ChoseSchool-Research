from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.support import REAL_ARCHIVE, REPOSITORY_ROOT
from chose_school.infrastructure.database import Database


class CliJourneyTest(unittest.TestCase):
    def test_candidate_report_is_read_only_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "candidate-report.sqlite3"
            initialized = self._run(
                "--database",
                str(database),
                "--json",
                "init",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            before = database.read_bytes()

            result = self._run(
                "--database",
                str(database),
                "--json",
                "candidate-report",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["read_only"])
            self.assertEqual(report["candidate_count"], 0)
            self.assertEqual(report["model_contract"]["selection_status"], "research_only")
            self.assertFalse(report["model_contract"]["roles_enabled"])
            self.assertFalse(report["model_contract"]["probability_enabled"])
            self.assertIn("profile_snapshot", report)
            self.assertIn("preference_intake", report["profile_snapshot"])
            self.assertIn("measurement_readiness", report["profile_snapshot"])
            self.assertIn("achievement_assets", report["profile_snapshot"])
            self.assertEqual(database.read_bytes(), before)

            invalid = self._run(
                "--database",
                str(database),
                "--json",
                "candidate-report",
                "--candidate-target-id",
                "0",
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertEqual(json.loads(invalid.stderr)["error_code"], "INVALID_ENTITY_ID")

    def test_backup_preserves_pre_migration_schema_without_auto_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "pre-migration.sqlite3"
            backup = root / "pre-migration-backup.sqlite3"

            missing_backup = self._run(
                "--database",
                str(database),
                "--json",
                "backup",
                "--output",
                str(backup),
            )
            self.assertNotEqual(missing_backup.returncode, 0)
            self.assertFalse(database.exists())
            self.assertFalse(backup.exists())

            missing_doctor = self._run(
                "--database",
                str(database),
                "--json",
                "doctor",
            )
            self.assertEqual(missing_doctor.returncode, 1)
            self.assertEqual(
                json.loads(missing_doctor.stderr)["error_code"],
                "DATABASE_MIGRATION_REQUIRED",
            )
            self.assertFalse(database.exists())

            migrations_through_24 = [
                path
                for path in Database._migration_paths()
                if int(path.name.split("_", 1)[0]) <= 24
            ]
            with patch.object(
                Database,
                "_migration_paths",
                return_value=migrations_through_24,
            ):
                self.assertEqual(
                    Database(database).migrate(),
                    list(range(1, 25)),
                )

            pre_migration_bytes = database.read_bytes()
            for guarded_command in ("doctor", "summary"):
                guarded_result = self._run(
                    "--database",
                    str(database),
                    "--json",
                    guarded_command,
                )
                self.assertEqual(guarded_result.returncode, 1)
                guarded_error = json.loads(guarded_result.stderr)
                self.assertEqual(
                    guarded_error["error_code"],
                    "DATABASE_MIGRATION_REQUIRED",
                )
                self.assertIn("python manage.py init", guarded_error["message"])
                self.assertEqual(database.read_bytes(), pre_migration_bytes)
                with closing(sqlite3.connect(database)) as guarded_connection:
                    self.assertEqual(
                        guarded_connection.execute(
                            "SELECT MAX(version) FROM schema_migrations"
                        ).fetchone()[0],
                            24,
                    )

            backup_result = self._run(
                "--database",
                str(database),
                "--json",
                "backup",
                "--output",
                str(backup),
            )
            self.assertEqual(backup_result.returncode, 0, backup_result.stderr)
            self.assertEqual(database.read_bytes(), pre_migration_bytes)
            with closing(sqlite3.connect(database)) as source_connection:
                self.assertEqual(
                    source_connection.execute(
                        "SELECT MAX(version) FROM schema_migrations"
                    ).fetchone()[0],
                    24,
                )
            with closing(sqlite3.connect(backup)) as backup_connection:
                self.assertEqual(
                    backup_connection.execute(
                        "SELECT MAX(version) FROM schema_migrations"
                    ).fetchone()[0],
                    24,
                )
                self.assertEqual(
                    backup_connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )

            migrated = self._run(
                "--database",
                str(database),
                "--json",
                "init",
            )
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            self.assertEqual(
                json.loads(migrated.stdout)["applied_migrations"], [25, 26, 27, 28, 29]
            )

    def test_fact_add_accepts_and_replays_one_structured_derivation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "structured-derivation.sqlite3"
            initialized = self._run(
                "--database",
                str(database),
                "--json",
                "init",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            observation = self._run(
                "--database",
                str(database),
                "--json",
                *_strict_observation_arguments(),
            )
            self.assertEqual(observation.returncode, 0, observation.stderr)
            observation_id = json.loads(observation.stdout)["observation_id"]

            arguments = (
                "fact-add",
                "--observation-id",
                str(observation_id),
                "--fact-key",
                "quota.plan_minus_received_recommendation",
                "--value",
                "22",
                "--evidence-grade",
                "official_mixed",
                "--source-title",
                "2026年复试方案",
                "--source-url",
                "https://example.edu/2026-retest-policy.pdf",
                "--source-institution",
                "西北农林科技大学研究生院",
                "--source-document-type",
                "retest_policy",
                "--source-content-sha256",
                "9" * 64,
                "--applicable-year",
                "2026",
                "--published-date",
                "2026-03-20",
                "--retrieved-date",
                "2026-08-13",
                "--population-scope",
                "目标项目复试阶段计划（专项未拆分）",
                "--statistic-scope",
                "同一文件总计划25减已接收推免3",
                "--derivation-operator",
                "subtract",
                "--derivation-left-fact-key",
                "quota.total_plan",
                "--derivation-left-value",
                "25",
                "--derivation-right-fact-key",
                "quota.recommendation_received",
                "--derivation-right-value",
                "3",
                "--note",
                "25-3=22；两个操作数来自同一份正式文件。",
            )
            first = self._run(
                "--database",
                str(database),
                "--json",
                *arguments,
            )
            replay = self._run(
                "--database",
                str(database),
                "--json",
                *arguments,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            first_id = json.loads(first.stdout)["claim_id"]
            self.assertEqual(json.loads(replay.stdout)["claim_id"], first_id)

            listed = self._run(
                "--database",
                str(database),
                "--json",
                "facts",
                "--observation-id",
                str(observation_id),
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            row = json.loads(listed.stdout)[0]
            self.assertEqual(row["derivation_operator"], "subtract")
            self.assertEqual(row["derivation_left_fact_key"], "quota.total_plan")
            self.assertEqual(row["derivation_left_value_integer"], 25)
            self.assertEqual(
                row["derivation_right_fact_key"],
                "quota.recommendation_received",
            )
            self.assertEqual(row["derivation_right_value_integer"], 3)

            invalid_arguments = list(arguments)
            right_value_index = invalid_arguments.index("--derivation-right-value") + 1
            invalid_arguments[right_value_index] = "2"
            invalid = self._run(
                "--database",
                str(database),
                "--json",
                *invalid_arguments,
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertEqual(
                json.loads(invalid.stderr)["error_code"],
                "DERIVATION_RESULT_MISMATCH",
            )

    def test_help_does_not_create_database_and_core_journey_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "含 空格" / "择校.sqlite3"
            export_path = root / "导出 结果.csv"

            help_result = self._run("--database", str(database), "--help")
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertFalse(database.exists())

            init_result = self._run(
                "--database", str(database), "--json", "init"
            )
            self.assertEqual(init_result.returncode, 0, init_result.stderr)

            import_result = self._run(
                "--database",
                str(database),
                "--json",
                "import-kimi",
                str(REAL_ARCHIVE),
            )
            self.assertEqual(import_result.returncode, 0, import_result.stderr)
            self.assertEqual(json.loads(import_result.stdout)["raw_rows"], 167)

            preference_add_result = self._run(
                "--database",
                str(database),
                "--json",
                "preference-add",
                "--dimension",
                "program_code",
                "--subject",
                "085404",
                "--acceptance",
                "accept",
                "--note",
                "CLI验收个人专业代码边界",
            )
            self.assertEqual(
                preference_add_result.returncode,
                0,
                preference_add_result.stderr,
            )
            preference_event_id = json.loads(preference_add_result.stdout)["event_id"]
            preferences_result = self._run(
                "--database",
                str(database),
                "--json",
                "preferences",
            )
            self.assertEqual(
                preferences_result.returncode,
                0,
                preferences_result.stderr,
            )
            preferences = json.loads(preferences_result.stdout)
            self.assertEqual(len(preferences), 1)
            self.assertEqual(preferences[0]["event_id"], preference_event_id)
            self.assertEqual(preferences[0]["subject_key"], "085404")

            preference_readiness_result = self._run(
                "--database",
                str(database),
                "--json",
                "preference-readiness",
            )
            self.assertEqual(
                preference_readiness_result.returncode,
                0,
                preference_readiness_result.stderr,
            )
            preference_readiness = json.loads(preference_readiness_result.stdout)
            self.assertEqual(preference_readiness["contract_version"], "personal-selection-preference-v2")
            self.assertEqual(preference_readiness["required_subject_count"], 23)
            self.assertEqual(preference_readiness["answered_subject_count"], 1)
            self.assertFalse(preference_readiness["is_preference_intake_complete"])

            context_add_result = self._run(
                "--database",
                str(database),
                "--json",
                "context-add",
                "--dimension",
                "study_progress",
                "--subject",
                "302.linear_algebra",
                "--value-json",
                '{"status":"not_started","book_purchased":true}',
            )
            self.assertEqual(context_add_result.returncode, 0, context_add_result.stderr)
            contexts_result = self._run(
                "--database", str(database), "--json", "contexts"
            )
            self.assertEqual(contexts_result.returncode, 0, contexts_result.stderr)
            contexts = json.loads(contexts_result.stdout)
            self.assertEqual(contexts[0]["subject_key"], "302.linear_algebra")
            self.assertEqual(contexts[0]["value"]["status"], "not_started")

            official_arguments = (
                "official-observation-add",
                "--school",
                "西北农林科技大学",
                "--college",
                "信息工程学院",
                "--program-code",
                "085404",
                "--program-name",
                "计算机技术",
                "--admission-year",
                "2026",
                "--politics",
                "101",
                "--english",
                "204",
                "--math",
                "302",
                "--professional",
                "408",
                "--study-mode",
                "全日制",
                "--source-title",
                "2026年硕士研究生招生专业目录",
                "--source-url",
                "https://example.edu/2026-catalog.xls",
                "--source-institution",
                "西北农林科技大学研究生院",
                "--source-document-type",
                "official_catalog",
                "--source-content-sha256",
                "7" * 64,
                "--applicable-year",
                "2026",
            )
            official_result = self._run(
                "--database",
                str(database),
                "--json",
                *official_arguments,
            )
            self.assertEqual(official_result.returncode, 0, official_result.stderr)
            official_payload = json.loads(official_result.stdout)
            self.assertTrue(official_payload["created"])
            self.assertEqual(
                official_payload["strict_22408_status"],
                "official_confirmed",
            )
            repeated_official_result = self._run(
                "--database",
                str(database),
                "--json",
                *official_arguments,
            )
            self.assertEqual(
                repeated_official_result.returncode,
                0,
                repeated_official_result.stderr,
            )
            self.assertFalse(json.loads(repeated_official_result.stdout)["created"])

            projects_result = self._run(
                "--database", str(database), "--json", "projects", "--limit", "1"
            )
            self.assertEqual(projects_result.returncode, 0, projects_result.stderr)
            project = json.loads(projects_result.stdout)[0]
            raw_projects_result = self._run(
                "--database",
                str(database),
                "--json",
                "projects",
                "--raw-imported",
                "--limit",
                "1",
            )
            self.assertEqual(
                raw_projects_result.returncode,
                0,
                raw_projects_result.stderr,
            )
            self.assertEqual(len(json.loads(raw_projects_result.stdout)), 1)
            missing_scope_result = self._run(
                "--database",
                str(database),
                "--json",
                "fact-add",
                "--observation-id",
                str(project["observation_id"]),
                "--fact-key",
                "quota.exam_catalog_plan",
                "--value",
                "18",
                "--evidence-grade",
                "secondary",
                "--source-title",
                "CLI验收缺少事实口径",
                "--source-document-type",
                "secondary_summary",
                "--applicable-year",
                str(project["admission_year"]),
            )
            self.assertNotEqual(missing_scope_result.returncode, 0)
            self.assertIn("--population-scope", missing_scope_result.stderr)
            self.assertIn("--statistic-scope", missing_scope_result.stderr)
            fact_add_result = self._run(
                "--database",
                str(database),
                "--json",
                "fact-add",
                "--observation-id",
                str(project["observation_id"]),
                "--fact-key",
                "quota.exam_catalog_plan",
                "--value",
                "18",
                "--evidence-grade",
                "secondary",
                "--source-title",
                "CLI验收分专业汇总",
                "--source-document-type",
                "secondary_summary",
                "--applicable-year",
                str(project["admission_year"]),
                "--population-scope",
                "目录阶段目标项目",
                "--statistic-scope",
                "目录阶段考试拟招人数",
            )
            self.assertEqual(fact_add_result.returncode, 0, fact_add_result.stderr)
            claim_id = json.loads(fact_add_result.stdout)["claim_id"]
            fact_resolve_result = self._run(
                "--database",
                str(database),
                "--json",
                "fact-resolve",
                "--claim-id",
                str(claim_id),
                "--reason",
                "CLI验收先接受目录阶段计划口径",
            )
            self.assertEqual(
                fact_resolve_result.returncode,
                0,
                fact_resolve_result.stderr,
            )
            fact_unresolve_result = self._run(
                "--database",
                str(database),
                "--json",
                "fact-unresolve",
                "--claim-id",
                str(claim_id),
                "--reason",
                "CLI验收撤销当前裁决",
            )
            self.assertEqual(
                fact_unresolve_result.returncode,
                0,
                fact_unresolve_result.stderr,
            )
            unresolve_payload = json.loads(fact_unresolve_result.stdout)
            self.assertEqual(unresolve_payload["identity_claim_id"], claim_id)
            self.assertEqual(unresolve_payload["resolution_action"], "unresolved")
            self.assertIsNone(unresolve_payload["selected_claim_id"])
            facts_result = self._run(
                "--database",
                str(database),
                "--json",
                "facts",
                "--observation-id",
                str(project["observation_id"]),
            )
            self.assertEqual(facts_result.returncode, 0, facts_result.stderr)
            fact_rows = json.loads(facts_result.stdout)
            self.assertEqual(len(fact_rows), 1)
            self.assertEqual(fact_rows[0]["claim_id"], claim_id)
            self.assertEqual(fact_rows[0]["is_current_resolution"], 0)

            issues_result = self._run(
                "--database",
                str(database),
                "--json",
                "issues",
                "--limit",
                "1",
            )
            self.assertEqual(issues_result.returncode, 0, issues_result.stderr)
            issue_id = json.loads(issues_result.stdout)[0]["id"]
            resolution_result = self._run(
                "--database",
                str(database),
                "--json",
                "issue-resolve",
                "--issue-id",
                str(issue_id),
                "--note",
                "CLI验收测试中的可审计解决说明",
            )
            self.assertEqual(resolution_result.returncode, 0, resolution_result.stderr)

            export_result = self._run(
                "--database",
                str(database),
                "--json",
                "export",
                "--output",
                str(export_path),
                "--excel-safe",
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)
            self.assertTrue(export_path.is_file())
            raw_export_path = root / "导出 原始值.csv"
            raw_export_result = self._run(
                "--database",
                str(database),
                "--json",
                "export",
                "--output",
                str(raw_export_path),
                "--raw-imported",
                "--excel-safe",
            )
            self.assertEqual(
                raw_export_result.returncode,
                0,
                raw_export_result.stderr,
            )
            self.assertTrue(raw_export_path.is_file())
            self.assertNotEqual(export_path.read_bytes(), raw_export_path.read_bytes())

            backup_path = root / "备份 文件.sqlite3"
            backup_result = self._run(
                "--database",
                str(database),
                "--json",
                "backup",
                "--output",
                str(backup_path),
            )
            self.assertEqual(backup_result.returncode, 0, backup_result.stderr)
            self.assertTrue(backup_path.is_file())

            doctor_result = self._run(
                "--database", str(database), "--json", "doctor"
            )
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertEqual(json.loads(doctor_result.stdout)["status"], "ok")

            backup_doctor_result = self._run(
                "--database", str(backup_path), "--json", "doctor"
            )
            self.assertEqual(
                backup_doctor_result.returncode,
                0,
                backup_doctor_result.stderr,
            )
            self.assertEqual(json.loads(backup_doctor_result.stdout)["status"], "ok")

    def test_policy_event_cli_journey_is_idempotent_and_strict_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "政策事件.sqlite3"
            self._run_json("--database", str(database), "--json", "init")
            observation = self._run_json(
                "--database",
                str(database),
                "--json",
                *_strict_observation_arguments(),
            )
            self.assertTrue(observation["created"])

            before = self._run_json(
                "--database", str(database), "--json", "projects", "--limit", "10"
            )
            first = self._run_json(
                "--database", str(database), "--json", *_policy_event_arguments()
            )
            replay = self._run_json(
                "--database", str(database), "--json", *_policy_event_arguments()
            )
            events = self._run_json(
                "--database",
                str(database),
                "--json",
                "policy-events",
                "--year",
                "2027",
                "--school",
                "西北农林科技大学",
            )
            after = self._run_json(
                "--database", str(database), "--json", "projects", "--limit", "10"
            )
            doctor = self._run_json(
                "--database", str(database), "--json", "doctor"
            )

            self.assertTrue(first["created"])
            self.assertFalse(replay["created"])
            self.assertEqual(replay["event_id"], first["event_id"])
            self.assertEqual(first["event_status"], "pending_directory")
            self.assertFalse(first["establishes_official_catalog"])
            self.assertFalse(first["can_confirm_strict_22408"])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_id"], first["event_id"])
            self.assertEqual(events[0]["establishes_official_catalog"], 0)
            self.assertEqual(events[0]["can_confirm_strict_22408"], 0)
            self.assertEqual(_strict_project_states(after), _strict_project_states(before))
            self.assertEqual(doctor["status"], "ok")

    def test_machine_measurement_cli_journey_keeps_protocols_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "机试测量.sqlite3"
            init_result = self._run("--database", str(database), "--json", "init")
            self.assertEqual(init_result.returncode, 0, init_result.stderr)

            initial_result = self._run(
                "--database",
                str(database),
                "--json",
                "machine-assessment",
            )
            self.assertEqual(initial_result.returncode, 0, initial_result.stderr)
            initial = json.loads(initial_result.stdout)
            self.assertFalse(initial["is_duration_coverage_complete"])
            self.assertEqual(initial["required_durations"], [90, 120, 180])
            self.assertEqual(
                [item["status"] for item in initial["durations"]],
                ["not_measured", "not_measured", "not_measured"],
            )

            invalid_result = self._run(
                "--database",
                str(database),
                "--json",
                "machine-add",
                "--date",
                "2026-08-08",
                "--duration-minutes",
                "90",
                "--language",
                "cpp",
                "--environment",
                "C++17 / 本地OJ",
                "--problem-source",
                "接受提示但未说明原因",
                "--difficulty",
                "basic",
                "--problem-count",
                "3",
                "--independently-solved-count",
                "0",
                "--first-exposure",
                "--received-assistance",
                "--strict-timed",
            )
            self.assertEqual(invalid_result.returncode, 1)
            self.assertEqual(
                json.loads(invalid_result.stderr)["error_code"],
                "MACHINE_TEST_INVALID_REASON_REQUIRED",
            )

            sessions = (
                (
                    "2026-08-09",
                    "90",
                    "90分钟未见题A",
                    "4",
                    "0",
                    (),
                ),
                (
                    "2026-08-23",
                    "120",
                    "120分钟未见题A",
                    "5",
                    "2",
                    ("--first-solve-minutes", "33", "--debugging-minutes", "40"),
                ),
                (
                    "2026-08-30",
                    "100",
                    "郑大100分钟专用题组A",
                    "4",
                    "1",
                    ("--first-solve-minutes", "46"),
                ),
            )
            for taken_on, duration, source, total, solved, optional in sessions:
                result = self._run(
                    "--database",
                    str(database),
                    "--json",
                    "machine-add",
                    "--date",
                    taken_on,
                    "--duration",
                    duration,
                    "--language",
                    "cpp",
                    "--environment",
                    "C++17 / 本地OJ",
                    "--source",
                    source,
                    "--difficulty",
                    "mixed",
                    "--total",
                    total,
                    "--solved",
                    solved,
                    "--scoring-method",
                    "solved_count",
                    "--first-exposure",
                    "--strict-timed",
                    *optional,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["is_valid"])

            before_180 = json.loads(
                self._run(
                    "--database",
                    str(database),
                    "--json",
                    "machine-assessment",
                ).stdout
            )
            self.assertFalse(before_180["is_duration_coverage_complete"])
            self.assertEqual(before_180["total_session_count"], 3)

            points_result = self._run(
                "--database",
                str(database),
                "--json",
                "machine-add",
                "--date",
                "2026-09-06",
                "--duration",
                "180",
                "--language",
                "cpp",
                "--environment",
                "C++17 / 本地OJ",
                "--source",
                "180分钟计分题组A",
                "--difficulty",
                "candidate_specific",
                "--total",
                "5",
                "--solved",
                "3",
                "--first-solve-minutes",
                "29",
                "--debugging-minutes",
                "58",
                "--scoring-method",
                "points",
                "--raw-score",
                "63",
                "--maximum-score",
                "100",
                "--first-exposure",
                "--strict-timed",
            )
            self.assertEqual(points_result.returncode, 0, points_result.stderr)

            list_result = self._run(
                "--database",
                str(database),
                "--json",
                "machine-sessions",
                "--duration",
                "120",
                "--language",
                "cpp",
                "--problem-count",
                "5",
                "--valid-only",
            )
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            listed = json.loads(list_result.stdout)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["debugging_minutes"], 40)

            final_result = self._run(
                "--database",
                str(database),
                "--json",
                "machine-assessment",
            )
            self.assertEqual(final_result.returncode, 0, final_result.stderr)
            final = json.loads(final_result.stdout)
            self.assertTrue(final["is_duration_coverage_complete"])
            self.assertEqual(final["total_session_count"], 4)
            self.assertNotIn("machine_test_level", final)
            self.assertNotIn("mean", final)

            doctor_result = self._run(
                "--database",
                str(database),
                "--json",
                "doctor",
            )
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertEqual(
                json.loads(doctor_result.stdout)["machine_test_missing_audit"],
                0,
            )

    @staticmethod
    def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            ["python", "manage.py", *arguments],
            cwd=REPOSITORY_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env=environment,
        )

    def _run_json(self, *arguments: str) -> Any:
        result = self._run(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


def _strict_observation_arguments() -> tuple[str, ...]:
    return (
        "official-observation-add",
        "--school",
        "西北农林科技大学",
        "--college",
        "信息工程学院",
        "--program-code",
        "085404",
        "--program-name",
        "计算机技术",
        "--admission-year",
        "2026",
        "--politics",
        "101",
        "--english",
        "204",
        "--math",
        "302",
        "--professional",
        "408",
        "--study-mode",
        "全日制",
        "--source-title",
        "2026年硕士研究生招生专业目录",
        "--source-url",
        "https://example.edu/2026-catalog.xls",
        "--source-institution",
        "西北农林科技大学研究生院",
        "--source-document-type",
        "official_catalog",
        "--source-content-sha256",
        "7" * 64,
        "--applicable-year",
        "2026",
        "--retrieved-date",
        "2026-08-03",
    )


def _policy_event_arguments() -> tuple[str, ...]:
    return (
        "policy-event-add",
        "--school",
        "西北农林科技大学",
        "--effective-year",
        "2027",
        "--event-type",
        "subject_adjustment_notice",
        "--scope-text",
        "信息工程学院085404计算机技术",
        "--title",
        "2027年硕士研究生招生考试初试科目调整公告",
        "--description",
        "第四科调整为408，完整四码及严格22408状态仍以正式目录为准",
        "--announced-on",
        "2026-05-19",
        "--source-title",
        "2027年硕士研究生招生考试初试科目调整公告",
        "--source-url",
        "https://example.edu/notice/2027-subject-change",
        "--source-institution",
        "西北农林科技大学研究生院",
        "--source-document-type",
        "official_notice",
        "--source-content-sha256",
        "8" * 64,
        "--applicable-year",
        "2027",
        "--published-date",
        "2026-05-19",
        "--retrieved-date",
        "2026-08-03",
    )


def _strict_project_states(projects: list[dict[str, Any]]) -> list[tuple[int, str]]:
    return [
        (project["observation_id"], project["strict_22408_status"])
        for project in projects
    ]


if __name__ == "__main__":
    unittest.main()
