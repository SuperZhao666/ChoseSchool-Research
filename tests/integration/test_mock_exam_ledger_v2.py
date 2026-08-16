from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Mapping

from tests.support import build_test_application

from chose_school.domain.enums import (
    MockAttendanceStatus,
    MockDifficulty,
    MockInvalidReasonCode,
    MockPaperFamily,
    ScoreBand,
)
from chose_school.domain.errors import StateConflictError, ValidationError
from chose_school.domain.models import (
    MockExamInput,
    MockExamLedgerInput,
    MockSubjectResultInput,
)


CHINA_TIMEZONE = timezone(timedelta(hours=8))
SUBJECT_CODES = ("101", "204", "302", "408")


class MockExamLedgerV2Test(unittest.TestCase):
    def test_migration_14_builds_ledger_schema_on_an_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))

            with closing(sqlite3.connect(settings.database_path)) as connection:
                versions = tuple(
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                )
                objects = {
                    (row[0], row[1])
                    for row in connection.execute(
                        """
                        SELECT type, name
                        FROM sqlite_master
                        WHERE name LIKE 'mock_exam_%'
                           OR name = 'v_mock_exam_ledger_sessions'
                        """
                    )
                }
                session_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(mock_exam_sessions)")
                }

            self.assertIn(14, versions)
            self.assertIn(("table", "mock_exam_subject_results"), objects)
            self.assertIn(("table", "mock_exam_session_exclusions"), objects)
            self.assertIn(("view", "v_mock_exam_ledger_sessions"), objects)
            self.assertIn(("trigger", "mock_exam_sessions_no_update"), objects)
            self.assertIn(("trigger", "mock_exam_subject_results_no_delete"), objects)
            self.assertIn(("trigger", "mock_exam_session_exclusions_no_update"), objects)
            self.assertTrue(
                {
                    "ledger_version",
                    "trace_id",
                    "completed_on",
                    "paper_key",
                    "exam_contract",
                    "scoring_rule_key",
                }.issubset(session_columns)
            )
            self.assertEqual(application.assessment.summarize().total_session_count, 0)

    def test_legacy_mock_is_audited_but_never_enters_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            trace_id = str(uuid.uuid4())
            session_id = application.assessment.add_mock_exam(
                MockExamInput(
                    taken_on=date(2026, 9, 1),
                    paper_name="旧版精确分入口",
                    politics_score=70,
                    english_score=75,
                    math_score=120,
                    computer_science_score=125,
                    strict_timed=True,
                ),
                trace_id,
            )

            summary = application.assessment.summarize()
            sessions = application.assessment.list_mock_exams(include_legacy=True)

            self.assertEqual(summary.total_session_count, 1)
            self.assertEqual(summary.legacy_session_count, 1)
            self.assertEqual(summary.eligible_total_count, 0)
            self.assertEqual(summary.session_count, 0)
            self.assertFalse(summary.is_score_window_ready)
            self.assertFalse(summary.is_selection_ready)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["session_id"], session_id)
            self.assertEqual(sessions[0]["ledger_version"], 1)
            self.assertEqual(sessions[0]["eligibility_status"], "legacy_unverified")
            self.assertFalse(sessions[0]["is_assessment_eligible"])
            self.assertEqual(len(sessions[0]["legacy_scores"]), 4)

            with closing(sqlite3.connect(settings.database_path)) as connection:
                audit_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE trace_id = ?
                      AND event_type = 'mock_exam_added'
                      AND entity_id = ?
                    """,
                    (trace_id, str(session_id)),
                ).fetchone()[0]
            self.assertEqual(audit_count, 1)

    def test_exact_interval_blank_and_absent_have_distinct_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            first_day = date(2026, 9, 1)

            exact = application.assessment.add_mock_exam_ledger(
                _ledger(
                    first_day,
                    "exact",
                    _explicit_bounds((62, 71, 112, 121)),
                ),
                str(uuid.uuid4()),
            )
            interval = application.assessment.add_mock_exam_ledger(
                _ledger(
                    first_day + timedelta(days=3),
                    "interval",
                    {
                        "101": (62, 68),
                        "204": (71, 74),
                        "302": (112, 112),
                        "408": (121, 126),
                    },
                ),
                str(uuid.uuid4()),
            )
            blank = application.assessment.add_mock_exam_ledger(
                _ledger(
                    first_day + timedelta(days=6),
                    "blank",
                    _explicit_bounds((62, 71, 112, 0)),
                    attendance={"408": MockAttendanceStatus.PRESENT_BLANK},
                ),
                str(uuid.uuid4()),
            )
            absent = application.assessment.add_mock_exam_ledger(
                _ledger(
                    first_day + timedelta(days=9),
                    "absent",
                    _explicit_bounds((62, 71, 112, 0)),
                    attendance={"408": MockAttendanceStatus.ABSENT},
                ),
                str(uuid.uuid4()),
            )

            self.assertEqual(exact.eligibility_status, "valid")
            self.assertEqual(exact.total_lower, 366.0)
            self.assertEqual(exact.total_upper, 366.0)
            self.assertEqual(interval.eligibility_status, "valid")
            self.assertEqual(interval.total_lower, 366.0)
            self.assertEqual(interval.total_upper, 380.0)
            self.assertEqual(blank.eligibility_status, "valid")
            self.assertEqual(blank.total_lower, 245.0)
            self.assertEqual(blank.total_upper, 245.0)
            self.assertEqual(absent.eligibility_status, "absent_subject")

            sessions = {
                session["session_id"]: session
                for session in application.assessment.list_mock_exams()
            }
            self.assertEqual(sessions[exact.session_id]["score_precision_mode"], "exact")
            self.assertEqual(
                sessions[interval.session_id]["score_precision_mode"], "interval"
            )
            blank_result = _subject_result(sessions[blank.session_id], "408")
            self.assertEqual(blank_result["attendance_status"], "present_blank")
            self.assertEqual(blank_result["score_lower"], 0.0)
            self.assertEqual(blank_result["score_upper"], 0.0)
            absent_result = _subject_result(sessions[absent.session_id], "408")
            self.assertEqual(absent_result["attendance_status"], "absent")
            self.assertIsNone(absent_result["score_lower"])
            self.assertIsNone(absent_result["score_upper"])
            self.assertIsNone(absent_result["started_at"])
            self.assertIsNone(absent_result["ended_at"])
            self.assertFalse(sessions[absent.session_id]["is_assessment_eligible"])

            summary = application.assessment.summarize()
            self.assertEqual(summary.total_session_count, 4)
            self.assertEqual(summary.eligible_total_count, 3)
            self.assertEqual(summary.invalid_session_count, 1)

    def test_protocol_failures_are_retained_but_ineligible(self) -> None:
        failure_cases = (
            (
                "not-first",
                {"first_exposure": False},
                MockInvalidReasonCode.NOT_FIRST_EXPOSURE,
            ),
            (
                "materials",
                {"consulted_materials": True},
                MockInvalidReasonCode.CONSULTED_MATERIALS,
            ),
            (
                "assistance",
                {"received_assistance": True},
                MockInvalidReasonCode.RECEIVED_ASSISTANCE,
            ),
            (
                "paused",
                {"paused_timer": True},
                MockInvalidReasonCode.PAUSED_TIMER,
            ),
            (
                "answers-early",
                {"reviewed_answers_early": True},
                MockInvalidReasonCode.REVIEWED_ANSWERS_EARLY,
            ),
            (
                "not-timed",
                {"strict_timed": False},
                MockInvalidReasonCode.NOT_STRICT_TIMED,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            first_day = date(2026, 9, 1)
            session_ids: list[int] = []
            for index, (paper_key, flags, reason_code) in enumerate(failure_cases):
                with self.subTest(paper_key=paper_key):
                    result = application.assessment.add_mock_exam_ledger(
                        _ledger(
                            first_day + timedelta(days=index * 3),
                            paper_key,
                            _bounds_for_total(330),
                            invalid_reason_code=reason_code,
                            invalid_reason_note=f"受控测试：{paper_key}",
                            **flags,
                        ),
                        str(uuid.uuid4()),
                    )
                    self.assertEqual(result.eligibility_status, "invalid_execution")
                    session_ids.append(result.session_id)

            sessions = application.assessment.list_mock_exams()
            self.assertEqual(
                {session["session_id"] for session in sessions}, set(session_ids)
            )
            self.assertTrue(
                all(session["eligibility_status"] == "invalid_execution" for session in sessions)
            )
            self.assertTrue(
                all(not session["is_assessment_eligible"] for session in sessions)
            )
            summary = application.assessment.summarize()
            self.assertEqual(summary.total_session_count, len(failure_cases))
            self.assertEqual(summary.invalid_session_count, len(failure_cases))
            self.assertEqual(summary.eligible_total_count, 0)
            self.assertEqual(summary.session_count, 0)

    def test_duplicate_content_overlap_and_false_authentic_slots_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            first = _ledger(date(2026, 9, 1), "identity-a", _bounds_for_total(330))
            application.assessment.add_mock_exam_ledger(first, str(uuid.uuid4()))

            renamed_duplicate = replace(
                _ledger(date(2026, 9, 4), "identity-b", _bounds_for_total(330)),
                paper_content_sha256=first.paper_content_sha256,
            )
            with self.assertRaises(StateConflictError) as duplicate_context:
                application.assessment.add_mock_exam_ledger(
                    renamed_duplicate,
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                duplicate_context.exception.error_code,
                "MOCK_EXAM_LEDGER_ALREADY_EXISTS",
            )

            overlapping = _ledger(
                date(2026, 9, 2),
                "overlapping-dates",
                _bounds_for_total(330),
            )
            with self.assertRaises(StateConflictError) as overlap_context:
                application.assessment.add_mock_exam_ledger(
                    overlapping,
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                overlap_context.exception.error_code,
                "MOCK_EXAM_DATE_OVERLAP",
            )

            wrong_slot = _ledger(
                date(2026, 9, 7),
                "wrong-authentic-slot",
                _bounds_for_total(330),
            )
            politics = wrong_slot.subject_results["101"]
            wrong_subjects = dict(wrong_slot.subject_results)
            wrong_subjects["101"] = replace(
                politics,
                started_at=politics.started_at + timedelta(minutes=1),
                ended_at=politics.ended_at + timedelta(minutes=1),
            )
            with self.assertRaises(ValidationError) as slot_context:
                application.assessment.add_mock_exam_ledger(
                    replace(wrong_slot, subject_results=wrong_subjects),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                slot_context.exception.error_code,
                "MOCK_SUBJECT_SLOT_MISMATCH",
            )

    def test_exclusion_is_additive_and_all_mock_tables_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            legacy_id = application.assessment.add_mock_exam(
                MockExamInput(
                    taken_on=date(2026, 8, 20),
                    paper_name="legacy-for-immutability",
                    politics_score=60,
                    english_score=60,
                    math_score=100,
                    computer_science_score=100,
                    strict_timed=True,
                ),
                str(uuid.uuid4()),
            )
            ledger_result = application.assessment.add_mock_exam_ledger(
                _ledger(date(2026, 9, 1), "exclude-me", _bounds_for_total(330)),
                str(uuid.uuid4()),
            )
            exclusion_trace = str(uuid.uuid4())
            exclusion_id = application.assessment.exclude_mock_exam(
                ledger_result.session_id,
                "事后发现卷面不完整；保留原始行并追加排除事件",
                exclusion_trace,
            )

            session = application.assessment.list_mock_exams(
                session_id=ledger_result.session_id
            )[0]
            self.assertEqual(session["eligibility_status"], "excluded")
            self.assertFalse(session["is_assessment_eligible"])
            self.assertEqual(session["exclusion_id"], exclusion_id)
            self.assertEqual(len(session["subject_results"]), 4)
            summary = application.assessment.summarize()
            self.assertEqual(summary.total_session_count, 2)
            self.assertEqual(summary.legacy_session_count, 1)
            self.assertEqual(summary.excluded_session_count, 1)
            self.assertEqual(summary.eligible_total_count, 0)

            with closing(sqlite3.connect(settings.database_path)) as connection:
                profile_id = connection.execute(
                    "SELECT profile_id FROM mock_exam_sessions WHERE id = ?",
                    (ledger_result.session_id,),
                ).fetchone()[0]
                subject_result_id = connection.execute(
                    "SELECT id FROM mock_exam_subject_results WHERE session_id = ? LIMIT 1",
                    (ledger_result.session_id,),
                ).fetchone()[0]
                audit_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM audit_events
                    WHERE trace_id = ?
                      AND event_type = 'mock_exam_excluded'
                      AND entity_id = ?
                    """,
                    (exclusion_trace, str(exclusion_id)),
                ).fetchone()[0]
            self.assertEqual(audit_count, 1)

            rejected_statements = (
                ("UPDATE mock_exam_sessions SET notes = 'tampered' WHERE id = ?", (ledger_result.session_id,)),
                ("DELETE FROM mock_exam_sessions WHERE id = ?", (legacy_id,)),
                ("UPDATE mock_exam_scores SET score = 1 WHERE session_id = ?", (legacy_id,)),
                ("DELETE FROM mock_exam_scores WHERE session_id = ?", (legacy_id,)),
                ("UPDATE mock_exam_subject_results SET note = 'tampered' WHERE id = ?", (subject_result_id,)),
                ("DELETE FROM mock_exam_subject_results WHERE id = ?", (subject_result_id,)),
                ("UPDATE mock_exam_session_exclusions SET reason = 'tampered' WHERE id = ?", (exclusion_id,)),
                ("DELETE FROM mock_exam_session_exclusions WHERE id = ?", (exclusion_id,)),
                ("DELETE FROM applicant_profiles WHERE id = ?", (profile_id,)),
            )
            for statement, parameters in rejected_statements:
                with self.subTest(statement=statement):
                    _assert_sql_rejected(
                        self,
                        settings.database_path,
                        statement,
                        parameters,
                    )

            with closing(sqlite3.connect(settings.database_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM mock_exam_sessions"
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM mock_exam_subject_results"
                    ).fetchone()[0],
                    4,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM mock_exam_session_exclusions"
                    ).fetchone()[0],
                    1,
                )

    def test_doctor_accepts_clean_ledger_and_detects_missing_audits(self) -> None:
        error_metric_names = (
            "mock_v2_missing_audit",
            "mock_exclusion_missing_audit",
            "legacy_mock_missing_audit",
            "mock_v2_subject_count_mismatch",
            "mock_v2_subject_code_mismatch",
            "mock_subject_trace_mismatch",
            "mock_v2_attendance_score_mismatch",
            "mock_v2_validity_reason_mismatch",
            "mock_v2_scoring_rule_missing",
            "mock_v2_protocol_fact_missing",
            "mock_v2_subject_schedule_mismatch",
            "mock_v2_subject_maximum_mismatch",
            "mock_v2_calendar_overlap",
            "mock_v2_paper_key_reuse_mismatch",
            "mock_v2_content_hash_reuse_mismatch",
        )
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            legacy_id = application.assessment.add_mock_exam(
                MockExamInput(
                    taken_on=date(2026, 8, 20),
                    paper_name="legacy-doctor-fixture",
                    politics_score=60,
                    english_score=60,
                    math_score=100,
                    computer_science_score=100,
                    strict_timed=True,
                ),
                str(uuid.uuid4()),
            )
            ledger_result = application.assessment.add_mock_exam_ledger(
                _ledger(date(2026, 9, 1), "doctor-v2", _bounds_for_total(330)),
                str(uuid.uuid4()),
            )
            exclusion_id = application.assessment.exclude_mock_exam(
                ledger_result.session_id,
                "doctor排除审计基线",
                str(uuid.uuid4()),
            )

            clean = application.catalog.doctor()
            self.assertEqual(clean["status"], "ok")
            self.assertEqual(clean["legacy_mock_session_count"], 1)
            for metric_name in error_metric_names:
                with self.subTest(clean_metric=metric_name):
                    self.assertEqual(clean[metric_name], 0)

            with closing(sqlite3.connect(settings.database_path)) as connection:
                connection.execute("DROP TRIGGER protect_audit_events_delete")
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE event_type = 'mock_exam_added'
                      AND entity_type = 'mock_exam_session'
                      AND entity_id IN (?, ?)
                    """,
                    (str(legacy_id), str(ledger_result.session_id)),
                )
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE event_type = 'mock_exam_excluded'
                      AND entity_type = 'mock_exam_session_exclusion'
                      AND entity_id = ?
                    """,
                    (str(exclusion_id),),
                )
                connection.commit()

            corrupted = application.catalog.doctor()
            self.assertEqual(corrupted["status"], "error")
            self.assertEqual(corrupted["mock_v2_missing_audit"], 1)
            self.assertEqual(corrupted["mock_exclusion_missing_audit"], 1)
            self.assertEqual(corrupted["legacy_mock_missing_audit"], 1)
            for metric_name in error_metric_names[3:]:
                with self.subTest(corrupted_metric=metric_name):
                    self.assertEqual(corrupted[metric_name], 0)

    def test_latest_five_use_second_low_third_low_and_do_not_mix_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            first_day = date(2026, 9, 1)
            totals = (300, 320, 310, 340, 330)
            session_ids = []
            for index, total in enumerate(totals):
                result = application.assessment.add_mock_exam_ledger(
                    _ledger(
                        first_day + timedelta(days=index * 3),
                        f"window-{index + 1}",
                        _bounds_for_total(total),
                    ),
                    str(uuid.uuid4()),
                )
                session_ids.append(result.session_id)

            summary = application.assessment.summarize()
            self.assertTrue(summary.is_score_window_ready)
            self.assertFalse(summary.is_selection_ready)
            self.assertEqual(summary.window_session_ids, tuple(session_ids))
            self.assertEqual(summary.statistics.total_lower_sequence, totals)
            self.assertEqual(summary.statistics.conservative_total_lower, 310.0)
            self.assertEqual(summary.statistics.typical_total_lower, 320.0)
            self.assertEqual(summary.conservative_total, 310.0)

            sixth = application.assessment.add_mock_exam_ledger(
                _ledger(
                    first_day + timedelta(days=15),
                    "window-6",
                    _bounds_for_total(350),
                ),
                str(uuid.uuid4()),
            )
            rolled = application.assessment.summarize()
            self.assertEqual(
                rolled.window_session_ids,
                tuple(session_ids[1:]) + (sixth.session_id,),
            )
            self.assertEqual(
                rolled.statistics.total_lower_sequence,
                (320.0, 310.0, 340.0, 330.0, 350.0),
            )
            self.assertEqual(rolled.statistics.conservative_total_lower, 320.0)
            self.assertEqual(rolled.statistics.typical_total_lower, 330.0)

            isolated = application.assessment.add_mock_exam_ledger(
                _ledger(
                    first_day + timedelta(days=18),
                    "different-rule",
                    _bounds_for_total(400),
                    scoring_rule_key="different-scoring-rule",
                ),
                str(uuid.uuid4()),
            )
            isolated_summary = application.assessment.summarize()
            self.assertEqual(isolated_summary.eligible_total_count, 7)
            self.assertEqual(len(isolated_summary.comparison_groups), 2)
            self.assertEqual(isolated_summary.session_count, 1)
            self.assertEqual(isolated_summary.window_session_ids, (isolated.session_id,))
            self.assertEqual(
                isolated_summary.statistics.total_lower_sequence,
                (400.0,),
            )
            self.assertFalse(isolated_summary.is_score_window_ready)
            self.assertIsNone(isolated_summary.statistics.conservative_total_lower)
            self.assertIsNone(isolated_summary.statistics.typical_total_lower)

    def test_interval_window_preserves_bounds_and_never_uses_midpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            first_day = date(2026, 9, 1)
            lower_totals = (300, 320, 310, 340, 330)
            upper_totals = (340, 360, 350, 380, 370)
            for index, (lower, upper) in enumerate(zip(lower_totals, upper_totals)):
                application.assessment.add_mock_exam_ledger(
                    _ledger(
                        first_day + timedelta(days=index * 3),
                        f"interval-window-{index + 1}",
                        _bounds_for_total(lower, upper),
                    ),
                    str(uuid.uuid4()),
                )

            summary = application.assessment.summarize()

            self.assertTrue(summary.is_score_window_ready)
            self.assertTrue(summary.has_score_intervals)
            self.assertIsNone(summary.total_mean)
            self.assertIsNone(summary.total_standard_deviation)
            self.assertIsNone(summary.conservative_total)
            self.assertEqual(summary.subject_means, {})
            self.assertEqual(summary.statistics.total_lower_sequence, lower_totals)
            self.assertEqual(summary.statistics.total_upper_sequence, upper_totals)
            self.assertEqual(summary.statistics.total_lower_mean, 320.0)
            self.assertEqual(summary.statistics.total_upper_mean, 360.0)
            self.assertEqual(summary.statistics.conservative_total_lower, 310.0)
            self.assertEqual(summary.statistics.conservative_total_upper, 350.0)
            self.assertEqual(summary.statistics.typical_total_lower, 320.0)
            self.assertEqual(summary.statistics.typical_total_upper, 360.0)
            self.assertNotEqual(summary.statistics.total_lower_mean, 340.0)

    def test_all_nine_decimal_band_boundaries_and_cross_band_guard(self) -> None:
        boundary_cases = (
            (289.99, ScoreBand.BELOW_290.value),
            (290.0, ScoreBand.FROM_290_TO_304.value),
            (304.99, ScoreBand.FROM_290_TO_304.value),
            (305.0, ScoreBand.FROM_305_TO_314.value),
            (314.99, ScoreBand.FROM_305_TO_314.value),
            (315.0, ScoreBand.FROM_315_TO_324.value),
            (324.99, ScoreBand.FROM_315_TO_324.value),
            (325.0, ScoreBand.FROM_325_TO_334.value),
            (334.99, ScoreBand.FROM_325_TO_334.value),
            (335.0, ScoreBand.FROM_335_TO_344.value),
            (344.99, ScoreBand.FROM_335_TO_344.value),
            (345.0, ScoreBand.FROM_345_TO_359.value),
            (359.99, ScoreBand.FROM_345_TO_359.value),
            (360.0, ScoreBand.FROM_360_TO_379.value),
            (379.99, ScoreBand.FROM_360_TO_379.value),
            (380.0, ScoreBand.AT_LEAST_380.value),
        )
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            next_day = date(2026, 8, 1)
            for case_index, (total, expected_band) in enumerate(boundary_cases):
                scoring_rule = f"boundary-{case_index}"
                for sample_index in range(5):
                    application.assessment.add_mock_exam_ledger(
                        _ledger(
                            next_day,
                            f"boundary-{case_index}-{sample_index}",
                            _bounds_for_total(total),
                            scoring_rule_key=scoring_rule,
                        ),
                        str(uuid.uuid4()),
                    )
                    next_day += timedelta(days=3)
                with self.subTest(total=total, expected_band=expected_band):
                    summary = application.assessment.summarize()
                    self.assertTrue(summary.is_score_window_ready)
                    self.assertEqual(summary.band.conservative_band, expected_band)
                    self.assertEqual(summary.band.occupied_bands, (expected_band,))
                    self.assertEqual(summary.band.role_band, expected_band)
                    self.assertFalse(summary.band.multi_band_guard_applied)

            guard_totals = (304.5, 305.0, 306.0, 307.0, 308.0)
            for sample_index, total in enumerate(guard_totals):
                application.assessment.add_mock_exam_ledger(
                    _ledger(
                        next_day,
                        f"cross-band-{sample_index}",
                        _bounds_for_total(total),
                        scoring_rule_key="cross-band-guard",
                    ),
                    str(uuid.uuid4()),
                )
                next_day += timedelta(days=3)

            guarded = application.assessment.summarize()
            self.assertEqual(guarded.statistics.conservative_total_lower, 305.0)
            self.assertEqual(
                guarded.band.conservative_band,
                ScoreBand.FROM_305_TO_314.value,
            )
            self.assertEqual(
                guarded.band.occupied_bands,
                (
                    ScoreBand.FROM_290_TO_304.value,
                    ScoreBand.FROM_305_TO_314.value,
                ),
            )
            self.assertTrue(guarded.band.multi_band_guard_applied)
            self.assertEqual(
                guarded.band.role_band,
                ScoreBand.FROM_290_TO_304.value,
            )


def _ledger(
    started_on: date,
    paper_key: str,
    score_bounds: Mapping[str, tuple[float, float]],
    *,
    attendance: Mapping[str, MockAttendanceStatus] | None = None,
    scoring_rule_key: str = "strict-22408-manual-v1",
    first_exposure: bool = True,
    complete_paper_set: bool = True,
    strict_schedule: bool = True,
    authentic_time_slots: bool = True,
    strict_timed: bool = True,
    consulted_materials: bool = False,
    received_assistance: bool = False,
    paused_timer: bool = False,
    reviewed_answers_early: bool = False,
    invalid_reason_code: MockInvalidReasonCode | None = None,
    invalid_reason_note: str | None = None,
) -> MockExamLedgerInput:
    completed_on = started_on + timedelta(days=1)
    attendance = attendance or {}
    subject_times = {
        "101": (datetime.combine(started_on, time(8, 30), CHINA_TIMEZONE),),
        "204": (datetime.combine(started_on, time(14, 0), CHINA_TIMEZONE),),
        "302": (datetime.combine(completed_on, time(8, 30), CHINA_TIMEZONE),),
        "408": (datetime.combine(completed_on, time(14, 0), CHINA_TIMEZONE),),
    }
    subject_results: dict[str, MockSubjectResultInput] = {}
    for subject_code in SUBJECT_CODES:
        status = attendance.get(subject_code, MockAttendanceStatus.PRESENT_SCORED)
        lower, upper = score_bounds[subject_code]
        if status is MockAttendanceStatus.ABSENT:
            subject_results[subject_code] = MockSubjectResultInput(
                attendance_status=status,
                score_lower=None,
                score_upper=None,
                started_at=None,
                ended_at=None,
            )
            continue
        started_at = subject_times[subject_code][0]
        subject_results[subject_code] = MockSubjectResultInput(
            attendance_status=status,
            score_lower=(None if status is MockAttendanceStatus.PRESENT_BLANK else lower),
            score_upper=(None if status is MockAttendanceStatus.PRESENT_BLANK else upper),
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=180),
        )

    return MockExamLedgerInput(
        started_on=started_on,
        completed_on=completed_on,
        paper_name=f"完整套卷 {paper_key}",
        paper_key=paper_key,
        paper_source="tests/integration/test_mock_exam_ledger_v2.py",
        paper_content_sha256=hashlib.sha256(paper_key.encode("utf-8")).hexdigest(),
        paper_family=MockPaperFamily.OFFICIAL_PAST,
        difficulty=MockDifficulty.STANDARD,
        scoring_rule_key=scoring_rule_key,
        first_exposure=first_exposure,
        complete_paper_set=complete_paper_set,
        strict_schedule=strict_schedule,
        authentic_time_slots=authentic_time_slots,
        strict_timed=strict_timed,
        consulted_materials=consulted_materials,
        received_assistance=received_assistance,
        paused_timer=paused_timer,
        reviewed_answers_early=reviewed_answers_early,
        subject_results=subject_results,
        invalid_reason_code=invalid_reason_code,
        invalid_reason_note=invalid_reason_note,
    )


def _explicit_bounds(scores: tuple[float, float, float, float]) -> Mapping[str, tuple[float, float]]:
    return {
        subject_code: (float(score), float(score))
        for subject_code, score in zip(SUBJECT_CODES, scores)
    }


def _bounds_for_total(
    lower_total: float,
    upper_total: float | None = None,
) -> Mapping[str, tuple[float, float]]:
    upper_total = lower_total if upper_total is None else upper_total
    if not (260 <= lower_total <= upper_total <= 410):
        raise ValueError("test helper supports total bounds from 260 through 410")
    return {
        "101": (70.0, 70.0),
        "204": (70.0, 70.0),
        "302": (120.0, 120.0),
        "408": (float(lower_total - 260), float(upper_total - 260)),
    }


def _subject_result(session: Mapping[str, object], subject_code: str) -> Mapping[str, object]:
    return next(
        result
        for result in session["subject_results"]  # type: ignore[index,union-attr]
        if result["subject_code"] == subject_code
    )


def _assert_sql_rejected(
    testcase: unittest.TestCase,
    database_path: Path,
    statement: str,
    parameters: tuple[object, ...],
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with testcase.assertRaises(sqlite3.DatabaseError):
            connection.execute(statement, parameters)
            connection.commit()
        connection.rollback()
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
