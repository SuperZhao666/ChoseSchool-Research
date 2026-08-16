from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.errors import EntityNotFoundError, StateConflictError
from chose_school.domain.models import MachineTestInput
from chose_school.infrastructure.database import Database


class SqliteMachineTestRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_id(self, profile_key: str) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        return int(row["id"]) if row else None

    def add_machine_test(
        self,
        profile_id: int,
        machine_test: MachineTestInput,
        trace_id: str,
    ) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                profile = connection.execute(
                    "SELECT id FROM applicant_profiles WHERE id = ?",
                    (profile_id,),
                ).fetchone()
                if profile is None:
                    raise EntityNotFoundError(
                        "PROFILE_NOT_FOUND",
                        f"applicant profile does not exist: {profile_id}",
                    )
                existing = connection.execute(
                    """
                    SELECT id
                    FROM machine_test_sessions
                    WHERE profile_id = ?
                      AND taken_on = ?
                      AND problem_source = ?
                      AND attempt_number = ?
                    """,
                    (
                        profile_id,
                        machine_test.taken_on.isoformat(),
                        machine_test.problem_source,
                        machine_test.attempt_number,
                    ),
                ).fetchone()
                if existing is not None:
                    raise StateConflictError(
                        "MACHINE_TEST_ALREADY_EXISTS",
                        "同一日期、题组来源和尝试次数的机试记录已存在",
                        {"session_id": int(existing["id"])},
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO machine_test_sessions(
                        profile_id, taken_on, duration_minutes, language,
                        environment, problem_source, difficulty_label,
                        problem_count, independently_solved_count,
                        first_solve_minutes, first_exposure,
                        consulted_materials, strict_timed, received_assistance,
                        paused_timer, scoring_method, raw_score, maximum_score,
                        debugging_minutes, attempt_number,
                        invalid_reason, primary_blocker, notes, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile_id,
                        machine_test.taken_on.isoformat(),
                        machine_test.duration_minutes,
                        machine_test.language,
                        machine_test.environment,
                        machine_test.problem_source,
                        machine_test.difficulty.value,
                        machine_test.problem_count,
                        machine_test.independently_solved_count,
                        machine_test.first_solve_minutes,
                        int(machine_test.first_exposure),
                        int(machine_test.consulted_materials),
                        int(machine_test.strict_timed),
                        int(machine_test.received_assistance),
                        int(machine_test.paused_timer),
                        machine_test.scoring_method.value,
                        machine_test.raw_score,
                        machine_test.maximum_score,
                        machine_test.debugging_minutes,
                        machine_test.attempt_number,
                        machine_test.invalid_reason,
                        machine_test.primary_blocker,
                        machine_test.notes,
                        trace_id,
                        _utc_now(),
                    ),
                )
                session_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    session_id,
                    profile_id,
                    machine_test,
                )
                connection.commit()
                return session_id
            except Exception:
                connection.rollback()
                raise

    def list_machine_tests(
        self,
        profile_id: int,
        duration_minutes: int | None,
        language: str | None,
        problem_count: int | None,
        valid_only: bool,
    ) -> Sequence[Mapping[str, Any]]:
        clauses = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if duration_minutes is not None:
            clauses.append("duration_minutes = ?")
            parameters.append(duration_minutes)
        if language is not None:
            clauses.append("language = ?")
            parameters.append(language)
        if problem_count is not None:
            clauses.append("problem_count = ?")
            parameters.append(problem_count)
        if valid_only:
            clauses.append("is_valid = 1")
        query = f"""
            SELECT *
            FROM v_machine_test_sessions
            WHERE {' AND '.join(clauses)}
            ORDER BY taken_on, id
        """
        with self._database.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(_deserialize_row(row) for row in rows)


def _deserialize_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["session_id"] = item.pop("id")
    for key in (
        "first_exposure",
        "consulted_materials",
        "received_assistance",
        "paused_timer",
        "strict_timed",
        "is_valid",
    ):
        item[key] = bool(item[key])
    return item


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    session_id: int,
    profile_id: int,
    machine_test: MachineTestInput,
) -> None:
    payload = {
        "profile_id": profile_id,
        "taken_on": machine_test.taken_on.isoformat(),
        "duration_minutes": machine_test.duration_minutes,
        "problem_source": machine_test.problem_source,
        "difficulty": machine_test.difficulty.value,
        "language": machine_test.language,
        "problem_count": machine_test.problem_count,
        "scoring_method": machine_test.scoring_method.value,
        "independently_solved_count": machine_test.independently_solved_count,
        "first_exposure": machine_test.first_exposure,
        "consulted_materials": machine_test.consulted_materials,
        "received_assistance": machine_test.received_assistance,
        "paused_timer": machine_test.paused_timer,
        "strict_timed": machine_test.strict_timed,
        "is_valid": (
            machine_test.first_exposure
            and not machine_test.consulted_materials
            and not machine_test.received_assistance
            and not machine_test.paused_timer
            and machine_test.strict_timed
            and not machine_test.invalid_reason
        ),
    }
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id, event_type, entity_type, entity_id, payload_json, created_at
        ) VALUES (?, 'machine_test_added', 'machine_test_session', ?, ?, ?)
        """,
        (
            trace_id,
            str(session_id),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            _utc_now(),
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
