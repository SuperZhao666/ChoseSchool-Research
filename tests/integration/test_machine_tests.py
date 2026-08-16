from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import (
    MachineScoringMethod,
    MachineTestDifficulty,
)
from chose_school.domain.errors import StateConflictError, ValidationError
from chose_school.domain.models import MachineTestInput


class MachineTestMeasurementTest(unittest.TestCase):
    def test_measurements_are_audited_append_only_and_grouped_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))

            invalid = application.machine_tests.add_machine_test(
                _machine_test(
                    duration_minutes=90,
                    problem_source="看过解析的训练题组",
                    first_exposure=False,
                    strict_timed=False,
                    invalid_reason="题目并非首次见且中途暂停",
                ),
                str(uuid.uuid4()),
            )
            self.assertFalse(invalid.is_valid)

            traces: list[str] = []
            for measurement in (
                _machine_test(
                    duration_minutes=90,
                    problem_source="90分钟未见题A",
                    problem_count=4,
                    independently_solved_count=0,
                    first_solve_minutes=None,
                    debugging_minutes=20,
                    scoring_method=MachineScoringMethod.SOLVED_COUNT,
                ),
                _machine_test(
                    duration_minutes=120,
                    language="cpp",
                    problem_source="120分钟C++题组A",
                    problem_count=5,
                    independently_solved_count=2,
                    first_solve_minutes=31,
                    difficulty=MachineTestDifficulty.MIXED,
                    scoring_method=MachineScoringMethod.SOLVED_COUNT,
                ),
                _machine_test(
                    duration_minutes=120,
                    language="c",
                    problem_source="120分钟C题组A",
                    problem_count=5,
                    independently_solved_count=1,
                    first_solve_minutes=48,
                    difficulty=MachineTestDifficulty.MIXED,
                    scoring_method=MachineScoringMethod.SOLVED_COUNT,
                ),
                _machine_test(
                    duration_minutes=180,
                    problem_source="180分钟计分题组A",
                    problem_count=5,
                    independently_solved_count=3,
                    first_solve_minutes=28,
                    scoring_method=MachineScoringMethod.POINTS,
                    raw_score=62,
                    maximum_score=100,
                ),
                _machine_test(
                    duration_minutes=100,
                    problem_source="郑大100分钟专用题组A",
                    problem_count=4,
                    independently_solved_count=1,
                    first_solve_minutes=42,
                ),
            ):
                trace_id = str(uuid.uuid4())
                traces.append(trace_id)
                result = application.machine_tests.add_machine_test(
                    measurement,
                    trace_id,
                )
                self.assertTrue(result.is_valid)

            audit_count_before_queries = _audit_count(application)
            assessment = application.machine_tests.summarize()
            filtered = application.machine_tests.list_sessions(
                duration_minutes=120,
                language="cpp",
                problem_count=5,
                valid_only=True,
            )
            audit_count_after_queries = _audit_count(application)

            self.assertEqual(audit_count_before_queries, 6)
            self.assertEqual(audit_count_after_queries, audit_count_before_queries)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["language"], "cpp")
            self.assertTrue(filtered[0]["is_valid"])
            self.assertEqual(filtered[0]["scoring_method"], "solved_count")

            self.assertEqual(assessment.total_session_count, 6)
            self.assertEqual(assessment.valid_session_count, 5)
            self.assertTrue(assessment.is_duration_coverage_complete)
            self.assertEqual(assessment.required_durations, (90, 120, 180))
            self.assertEqual(
                [duration.duration_minutes for duration in assessment.durations],
                [90, 120, 180],
            )
            self.assertEqual(len(assessment.durations[1].comparison_groups), 2)
            serialized = asdict(assessment)
            self.assertNotIn("is_complete", serialized)
            self.assertNotIn("machine_test_level", serialized)
            self.assertNotIn("mean", serialized)

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                audit_rows = connection.execute(
                    """
                    SELECT trace_id, entity_id
                    FROM audit_events
                    WHERE event_type = 'machine_test_added'
                    ORDER BY id
                    """
                ).fetchall()
                self.assertEqual([row[0] for row in audit_rows[1:]], traces)
                session_id = int(audit_rows[0][1])
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE machine_test_sessions SET notes = '覆盖' WHERE id = ?",
                        (session_id,),
                    )
                connection.rollback()
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "DELETE FROM machine_test_sessions WHERE id = ?",
                        (session_id,),
                    )

            self.assertEqual(application.catalog.doctor()["machine_test_missing_audit"], 0)

    def test_validation_preserves_low_results_but_rejects_ambiguous_protocols(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            trace_id = str(uuid.uuid4())

            zero_result = application.machine_tests.add_machine_test(
                _machine_test(
                    problem_source="有效但零通过题组",
                    independently_solved_count=0,
                    first_solve_minutes=None,
                ),
                trace_id,
            )
            self.assertTrue(zero_result.is_valid)

            invalid_variants = (
                replace(
                    _machine_test(problem_source="接受提示"),
                    received_assistance=True,
                ),
                replace(
                    _machine_test(problem_source="暂停计时"),
                    paused_timer=True,
                ),
                replace(
                    _machine_test(problem_source="查询资料"),
                    consulted_materials=True,
                ),
            )
            for measurement in invalid_variants:
                with self.subTest(problem_source=measurement.problem_source):
                    with self.assertRaises(ValidationError):
                        application.machine_tests.add_machine_test(
                            measurement,
                            str(uuid.uuid4()),
                        )

            invalid_saved = application.machine_tests.add_machine_test(
                replace(
                    invalid_variants[0],
                    invalid_reason="接受了外部提示，只保留为训练记录",
                ),
                str(uuid.uuid4()),
            )
            self.assertFalse(invalid_saved.is_valid)

            invalid_inputs = (
                replace(
                    _machine_test(problem_source="有效却填无效原因"),
                    invalid_reason="不应存在",
                ),
                replace(
                    _machine_test(problem_source="零题却有首题时间"),
                    independently_solved_count=0,
                    first_solve_minutes=10,
                ),
                replace(
                    _machine_test(problem_source="有通过题却无时间"),
                    independently_solved_count=1,
                    first_solve_minutes=None,
                ),
                replace(
                    _machine_test(problem_source="调试越界"),
                    debugging_minutes=121,
                ),
                replace(
                    _machine_test(problem_source="分数缺满分"),
                    raw_score=60,
                ),
                replace(
                    _machine_test(problem_source="原始分越界"),
                    raw_score=101,
                    maximum_score=100,
                ),
                replace(
                    _machine_test(problem_source="积分制缺分数"),
                    scoring_method=MachineScoringMethod.POINTS,
                ),
            )
            for measurement in invalid_inputs:
                with self.subTest(problem_source=measurement.problem_source):
                    with self.assertRaises(ValidationError):
                        application.machine_tests.add_machine_test(
                            measurement,
                            str(uuid.uuid4()),
                        )

            with self.assertRaises(StateConflictError):
                application.machine_tests.add_machine_test(
                    _machine_test(
                        problem_source="有效但零通过题组",
                        independently_solved_count=0,
                        first_solve_minutes=None,
                    ),
                    str(uuid.uuid4()),
                )

    def test_database_trigger_and_doctor_reject_untraceable_or_inconsistent_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            profile_id = application.assessment.initialize_default_profile(str(uuid.uuid4()))
            database_path = application.database.database_path
            base_values = (
                profile_id,
                "2026-08-10",
                90,
                "cpp",
                "C++17 / 本地OJ",
                "直接SQL测试题组",
                "unknown",
                3,
                0,
                None,
                1,
                0,
                1,
                "unknown",
                "direct-sql-trace",
                "2026-08-10T00:00:00+00:00",
            )
            insert_sql = """
                INSERT INTO machine_test_sessions(
                    profile_id, taken_on, duration_minutes, language,
                    environment, problem_source, difficulty_label,
                    problem_count, independently_solved_count,
                    first_solve_minutes, first_exposure, consulted_materials,
                    strict_timed, received_assistance, scoring_method,
                    invalid_reason, trace_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(insert_sql, (*base_values[:-2], "错误地自称无效", *base_values[-2:]))
                connection.rollback()

                invalid_values = list(base_values)
                invalid_values[10] = 0
                invalid_values[12] = 0
                invalid_values.insert(-2, "非首次见题且未严格限时")
                connection.execute(insert_sql, tuple(invalid_values))
                connection.commit()

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["machine_test_missing_audit"], 1)
            self.assertEqual(doctor["status"], "error")


def _machine_test(**changes: object) -> MachineTestInput:
    measurement = MachineTestInput(
        taken_on=date(2026, 8, 9),
        duration_minutes=120,
        language="cpp",
        environment="C++17 / 本地OJ",
        problem_source="默认未见题组",
        difficulty=MachineTestDifficulty.BASIC,
        problem_count=3,
        independently_solved_count=1,
        first_solve_minutes=25,
        first_exposure=True,
        consulted_materials=False,
        strict_timed=True,
    )
    return replace(measurement, **changes)


def _audit_count(application: object) -> int:
    database_path = application.database.database_path
    with closing(sqlite3.connect(database_path)) as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type = 'machine_test_added'"
            ).fetchone()[0]
        )


if __name__ == "__main__":
    unittest.main()
