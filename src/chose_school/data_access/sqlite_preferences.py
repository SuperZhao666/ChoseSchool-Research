from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.errors import EntityNotFoundError
from chose_school.domain.models import PreferenceEventInput
from chose_school.infrastructure.database import Database


class SqlitePreferenceRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_id(self, profile_key: str) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        return int(row["id"]) if row else None

    def add_preference_event(
        self,
        profile_id: int,
        preference: PreferenceEventInput,
        canonical_value_json: str,
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
                cursor = connection.execute(
                    """
                    INSERT INTO applicant_preference_events(
                        profile_id, dimension, subject_key, value_json,
                        acceptance_level, note, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile_id,
                        preference.dimension.value,
                        preference.subject_key,
                        canonical_value_json,
                        preference.acceptance_level.value,
                        preference.note,
                        trace_id,
                        _utc_now(),
                    ),
                )
                event_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    event_id,
                    profile_id,
                    preference,
                    canonical_value_json,
                )
                connection.commit()
                return event_id
            except Exception:
                connection.rollback()
                raise

    def list_preferences(
        self,
        profile_id: int,
        dimension: str | None,
        subject_key: str | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "applicant_preference_events"
            if include_history
            else "v_current_applicant_preferences"
        )
        clauses = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if dimension:
            clauses.append("dimension = ?")
            parameters.append(dimension)
        if subject_key:
            clauses.append("subject_key = ?")
            parameters.append(subject_key)
        ordering = "dimension, subject_key, id" if include_history else "dimension, subject_key"
        query = f"""
            SELECT
                id AS event_id,
                profile_id,
                dimension,
                subject_key,
                value_json,
                acceptance_level,
                note,
                trace_id,
                created_at
            FROM {source}
            WHERE {' AND '.join(clauses)}
            ORDER BY {ordering}
        """
        with self._database.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(_deserialize_row(row) for row in rows)


def _deserialize_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["value"] = json.loads(str(item.pop("value_json")))
    return item


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_id: int,
    profile_id: int,
    preference: PreferenceEventInput,
    canonical_value_json: str,
) -> None:
    payload = {
        "profile_id": profile_id,
        "dimension": preference.dimension.value,
        "subject_key": preference.subject_key,
        "acceptance_level": preference.acceptance_level.value,
        "value": json.loads(canonical_value_json),
    }
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id, event_type, entity_type, entity_id, payload_json, created_at
        ) VALUES (?, 'preference_event_added', 'applicant_preference_event', ?, ?, ?)
        """,
        (
            trace_id,
            str(event_id),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            _utc_now(),
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
