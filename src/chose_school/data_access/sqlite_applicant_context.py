from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.models import ApplicantContextEventInput
from chose_school.infrastructure.database import Database


class SqliteApplicantContextRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_id(self, profile_key: str) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        return int(row["id"]) if row else None

    def add_context_event(
        self,
        profile_id: int,
        event: ApplicantContextEventInput,
        canonical_value_json: str,
        trace_id: str,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO applicant_context_events(
                    profile_id, dimension, subject_key, value_json,
                    note, trace_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    event.dimension.value,
                    event.subject_key,
                    canonical_value_json,
                    event.note,
                    trace_id,
                    created_at,
                ),
            )
            event_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO audit_events(
                    trace_id, event_type, entity_type, entity_id,
                    payload_json, created_at
                ) VALUES (?, 'applicant_context_event_added',
                          'applicant_context_event', ?, ?, ?)
                """,
                (
                    trace_id,
                    str(event_id),
                    json.dumps(
                        {
                            "profile_id": profile_id,
                            "dimension": event.dimension.value,
                            "subject_key": event.subject_key,
                            "value": json.loads(canonical_value_json),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    created_at,
                ),
            )
            connection.commit()
        return event_id

    def list_context_events(
        self,
        profile_id: int,
        dimension: str | None,
        subject_key: str | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "applicant_context_events"
            if include_history
            else "v_current_applicant_context"
        )
        clauses = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if dimension is not None:
            clauses.append("dimension = ?")
            parameters.append(dimension)
        if subject_key is not None:
            clauses.append("subject_key = ?")
            parameters.append(subject_key)
        order = "id" if include_history else "dimension, subject_key"
        with self._database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id AS event_id, profile_id, dimension, subject_key,
                       value_json, note, trace_id, created_at
                FROM {source}
                WHERE {' AND '.join(clauses)}
                ORDER BY {order}
                """,
                parameters,
            ).fetchall()
        return tuple(_deserialize(row) for row in rows)


def _deserialize(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["value"] = json.loads(str(item.pop("value_json")))
    return item
