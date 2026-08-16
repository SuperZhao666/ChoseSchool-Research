from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.enums import EvidenceGrade, PolicyEventStatus, PolicyEventType
from chose_school.domain.errors import (
    EntityNotFoundError,
    StateConflictError,
    ValidationError,
)
from chose_school.domain.models import (
    PolicyEventAddResult,
    PolicyEventFilter,
    PolicyEventInput,
)
from chose_school.infrastructure.database import Database


class SqlitePolicyEventRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def add_policy_event(
        self,
        event: PolicyEventInput,
        trace_id: str,
    ) -> PolicyEventAddResult:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                school_id = _find_school_id(connection, event.school)
                project_id = _resolve_project_id(connection, event, school_id)
                source_identity_key = _source_identity_key(event)
                source = _find_source(connection, source_identity_key)
                if source is not None:
                    _assert_same_source_metadata(source, event)
                event_status = PolicyEventStatus.PENDING_DIRECTORY
                event_fingerprint = _event_fingerprint(
                    event,
                    school_id,
                    project_id,
                    event_status,
                    source_identity_key,
                )
                existing = _find_event_by_fingerprint(connection, event_fingerprint)
                if existing is not None:
                    connection.commit()
                    return _result_from_row(existing, created=False)

                _validate_supersession(
                    connection,
                    school_id,
                    project_id,
                    event,
                )
                if source is not None:
                    source_id = int(source["id"])
                else:
                    source_id = _insert_source(
                        connection,
                        event,
                        source_identity_key,
                    )

                _reject_same_source_interpretation_conflict(
                    connection,
                    school_id,
                    project_id,
                    event,
                    source_id,
                    event_fingerprint,
                )
                now = _utc_now()
                cursor = connection.execute(
                    """
                    INSERT INTO policy_events(
                        school_id, project_id, effective_year, event_type,
                        event_status, title, description, source_id,
                        announced_on, created_at, updated_at, trace_id,
                        event_fingerprint, scope_text, source_content_sha256,
                        supersedes_event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        school_id,
                        project_id,
                        event.effective_year,
                        event.event_type.value,
                        event_status.value,
                        event.title,
                        event.description,
                        source_id,
                        event.announced_on.isoformat(),
                        now,
                        now,
                        trace_id,
                        event_fingerprint,
                        event.scope_text,
                        event.source_content_sha256,
                        event.supersedes_event_id,
                    ),
                )
                event_id = int(cursor.lastrowid)
                _insert_source_snapshot(
                    connection,
                    event_id,
                    source_id,
                    source_identity_key,
                    event,
                    trace_id,
                    now,
                )
                _insert_audit_event(
                    connection,
                    event_id,
                    trace_id,
                    school_id,
                    project_id,
                    source_id,
                    event,
                    event_status,
                    event_fingerprint,
                )
                connection.commit()
                return PolicyEventAddResult(
                    event_id=event_id,
                    created=True,
                    school_id=school_id,
                    project_id=project_id,
                    effective_year=event.effective_year,
                    event_type=event.event_type,
                    event_status=event_status,
                )
            except Exception:
                connection.rollback()
                raise

    def list_policy_events(
        self,
        event_filter: PolicyEventFilter,
    ) -> Sequence[Mapping[str, Any]]:
        clauses = ["1 = 1"]
        parameters: list[Any] = []
        if event_filter.effective_year is not None:
            clauses.append("event.effective_year = ?")
            parameters.append(event_filter.effective_year)
        if event_filter.school_keyword:
            clauses.append("event.school LIKE ?")
            parameters.append(f"%{event_filter.school_keyword}%")
        if event_filter.event_type is not None:
            clauses.append("event.event_type = ?")
            parameters.append(event_filter.event_type.value)
        if event_filter.event_status is not None:
            clauses.append("event.event_status = ?")
            parameters.append(event_filter.event_status.value)
        if event_filter.current_only:
            clauses.append("event.is_superseded = 0")
        with self._database.connect() as connection:
            if event_filter.observation_id is not None:
                project_id = _find_project_id_by_observation(
                    connection,
                    event_filter.observation_id,
                )
                clauses.append("event.project_id = ?")
                parameters.append(project_id)
            parameters.append(event_filter.limit)
            query = f"""
                SELECT
                    event.event_id,
                    event.school_id,
                    event.school,
                    event.project_id,
                    event.college,
                    event.program_code,
                    event.program_name,
                    event.direction,
                    event.effective_year,
                    event.event_type,
                    event.event_status,
                    event.scope_text,
                    event.title,
                    event.description,
                    event.announced_on,
                    event.source_id,
                    event.source_title,
                    event.source_institution,
                    event.source_url,
                    event.source_document_type,
                    event.source_content_sha256,
                    event.applicable_year,
                    event.published_date,
                    event.retrieved_date,
                    event.supersedes_event_id,
                    event.is_superseded,
                    event.trace_id,
                    event.created_at,
                    event.establishes_official_catalog,
                    event.can_confirm_strict_22408
                FROM v_policy_event_history event
                WHERE {' AND '.join(clauses)}
                ORDER BY event.effective_year DESC, event.event_id ASC
                LIMIT ?
            """
            rows = connection.execute(query, parameters).fetchall()
        return tuple(dict(row) for row in rows)


def _find_school_id(connection: sqlite3.Connection, school: str) -> int:
    canonical_name = _canonical_text(school)
    row = connection.execute(
        "SELECT id FROM schools WHERE canonical_name = ?",
        (canonical_name,),
    ).fetchone()
    if row is None:
        raise EntityNotFoundError(
            "SCHOOL_NOT_FOUND",
            f"政策目标学校尚未进入数据库：{school}",
            {"school": school},
        )
    return int(row["id"])


def _resolve_project_id(
    connection: sqlite3.Connection,
    event: PolicyEventInput,
    school_id: int,
) -> int | None:
    if event.observation_id is None:
        return None
    row = connection.execute(
        """
        SELECT observation.project_id, project.school_id
        FROM project_year_observations observation
        JOIN projects project ON project.id = observation.project_id
        WHERE observation.id = ?
        """,
        (event.observation_id,),
    ).fetchone()
    if row is None:
        raise EntityNotFoundError(
            "OBSERVATION_NOT_FOUND",
            f"政策目标观测不存在：{event.observation_id}",
        )
    if int(row["school_id"]) != school_id:
        raise ValidationError(
            "POLICY_PROJECT_SCHOOL_MISMATCH",
            "政策目标观测不属于指定学校",
            {"observation_id": event.observation_id, "school_id": school_id},
        )
    return int(row["project_id"])


def _find_project_id_by_observation(
    connection: sqlite3.Connection,
    observation_id: int,
) -> int:
    row = connection.execute(
        "SELECT project_id FROM project_year_observations WHERE id = ?",
        (observation_id,),
    ).fetchone()
    if row is None:
        raise EntityNotFoundError(
            "OBSERVATION_NOT_FOUND",
            f"政策目标观测不存在：{observation_id}",
            {"observation_id": observation_id},
        )
    return int(row["project_id"])


def _find_source(
    connection: sqlite3.Connection,
    identity_key: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, title, institution, url, document_type,
               content_sha256, applicable_year, published_date
        FROM evidence_sources
        WHERE identity_key = ?
        """,
        (identity_key,),
    ).fetchone()


def _insert_source(
    connection: sqlite3.Connection,
    event: PolicyEventInput,
    identity_key: str,
) -> int:
    now = _utc_now()
    cursor = connection.execute(
        """
        INSERT INTO evidence_sources(
            identity_key, title, institution, url, evidence_grade,
            published_date, retrieved_date, source_note, created_at,
            updated_at, document_type, content_sha256, applicable_year
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity_key,
            event.source_title,
            event.source_institution,
            event.source_url,
            EvidenceGrade.OFFICIAL.value,
            event.published_date.isoformat() if event.published_date else None,
            event.retrieved_date.isoformat(),
            event.note,
            now,
            now,
            event.source_document_type.value,
            event.source_content_sha256,
            event.applicable_year,
        ),
    )
    return int(cursor.lastrowid)


def _assert_same_source_metadata(source: sqlite3.Row, event: PolicyEventInput) -> None:
    existing = (
        source["title"],
        source["institution"],
        source["url"],
        source["document_type"],
        source["content_sha256"],
        source["applicable_year"],
        source["published_date"],
    )
    requested = (
        event.source_title,
        event.source_institution,
        event.source_url,
        event.source_document_type.value,
        event.source_content_sha256,
        event.applicable_year,
        event.published_date.isoformat() if event.published_date else None,
    )
    if existing != requested:
        raise StateConflictError(
            "SOURCE_IDENTITY_METADATA_CONFLICT",
            "相同来源内容身份已经具有不同元数据",
            {"source_id": source["id"]},
        )


def _find_event_by_fingerprint(
    connection: sqlite3.Connection,
    event_fingerprint: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id AS event_id, school_id, project_id, effective_year,
               event_type, event_status
        FROM policy_events
        WHERE event_fingerprint = ?
        """,
        (event_fingerprint,),
    ).fetchone()


def _result_from_row(row: sqlite3.Row, created: bool) -> PolicyEventAddResult:
    return PolicyEventAddResult(
        event_id=int(row["event_id"]),
        created=created,
        school_id=int(row["school_id"]),
        project_id=int(row["project_id"]) if row["project_id"] is not None else None,
        effective_year=int(row["effective_year"]),
        event_type=PolicyEventType(str(row["event_type"])),
        event_status=PolicyEventStatus(str(row["event_status"])),
    )


def _reject_same_source_interpretation_conflict(
    connection: sqlite3.Connection,
    school_id: int,
    project_id: int | None,
    event: PolicyEventInput,
    source_id: int,
    event_fingerprint: str,
) -> None:
    row = connection.execute(
        """
        SELECT id, event_fingerprint
        FROM policy_events
        WHERE school_id = ?
          AND project_id IS ?
          AND effective_year = ?
          AND event_type = ?
          AND source_id = ?
        LIMIT 1
        """,
        (
            school_id,
            project_id,
            event.effective_year,
            event.event_type.value,
            source_id,
        ),
    ).fetchone()
    if (
        row is not None
        and row["event_fingerprint"] != event_fingerprint
        and event.supersedes_event_id is None
    ):
        raise StateConflictError(
            "POLICY_EVENT_SOURCE_CONFLICT",
            "同一官方来源和政策作用域已经存在不同解析",
            {"event_id": row["id"]},
        )


def _validate_supersession(
    connection: sqlite3.Connection,
    school_id: int,
    project_id: int | None,
    event: PolicyEventInput,
) -> None:
    if event.supersedes_event_id is None:
        return
    row = connection.execute(
        """
        SELECT previous.school_id, previous.project_id, previous.effective_year,
               previous.event_type, successor.id AS successor_id
        FROM policy_events previous
        LEFT JOIN policy_events successor
          ON successor.supersedes_event_id = previous.id
        WHERE previous.id = ?
        """,
        (event.supersedes_event_id,),
    ).fetchone()
    if row is None:
        raise EntityNotFoundError(
            "SUPERSEDED_POLICY_EVENT_NOT_FOUND",
            f"被替代的政策事件不存在：{event.supersedes_event_id}",
        )
    identity = (
        int(row["school_id"]),
        int(row["project_id"]) if row["project_id"] is not None else None,
        int(row["effective_year"]),
        str(row["event_type"]),
    )
    expected = (
        school_id,
        project_id,
        event.effective_year,
        event.event_type.value,
    )
    if identity != expected:
        raise ValidationError(
            "POLICY_EVENT_SUPERSESSION_MISMATCH",
            "新旧政策事件的学校、项目、年度和类型必须一致",
        )
    if row["successor_id"] is not None:
        raise StateConflictError(
            "POLICY_EVENT_ALREADY_SUPERSEDED",
            "被替代的政策事件已经存在后续修订",
            {
                "supersedes_event_id": event.supersedes_event_id,
                "successor_event_id": int(row["successor_id"]),
            },
        )


def _insert_source_snapshot(
    connection: sqlite3.Connection,
    event_id: int,
    source_id: int,
    source_identity_key: str,
    event: PolicyEventInput,
    trace_id: str,
    captured_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO policy_event_source_snapshots(
            policy_event_id, source_id, source_identity_key, source_title,
            source_institution, source_url, evidence_grade,
            source_document_type, source_content_sha256, applicable_year,
            published_date, retrieved_date, captured_at, trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            source_id,
            source_identity_key,
            event.source_title,
            event.source_institution,
            event.source_url,
            EvidenceGrade.OFFICIAL.value,
            event.source_document_type.value,
            event.source_content_sha256,
            event.applicable_year,
            event.published_date.isoformat() if event.published_date else None,
            event.retrieved_date.isoformat(),
            captured_at,
            trace_id,
        ),
    )


def _insert_audit_event(
    connection: sqlite3.Connection,
    event_id: int,
    trace_id: str,
    school_id: int,
    project_id: int | None,
    source_id: int,
    event: PolicyEventInput,
    event_status: PolicyEventStatus,
    event_fingerprint: str,
) -> None:
    payload = {
        "school_id": school_id,
        "project_id": project_id,
        "effective_year": event.effective_year,
        "event_type": event.event_type.value,
        "event_status": event_status.value,
        "scope_text": event.scope_text,
        "source_id": source_id,
        "source_content_sha256": event.source_content_sha256,
        "event_fingerprint": event_fingerprint,
        "supersedes_event_id": event.supersedes_event_id,
        "establishes_official_catalog": False,
        "can_confirm_strict_22408": False,
    }
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id, event_type, entity_type, entity_id,
            payload_json, created_at
        ) VALUES (?, 'policy_event_added', 'policy_event', ?, ?, ?)
        """,
        (
            trace_id,
            str(event_id),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            _utc_now(),
        ),
    )


def _source_identity_key(event: PolicyEventInput) -> str:
    return _sha256_json(
        (
            event.source_content_sha256,
            event.source_document_type.value,
            event.applicable_year,
        )
    )


def _event_fingerprint(
    event: PolicyEventInput,
    school_id: int,
    project_id: int | None,
    event_status: PolicyEventStatus,
    source_identity_key: str,
) -> str:
    return _sha256_json(
        (
            school_id,
            project_id,
            event.effective_year,
            event.event_type.value,
            event_status.value,
            event.scope_text,
            event.title,
            event.description,
            source_identity_key,
            event.announced_on.isoformat(),
            event.supersedes_event_id,
        )
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _canonical_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
