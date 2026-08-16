from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from tests.support import REPOSITORY_ROOT


EXPLICIT_PROTOCOL_FLAGS = (
    "--first-exposure",
    "--complete-paper-set",
    "--strict-schedule",
    "--authentic-time-slots",
    "--strict-timed",
    "--no-consulted-materials",
    "--no-received-assistance",
    "--no-paused-timer",
    "--no-reviewed-answers-early",
)

EXPECTED_SELECTION_GATE_CODES = (
    "score_window",
    "subject_risk",
    "preference_input_coverage",
    "candidate_structure",
    "candidate_2027_catalog",
    "candidate_ordinary_quota",
    "candidate_retest_contract",
    "candidate_fairness_review",
)

EXPECTED_INCOMPLETE_SELECTION_BLOCKERS = (
    "SCORE_WINDOW_INCOMPLETE",
    "SUBJECT_RISK_NOT_REVIEWABLE",
    "PERSONAL_PREFERENCES_INCOMPLETE",
    "ACTIVE_CANDIDATE_SET_EMPTY",
    "CANDIDATE_CATALOG_NOT_EVALUABLE",
    "CANDIDATE_QUOTA_NOT_EVALUABLE",
    "CANDIDATE_RETEST_CONTRACT_NOT_RECORDED",
    "CANDIDATE_FAIRNESS_REVIEW_NOT_RECORDED",
)


class MockLedgerCliJourneyTest(unittest.TestCase):
    def test_cli_round_trip_preserves_trace_interval_blank_and_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "CLI 完整套卷.sqlite3"

            initialized = _run("--database", str(database), "--json", "init")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            add_result = _run(*_mock_ledger_command(database, "cli-v2-round-trip"))
            self.assertEqual(add_result.returncode, 0, add_result.stderr)
            added = json.loads(add_result.stdout)
            session_id = int(added["session_id"])
            add_trace_id = _validated_uuid(added["trace_id"])
            self.assertEqual(added["ledger_version"], 2)
            self.assertEqual(added["eligibility_status"], "valid")
            self.assertEqual(added["total_lower"], 244.0)
            self.assertEqual(added["total_upper"], 250.0)

            listed = _json_command(
                database,
                "mock-sessions",
                "--session-id",
                str(session_id),
            )
            self.assertEqual(len(listed), 1)
            session = listed[0]
            self.assertEqual(session["session_id"], session_id)
            self.assertEqual(session["trace_id"], str(add_trace_id))
            self.assertEqual(session["eligibility_status"], "valid")
            self.assertTrue(session["is_assessment_eligible"])
            self.assertEqual(session["score_precision_mode"], "interval")
            self.assertEqual(session["total_lower"], 244.0)
            self.assertEqual(session["total_upper"], 250.0)
            subject_results = {
                result["subject_code"]: result for result in session["subject_results"]
            }
            self.assertEqual(subject_results["101"]["score_lower"], 62.0)
            self.assertEqual(subject_results["101"]["score_upper"], 68.0)
            self.assertEqual(
                subject_results["408"]["attendance_status"],
                "present_blank",
            )
            self.assertEqual(subject_results["408"]["score_lower"], 0.0)
            self.assertEqual(subject_results["408"]["score_upper"], 0.0)
            self.assertEqual(
                {result["trace_id"] for result in subject_results.values()},
                {str(add_trace_id)},
            )

            assessment = _json_command(database, "assessment")
            self.assertEqual(assessment["total_session_count"], 1)
            self.assertEqual(assessment["eligible_total_count"], 1)
            self.assertEqual(assessment["session_count"], 1)
            self.assertEqual(assessment["window_session_ids"], [session_id])
            self.assertEqual(
                assessment["statistics"]["total_lower_sequence"],
                [244.0],
            )
            self.assertEqual(
                assessment["statistics"]["total_upper_sequence"],
                [250.0],
            )
            self.assertTrue(assessment["has_score_intervals"])
            self.assertFalse(assessment["is_score_window_ready"])
            self.assertFalse(assessment["is_selection_ready"])
            self.assertIsNone(assessment["total_mean"])
            _assert_selection_gate_contract(self, assessment)

            exclude_result = _run(
                "--database",
                str(database),
                "--json",
                "mock-exclude",
                "--session-id",
                str(session_id),
                "--reason",
                "CLI验收：追加排除事件，不覆盖原始区间分与空白事实",
            )
            self.assertEqual(exclude_result.returncode, 0, exclude_result.stderr)
            excluded = json.loads(exclude_result.stdout)
            exclusion_id = int(excluded["exclusion_id"])
            exclusion_trace_id = _validated_uuid(excluded["trace_id"])
            self.assertNotEqual(exclusion_trace_id, add_trace_id)
            self.assertEqual(excluded["session_id"], session_id)
            self.assertEqual(excluded["status"], "exclusion_appended")

            listed_after_exclusion = _json_command(
                database,
                "mock-sessions",
                "--session-id",
                str(session_id),
            )
            self.assertEqual(len(listed_after_exclusion), 1)
            excluded_session = listed_after_exclusion[0]
            self.assertEqual(excluded_session["eligibility_status"], "excluded")
            self.assertFalse(excluded_session["is_assessment_eligible"])
            self.assertEqual(excluded_session["exclusion_id"], exclusion_id)
            self.assertEqual(len(excluded_session["subject_results"]), 4)

            final_assessment = _json_command(database, "assessment")
            self.assertEqual(final_assessment["total_session_count"], 1)
            self.assertEqual(final_assessment["excluded_session_count"], 1)
            self.assertEqual(final_assessment["eligible_total_count"], 0)
            self.assertEqual(final_assessment["session_count"], 0)
            self.assertEqual(final_assessment["window_session_ids"], [])
            _assert_selection_gate_contract(self, final_assessment)
            self.assertEqual(
                _json_command(database, "mock-sessions", "--eligible-only"),
                [],
            )
            _assert_cli_traces_are_persisted(
                self,
                database,
                session_id,
                exclusion_id,
                str(add_trace_id),
                str(exclusion_trace_id),
            )

    def test_each_protocol_boolean_is_required_before_database_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, omitted_flag in enumerate(EXPLICIT_PROTOCOL_FLAGS):
                with self.subTest(omitted_flag=omitted_flag):
                    database = root / f"missing-flag-{index}.sqlite3"
                    arguments = _mock_ledger_command(
                        database,
                        f"missing-flag-{index}",
                    )
                    arguments.remove(omitted_flag)

                    result = _run(*arguments)

                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("required", result.stderr.lower())
                    self.assertIn(_positive_option_name(omitted_flag), result.stderr)
                    self.assertFalse(database.exists())


def _mock_ledger_command(database: Path, paper_key: str) -> list[str]:
    return [
        "--database",
        str(database),
        "--json",
        "mock-ledger-add",
        "--start-date",
        "2026-09-12",
        "--end-date",
        "2026-09-13",
        "--paper",
        "CLI区间分与到场空白验收卷",
        "--paper-key",
        paper_key,
        "--paper-source",
        "tests/acceptance/test_mock_ledger_cli.py",
        "--paper-content-sha256",
        hashlib.sha256(paper_key.encode("utf-8")).hexdigest(),
        "--paper-family",
        "official_past",
        "--difficulty",
        "standard",
        "--scoring-rule-key",
        "strict-22408-cli-v1",
        "--subject-results-json",
        _subject_results_json(),
        *EXPLICIT_PROTOCOL_FLAGS,
    ]


def _subject_results_json() -> str:
    return json.dumps(
        {
            "101": {
                "attendance_status": "present_scored",
                "score_lower": 62,
                "score_upper": 68,
                "started_at": "2026-09-12T08:30:00+08:00",
                "ended_at": "2026-09-12T11:30:00+08:00",
            },
            "204": {
                "attendance_status": "present_scored",
                "score_lower": 70,
                "score_upper": 70,
                "started_at": "2026-09-12T14:00:00+08:00",
                "ended_at": "2026-09-12T17:00:00+08:00",
            },
            "302": {
                "attendance_status": "present_scored",
                "score_lower": 112,
                "score_upper": 112,
                "started_at": "2026-09-13T08:30:00+08:00",
                "ended_at": "2026-09-13T11:30:00+08:00",
            },
            "408": {
                "attendance_status": "present_blank",
                "started_at": "2026-09-13T14:00:00+08:00",
                "ended_at": "2026-09-13T17:00:00+08:00",
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _json_command(database: Path, command: str, *arguments: str):
    result = _run(
        "--database",
        str(database),
        "--json",
        command,
        *arguments,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


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


def _validated_uuid(value: str) -> uuid.UUID:
    parsed = uuid.UUID(value)
    if str(parsed) != value:
        raise AssertionError(f"TraceId不是规范UUID：{value}")
    return parsed


def _positive_option_name(option: str) -> str:
    return option.replace("--no-", "--", 1)


def _assert_selection_gate_contract(
    testcase: unittest.TestCase,
    assessment: dict[str, object],
) -> None:
    testcase.assertEqual(
        assessment["selection_gate_version"],
        "selection-readiness-v3",
    )
    gates = assessment["selection_gates"]
    testcase.assertIsInstance(gates, list)
    testcase.assertEqual(
        tuple(gate["code"] for gate in gates),
        EXPECTED_SELECTION_GATE_CODES,
    )
    testcase.assertEqual(
        tuple(gate["status"] for gate in gates),
        ("blocked", "blocked", "blocked")
        + ("not_evaluable",) * 5,
    )
    for gate in gates:
        testcase.assertEqual(
            set(gate),
            {"code", "status", "blocking_reason", "details"},
        )
        testcase.assertIsInstance(gate["details"], dict)

    derived_blockers: list[str] = []
    for gate in gates:
        blocking_reason = gate["blocking_reason"]
        if (
            gate["status"] == "passed"
            or blocking_reason is None
            or blocking_reason in derived_blockers
        ):
            continue
        derived_blockers.append(blocking_reason)
    testcase.assertEqual(
        tuple(assessment["selection_blocking_reasons"]),
        EXPECTED_INCOMPLETE_SELECTION_BLOCKERS,
    )
    testcase.assertEqual(
        assessment["selection_blocking_reasons"],
        derived_blockers,
    )


def _assert_cli_traces_are_persisted(
    testcase: unittest.TestCase,
    database: Path,
    session_id: int,
    exclusion_id: int,
    add_trace_id: str,
    exclusion_trace_id: str,
) -> None:
    with closing(sqlite3.connect(database)) as connection:
        session_trace = connection.execute(
            "SELECT trace_id FROM mock_exam_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()[0]
        subject_traces = {
            row[0]
            for row in connection.execute(
                "SELECT trace_id FROM mock_exam_subject_results WHERE session_id = ?",
                (session_id,),
            )
        }
        exclusion_trace = connection.execute(
            "SELECT trace_id FROM mock_exam_session_exclusions WHERE id = ?",
            (exclusion_id,),
        ).fetchone()[0]
        audit_rows = set(
            connection.execute(
                """
                SELECT trace_id, event_type, entity_type, entity_id
                FROM audit_events
                WHERE (trace_id = ? AND entity_id = ?)
                   OR (trace_id = ? AND entity_id = ?)
                """,
                (
                    add_trace_id,
                    str(session_id),
                    exclusion_trace_id,
                    str(exclusion_id),
                ),
            ).fetchall()
        )
    testcase.assertEqual(session_trace, add_trace_id)
    testcase.assertEqual(subject_traces, {add_trace_id})
    testcase.assertEqual(exclusion_trace, exclusion_trace_id)
    testcase.assertIn(
        (
            add_trace_id,
            "mock_exam_added",
            "mock_exam_session",
            str(session_id),
        ),
        audit_rows,
    )
    testcase.assertIn(
        (
            exclusion_trace_id,
            "mock_exam_excluded",
            "mock_exam_session_exclusion",
            str(exclusion_id),
        ),
        audit_rows,
    )


if __name__ == "__main__":
    unittest.main()
