from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.models import (
    MockExamLedgerAddResult,
    MockExamLedgerInput,
    MockExamInput,
)
from chose_school.domain.errors import EntityNotFoundError, StateConflictError
from chose_school.infrastructure.database import Database


_MOCK_LEDGER_SESSION_INSERT = """
    INSERT INTO mock_exam_sessions(
        profile_id, taken_on, paper_name, attempt_number,
        strict_timed, notes, created_at, ledger_version,
        trace_id, completed_on, paper_key, paper_source,
        paper_content_sha256, exam_contract, first_exposure,
        complete_paper_set, strict_schedule, authentic_time_slots,
        consulted_materials, received_assistance, paused_timer,
        reviewed_answers_early, paper_family, difficulty_label,
        scoring_rule_key, invalid_reason_code, invalid_reason_note
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
"""

_MOCK_SUBJECT_RESULT_INSERT = """
    INSERT INTO mock_exam_subject_results(
        session_id, subject_code, attendance_status,
        score_lower, score_upper, maximum_score,
        started_at, ended_at, actual_duration_minutes,
        note, trace_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class SqliteAssessmentRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_id(self, profile_key: str) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        return int(row["id"]) if row else None

    def ensure_default_profile(
        self,
        profile_key: str,
        undergraduate_school: str,
        undergraduate_major: str,
        target_year: int,
        politics_code: str,
        english_code: str,
        math_code: str,
        professional_code: str,
        target_degree_type: str,
        target_tier: str,
        trace_id: str,
    ) -> int:
        now = _utc_now()
        with self._database.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
            if existing:
                return int(existing["id"])

            cursor = connection.execute(
                """
                INSERT INTO applicant_profiles(
                    profile_key, undergraduate_school, undergraduate_major,
                    target_exam_year, politics_code, english_code, math_code,
                    professional_code, target_degree_type, target_tier,
                    preferences_json, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?)
                """,
                (
                    profile_key,
                    undergraduate_school,
                    undergraduate_major,
                    target_year,
                    politics_code,
                    english_code,
                    math_code,
                    professional_code,
                    target_degree_type,
                    target_tier,
                    "用户画像来自两份深度研究报告；可通过后续迁移扩展偏好字段",
                    now,
                    now,
                ),
            )
            profile_id = int(cursor.lastrowid)
            _insert_audit_event(
                connection,
                trace_id,
                "profile_created",
                "applicant_profile",
                str(profile_id),
                {"profile_key": profile_key},
            )
            connection.commit()
            return profile_id

    def add_mock_exam(
        self,
        profile_id: int,
        mock_exam: MockExamInput,
        trace_id: str,
    ) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                profile = connection.execute(
                    """
                    SELECT politics_code, english_code, math_code, professional_code
                    FROM applicant_profiles WHERE id = ?
                    """,
                    (profile_id,),
                ).fetchone()
                if profile is None:
                    raise EntityNotFoundError(
                        "PROFILE_NOT_FOUND",
                        f"applicant profile does not exist: {profile_id}",
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO mock_exam_sessions(
                        profile_id, taken_on, paper_name, attempt_number,
                        strict_timed, notes, created_at, ledger_version, trace_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        profile_id,
                        mock_exam.taken_on.isoformat(),
                        mock_exam.paper_name,
                        mock_exam.attempt_number,
                        int(mock_exam.strict_timed),
                        mock_exam.notes,
                        _utc_now(),
                        trace_id,
                    ),
                )
                session_id = int(cursor.lastrowid)
                scores = (
                    (profile["politics_code"], mock_exam.politics_score, 100),
                    (profile["english_code"], mock_exam.english_score, 100),
                    (profile["math_code"], mock_exam.math_score, 150),
                    (profile["professional_code"], mock_exam.computer_science_score, 150),
                )
                connection.executemany(
                    """
                    INSERT INTO mock_exam_scores(
                        session_id, subject_code, score, maximum_score
                    ) VALUES (?, ?, ?, ?)
                    """,
                    ((session_id, code, score, maximum) for code, score, maximum in scores),
                )
                _insert_audit_event(
                    connection,
                    trace_id,
                    "mock_exam_added",
                    "mock_exam_session",
                    str(session_id),
                    {
                        "taken_on": mock_exam.taken_on.isoformat(),
                        "paper_name": mock_exam.paper_name,
                        "attempt_number": mock_exam.attempt_number,
                        "strict_timed": mock_exam.strict_timed,
                        "ledger_version": 1,
                        "eligibility_status": "legacy_unverified",
                    },
                )
                connection.commit()
                return session_id
            except Exception:
                connection.rollback()
                raise

    def add_mock_exam_ledger(
        self,
        profile_id: int,
        mock_exam: MockExamLedgerInput,
        trace_id: str,
    ) -> MockExamLedgerAddResult:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                profile = _require_profile(connection, profile_id)
                _ensure_mock_identity_available(
                    connection,
                    profile_id,
                    mock_exam,
                )
                _ensure_mock_dates_available(connection, profile_id, mock_exam)
                now = _utc_now()
                exam_contract, maximum_by_code = _profile_exam_contract(profile)
                session_id = _insert_mock_ledger_session(
                    connection,
                    profile_id,
                    mock_exam,
                    trace_id,
                    now,
                    exam_contract,
                )
                _insert_mock_subject_results(
                    connection,
                    session_id,
                    mock_exam,
                    maximum_by_code,
                    trace_id,
                    now,
                )
                ledger_row = _read_mock_ledger_row(connection, session_id)
                _audit_mock_ledger_add(
                    connection,
                    session_id,
                    mock_exam,
                    exam_contract,
                    str(ledger_row["eligibility_status"]),
                    trace_id,
                )
                connection.commit()
                return _mock_ledger_add_result(session_id, ledger_row)
            except Exception:
                connection.rollback()
                raise

    def list_mock_exam_sessions(
        self,
        profile_id: int,
        include_legacy: bool,
        eligible_only: bool,
        session_id: int | None,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        conditions = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if not include_legacy:
            conditions.append("ledger_version = 2")
        if eligible_only:
            conditions.append("is_assessment_eligible = 1")
        if session_id is not None:
            conditions.append("id = ?")
            parameters.append(session_id)
        parameters.append(limit)
        query = f"""
            SELECT *
            FROM v_mock_exam_ledger_sessions
            WHERE {' AND '.join(conditions)}
            ORDER BY COALESCE(completed_on, taken_on) DESC, id DESC
            LIMIT ?
        """
        with self._database.connect() as connection:
            rows = list(connection.execute(query, parameters).fetchall())
            rows.reverse()
            session_ids = [int(row["id"]) for row in rows]
            subject_results = _load_subject_results(connection, session_ids)
            legacy_scores = _load_legacy_scores(connection, session_ids)
        return tuple(
            _deserialize_mock_session(
                row,
                subject_results.get(int(row["id"]), ()),
                legacy_scores.get(int(row["id"]), ()),
            )
            for row in rows
        )

    def exclude_mock_exam(
        self,
        profile_id: int,
        session_id: int,
        reason: str,
        trace_id: str,
    ) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                session = connection.execute(
                    """
                    SELECT id
                    FROM mock_exam_sessions
                    WHERE id = ? AND profile_id = ?
                    """,
                    (session_id, profile_id),
                ).fetchone()
                if session is None:
                    raise EntityNotFoundError(
                        "MOCK_EXAM_NOT_FOUND",
                        f"mock exam session does not exist: {session_id}",
                    )
                existing = connection.execute(
                    "SELECT id FROM mock_exam_session_exclusions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if existing is not None:
                    raise StateConflictError(
                        "MOCK_EXAM_ALREADY_EXCLUDED",
                        "该完整套卷会话已经追加排除事件",
                        {"exclusion_id": int(existing["id"])},
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO mock_exam_session_exclusions(
                        session_id, reason, trace_id, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (session_id, reason, trace_id, _utc_now()),
                )
                exclusion_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    "mock_exam_excluded",
                    "mock_exam_session_exclusion",
                    str(exclusion_id),
                    {"session_id": session_id, "reason": reason},
                )
                connection.commit()
                return exclusion_id
            except Exception:
                connection.rollback()
                raise

    def strict_mock_totals(self, profile_id: int) -> Sequence[Mapping[str, Any]]:
        sessions = self.list_mock_exam_sessions(
            profile_id,
            include_legacy=False,
            eligible_only=True,
            session_id=None,
            limit=10000,
        )
        return tuple(_legacy_total_projection(session) for session in sessions)


def _require_profile(
    connection: sqlite3.Connection,
    profile_id: int,
) -> sqlite3.Row:
    profile = connection.execute(
        """
        SELECT politics_code, english_code, math_code, professional_code
        FROM applicant_profiles
        WHERE id = ?
        """,
        (profile_id,),
    ).fetchone()
    if profile is None:
        raise EntityNotFoundError(
            "PROFILE_NOT_FOUND",
            f"applicant profile does not exist: {profile_id}",
        )
    return profile


def _ensure_mock_identity_available(
    connection: sqlite3.Connection,
    profile_id: int,
    mock_exam: MockExamLedgerInput,
) -> None:
    existing = connection.execute(
        """
        SELECT id
        FROM mock_exam_sessions
        WHERE profile_id = ?
          AND ledger_version = 2
          AND attempt_number = ?
          AND (
              paper_key = ?
              OR (? IS NOT NULL AND paper_content_sha256 = ?)
          )
        """,
        (
            profile_id,
            mock_exam.attempt_number,
            mock_exam.paper_key,
            mock_exam.paper_content_sha256,
            mock_exam.paper_content_sha256,
        ),
    ).fetchone()
    if existing is not None:
        raise StateConflictError(
            "MOCK_EXAM_LEDGER_ALREADY_EXISTS",
            "同一试卷身份和尝试次数的完整套卷记录已存在",
            {"session_id": int(existing["id"])},
        )


def _ensure_mock_dates_available(
    connection: sqlite3.Connection,
    profile_id: int,
    mock_exam: MockExamLedgerInput,
) -> None:
    overlapping = connection.execute(
        """
        SELECT id
        FROM mock_exam_sessions
        WHERE profile_id = ?
          AND ledger_version = 2
          AND date(?) <= date(completed_on)
          AND date(?) >= date(taken_on)
        ORDER BY completed_on, id
        LIMIT 1
        """,
        (
            profile_id,
            mock_exam.started_on.isoformat(),
            mock_exam.completed_on.isoformat(),
        ),
    ).fetchone()
    if overlapping is not None:
        raise StateConflictError(
            "MOCK_EXAM_DATE_OVERLAP",
            "完整套卷会话的两天考试日期不能与已有套卷重叠",
            {"session_id": int(overlapping["id"])},
        )


def _profile_exam_contract(
    profile: sqlite3.Row,
) -> tuple[str, Mapping[str, float]]:
    subject_codes = tuple(
        str(profile[key])
        for key in (
            "politics_code",
            "english_code",
            "math_code",
            "professional_code",
        )
    )
    maximum_scores = (100.0, 100.0, 150.0, 150.0)
    return "+".join(subject_codes), dict(zip(subject_codes, maximum_scores))


def _insert_mock_ledger_session(
    connection: sqlite3.Connection,
    profile_id: int,
    mock_exam: MockExamLedgerInput,
    trace_id: str,
    created_at: str,
    exam_contract: str,
) -> int:
    cursor = connection.execute(
        _MOCK_LEDGER_SESSION_INSERT,
        _mock_ledger_session_parameters(
            profile_id,
            mock_exam,
            trace_id,
            created_at,
            exam_contract,
        ),
    )
    return int(cursor.lastrowid)


def _mock_ledger_session_parameters(
    profile_id: int,
    mock_exam: MockExamLedgerInput,
    trace_id: str,
    created_at: str,
    exam_contract: str,
) -> tuple[Any, ...]:
    invalid_reason_code = (
        mock_exam.invalid_reason_code.value
        if mock_exam.invalid_reason_code is not None
        else None
    )
    return (
        profile_id,
        mock_exam.started_on.isoformat(),
        mock_exam.paper_name,
        mock_exam.attempt_number,
        int(mock_exam.strict_timed),
        mock_exam.notes,
        created_at,
        2,
        trace_id,
        mock_exam.completed_on.isoformat(),
        mock_exam.paper_key,
        mock_exam.paper_source,
        mock_exam.paper_content_sha256,
        exam_contract,
        int(mock_exam.first_exposure),
        int(mock_exam.complete_paper_set),
        int(mock_exam.strict_schedule),
        int(mock_exam.authentic_time_slots),
        int(mock_exam.consulted_materials),
        int(mock_exam.received_assistance),
        int(mock_exam.paused_timer),
        int(mock_exam.reviewed_answers_early),
        mock_exam.paper_family.value,
        mock_exam.difficulty.value,
        mock_exam.scoring_rule_key,
        invalid_reason_code,
        mock_exam.invalid_reason_note,
    )


def _insert_mock_subject_results(
    connection: sqlite3.Connection,
    session_id: int,
    mock_exam: MockExamLedgerInput,
    maximum_by_code: Mapping[str, float],
    trace_id: str,
    created_at: str,
) -> None:
    for subject_code, maximum_score in maximum_by_code.items():
        result = mock_exam.subject_results[subject_code]
        connection.execute(
            _MOCK_SUBJECT_RESULT_INSERT,
            (
                session_id,
                subject_code,
                result.attendance_status.value,
                result.score_lower,
                result.score_upper,
                maximum_score,
                result.started_at.isoformat() if result.started_at else None,
                result.ended_at.isoformat() if result.ended_at else None,
                _duration_minutes(result.started_at, result.ended_at),
                result.note,
                trace_id,
                created_at,
            ),
        )


def _read_mock_ledger_row(
    connection: sqlite3.Connection,
    session_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT eligibility_status, total_lower, total_upper
        FROM v_mock_exam_ledger_sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("new mock ledger session cannot be read back")
    return row


def _audit_mock_ledger_add(
    connection: sqlite3.Connection,
    session_id: int,
    mock_exam: MockExamLedgerInput,
    exam_contract: str,
    eligibility_status: str,
    trace_id: str,
) -> None:
    payload = {
        "ledger_version": 2,
        "taken_on": mock_exam.started_on.isoformat(),
        "completed_on": mock_exam.completed_on.isoformat(),
        "paper_key": mock_exam.paper_key,
        "attempt_number": mock_exam.attempt_number,
        "exam_contract": exam_contract,
        "paper_family": mock_exam.paper_family.value,
        "difficulty_label": mock_exam.difficulty.value,
        "scoring_rule_key": mock_exam.scoring_rule_key,
        "first_exposure": mock_exam.first_exposure,
        "complete_paper_set": mock_exam.complete_paper_set,
        "strict_schedule": mock_exam.strict_schedule,
        "authentic_time_slots": mock_exam.authentic_time_slots,
        "strict_timed": mock_exam.strict_timed,
        "consulted_materials": mock_exam.consulted_materials,
        "received_assistance": mock_exam.received_assistance,
        "paused_timer": mock_exam.paused_timer,
        "reviewed_answers_early": mock_exam.reviewed_answers_early,
        "eligibility_status": eligibility_status,
    }
    _insert_audit_event(
        connection,
        trace_id,
        "mock_exam_added",
        "mock_exam_session",
        str(session_id),
        payload,
    )


def _mock_ledger_add_result(
    session_id: int,
    ledger_row: sqlite3.Row,
) -> MockExamLedgerAddResult:
    return MockExamLedgerAddResult(
        session_id=session_id,
        ledger_version=2,
        eligibility_status=str(ledger_row["eligibility_status"]),
        total_lower=_optional_float(ledger_row["total_lower"]),
        total_upper=_optional_float(ledger_row["total_upper"]),
    )


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _duration_minutes(
    started_at: datetime | None,
    ended_at: datetime | None,
) -> int | None:
    if started_at is None or ended_at is None:
        return None
    return int((ended_at - started_at).total_seconds() // 60)


def _load_subject_results(
    connection: sqlite3.Connection,
    session_ids: Sequence[int],
) -> Mapping[int, Sequence[Mapping[str, Any]]]:
    grouped: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    if not session_ids:
        return grouped
    placeholders = ", ".join("?" for _ in session_ids)
    rows = connection.execute(
        f"""
        SELECT id AS result_id, session_id, subject_code, attendance_status,
               score_lower, score_upper, maximum_score, started_at, ended_at,
               actual_duration_minutes, note, trace_id, created_at
        FROM mock_exam_subject_results
        WHERE session_id IN ({placeholders})
        ORDER BY session_id,
                 CASE subject_code
                     WHEN '101' THEN 1 WHEN '204' THEN 2
                     WHEN '302' THEN 3 WHEN '408' THEN 4 ELSE 5
                 END,
                 id
        """,
        tuple(session_ids),
    ).fetchall()
    for row in rows:
        grouped[int(row["session_id"])].append(dict(row))
    return grouped


def _load_legacy_scores(
    connection: sqlite3.Connection,
    session_ids: Sequence[int],
) -> Mapping[int, Sequence[Mapping[str, Any]]]:
    grouped: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    if not session_ids:
        return grouped
    placeholders = ", ".join("?" for _ in session_ids)
    rows = connection.execute(
        f"""
        SELECT session_id, subject_code, score, maximum_score, duration_minutes
        FROM mock_exam_scores
        WHERE session_id IN ({placeholders})
        ORDER BY session_id,
                 CASE subject_code
                     WHEN '101' THEN 1 WHEN '204' THEN 2
                     WHEN '302' THEN 3 WHEN '408' THEN 4 ELSE 5
                 END
        """,
        tuple(session_ids),
    ).fetchall()
    for row in rows:
        grouped[int(row["session_id"])].append(dict(row))
    return grouped


def _deserialize_mock_session(
    row: Mapping[str, Any],
    subject_results: Sequence[Mapping[str, Any]],
    legacy_scores: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    item = dict(row)
    item["session_id"] = int(item.pop("id"))
    for key in (
        "strict_timed",
        "first_exposure",
        "complete_paper_set",
        "strict_schedule",
        "authentic_time_slots",
        "consulted_materials",
        "received_assistance",
        "paused_timer",
        "reviewed_answers_early",
        "has_score_interval",
        "is_execution_valid",
        "is_assessment_eligible",
    ):
        if item.get(key) is not None:
            item[key] = bool(item[key])
    item["subject_results"] = tuple(subject_results)
    item["legacy_scores"] = tuple(legacy_scores)
    return item


def _legacy_total_projection(session: Mapping[str, Any]) -> Mapping[str, Any]:
    results = {
        str(result["subject_code"]): result
        for result in session["subject_results"]
    }
    return {
        "session_id": session["session_id"],
        "taken_on": session["taken_on"],
        "completed_on": session["completed_on"],
        "paper_name": session["paper_name"],
        "attempt_number": session["attempt_number"],
        "politics_score": results["101"]["score_lower"],
        "english_score": results["204"]["score_lower"],
        "math_score": results["302"]["score_lower"],
        "computer_science_score": results["408"]["score_lower"],
        "total_score": session["total_lower"],
    }


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id, event_type, entity_type, entity_id, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            trace_id,
            event_type,
            entity_type,
            entity_id,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            _utc_now(),
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
