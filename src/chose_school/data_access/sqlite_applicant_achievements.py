from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.errors import EntityNotFoundError, StateConflictError
from chose_school.domain.models import (
    ApplicantAchievementAddResult,
    ApplicantAchievementInput,
    ApplicantEvidenceInput,
)
from chose_school.infrastructure.database import Database


class SqliteApplicantAchievementRepository:
    """Append-only persistence for applicant achievements and their evidence."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_id(self, profile_key: str) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        return int(row["id"]) if row else None

    def add_achievement(
        self,
        profile_id: int,
        achievement: ApplicantAchievementInput,
        canonical_details_json: str,
        event_fingerprint: str,
        fingerprint_version: str,
        trace_id: str,
    ) -> ApplicantAchievementAddResult:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                _require_profile(connection, profile_id)

                existing_event = _find_event_by_fingerprint(
                    connection,
                    profile_id,
                    event_fingerprint,
                )
                if existing_event is not None:
                    result = _verify_idempotent_replay(
                        connection,
                        existing_event,
                        profile_id,
                        achievement,
                        canonical_details_json,
                        event_fingerprint,
                        fingerprint_version,
                    )
                    connection.commit()
                    return result

                semantic_equivalents = _find_semantically_equivalent_events(
                    connection,
                    profile_id,
                    achievement,
                    canonical_details_json,
                )
                for semantic_equivalent in semantic_equivalents:
                    result = _verify_semantic_replay(
                        connection,
                        semantic_equivalent,
                        profile_id,
                        achievement,
                        canonical_details_json,
                    )
                    if result is not None:
                        connection.commit()
                        return result

                created_at = _utc_now()
                evidence_document_ids: list[int] = []
                evidence_review_event_ids: list[int] = []
                for evidence in achievement.evidence:
                    document_id, review_event_id = _get_or_create_evidence(
                        connection,
                        profile_id,
                        evidence,
                        trace_id,
                        created_at,
                    )
                    evidence_document_ids.append(document_id)
                    evidence_review_event_ids.append(review_event_id)

                event_id = _insert_achievement_event(
                    connection,
                    profile_id,
                    achievement,
                    canonical_details_json,
                    event_fingerprint,
                    fingerprint_version,
                    trace_id,
                    created_at,
                )
                _insert_audit_event(
                    connection,
                    trace_id,
                    "applicant_achievement_event_added",
                    "applicant_achievement_event",
                    event_id,
                    {
                        "profile_id": profile_id,
                        "achievement_key": achievement.achievement_key,
                        "category": achievement.category.value,
                        "achievement_year": achievement.achievement_year,
                        "verification_status": achievement.verification_status.value,
                        "event_fingerprint": event_fingerprint,
                        "fingerprint_version": fingerprint_version,
                        "evidence_document_ids": evidence_document_ids,
                        "evidence_review_event_ids": evidence_review_event_ids,
                    },
                    created_at,
                )

                for evidence, evidence_document_id, evidence_review_event_id in zip(
                    achievement.evidence,
                    evidence_document_ids,
                    evidence_review_event_ids,
                    strict=True,
                ):
                    link_id = _insert_evidence_link(
                        connection,
                        event_id,
                        evidence_document_id,
                        evidence,
                        trace_id,
                        created_at,
                    )
                    review_link_id = _insert_evidence_review_link(
                        connection,
                        link_id,
                        evidence_review_event_id,
                        trace_id,
                        created_at,
                    )
                    _insert_audit_event(
                        connection,
                        trace_id,
                        "applicant_achievement_evidence_link_added",
                        "applicant_achievement_evidence_link",
                        link_id,
                        {
                            "achievement_event_id": event_id,
                            "evidence_document_id": evidence_document_id,
                            "relationship": evidence.relationship.value,
                        },
                        created_at,
                    )
                    _insert_audit_event(
                        connection,
                        trace_id,
                        "applicant_achievement_evidence_review_link_added",
                        "applicant_achievement_evidence_review_link",
                        review_link_id,
                        {
                            "achievement_evidence_link_id": link_id,
                            "evidence_review_event_id": evidence_review_event_id,
                        },
                        created_at,
                    )

                connection.commit()
                return ApplicantAchievementAddResult(
                    event_id=event_id,
                    created=True,
                    evidence_document_ids=tuple(evidence_document_ids),
                )
            except Exception:
                connection.rollback()
                raise

    def list_achievements(
        self,
        profile_id: int,
        category: str | None,
        achievement_year: int | None,
        achievement_key: str | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "applicant_achievement_events"
            if include_history
            else "v_current_applicant_achievements"
        )
        clauses = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if category is not None:
            clauses.append("category = ?")
            parameters.append(_value(category))
        if achievement_year is not None:
            clauses.append("achievement_year = ?")
            parameters.append(achievement_year)
        if achievement_key is not None:
            clauses.append("achievement_key = ?")
            parameters.append(achievement_key)

        ordering = (
            "achievement_year DESC, achievement_key, id"
            if include_history
            else "achievement_year DESC, achievement_key"
        )
        with self._database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id AS event_id,
                    profile_id,
                    achievement_key,
                    category,
                    title,
                    issuer,
                    achievement_year,
                    period_label,
                    awarded_on,
                    scope_level,
                    stage,
                    result,
                    participation_type,
                    team_name,
                    details_json,
                    verification_status,
                    event_fingerprint,
                    fingerprint_version,
                    note,
                    trace_id,
                    created_at
                FROM {source}
                WHERE {' AND '.join(clauses)}
                ORDER BY {ordering}
                """,
                parameters,
            ).fetchall()
            return tuple(_deserialize_event(connection, row) for row in rows)


def _require_profile(connection: sqlite3.Connection, profile_id: int) -> None:
    row = connection.execute(
        "SELECT 1 FROM applicant_profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    if row is None:
        raise EntityNotFoundError(
            "PROFILE_NOT_FOUND",
            "申请人档案不存在",
            {"profile_id": profile_id},
        )


def _find_event_by_fingerprint(
    connection: sqlite3.Connection,
    profile_id: int,
    event_fingerprint: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM applicant_achievement_events
        WHERE profile_id = ? AND event_fingerprint = ?
        """,
        (profile_id, event_fingerprint),
    ).fetchone()


def _find_semantically_equivalent_events(
    connection: sqlite3.Connection,
    profile_id: int,
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
) -> tuple[sqlite3.Row, ...]:
    rows = connection.execute(
        """
        SELECT *
        FROM applicant_achievement_events event
        WHERE event.profile_id = ?
          AND event.achievement_key = ?
        ORDER BY event.id DESC
        """,
        (profile_id, achievement.achievement_key),
    ).fetchall()
    requested_contract = _event_semantic_contract_from_input(
        profile_id,
        achievement,
        canonical_details_json,
    )
    return tuple(
        row
        for row in rows
        if _event_semantic_contract_from_row(row) == requested_contract
    )


def _verify_idempotent_replay(
    connection: sqlite3.Connection,
    existing_event: sqlite3.Row,
    profile_id: int,
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
    event_fingerprint: str,
    fingerprint_version: str,
) -> ApplicantAchievementAddResult:
    existing_contract = _event_contract_from_row(existing_event)
    requested_contract = _event_contract_from_input(
        profile_id,
        achievement,
        canonical_details_json,
        event_fingerprint,
        fingerprint_version,
    )
    if existing_contract != requested_contract:
        raise StateConflictError(
            "ACHIEVEMENT_FINGERPRINT_CONFLICT",
            "相同成果指纹已经对应不同的成果元数据",
            {"event_id": int(existing_event["id"])},
        )

    return _verify_replay_evidence(
        connection,
        existing_event,
        profile_id,
        achievement,
    )


def _verify_semantic_replay(
    connection: sqlite3.Connection,
    existing_event: sqlite3.Row,
    profile_id: int,
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
) -> ApplicantAchievementAddResult | None:
    if _event_semantic_contract_from_row(existing_event) != _event_semantic_contract_from_input(
        profile_id,
        achievement,
        canonical_details_json,
    ):
        raise StateConflictError(
            "ACHIEVEMENT_SEMANTIC_REPLAY_CONFLICT",
            "当前成果版本与本次请求的成果元数据不一致",
            {"event_id": int(existing_event["id"])},
        )
    try:
        return _verify_replay_evidence(
            connection,
            existing_event,
            profile_id,
            achievement,
        )
    except StateConflictError as error:
        # Matching achievement semantics with a different document, relationship,
        # or review is a new evidence-backed version, not an idempotent replay.
        # Document identity conflicts are still rejected later by
        # _get_or_create_evidence so a hash can never silently change metadata.
        if error.error_code in {
            "ACHIEVEMENT_REPLAY_EVIDENCE_CONFLICT",
            "ACHIEVEMENT_REPLAY_EVIDENCE_REVIEW_CONFLICT",
        }:
            return None
        raise


def _verify_replay_evidence(
    connection: sqlite3.Connection,
    existing_event: sqlite3.Row,
    profile_id: int,
    achievement: ApplicantAchievementInput,
) -> ApplicantAchievementAddResult:
    requested_links: list[tuple[int, str, int]] = []
    requested_document_ids: list[int] = []
    for evidence in achievement.evidence:
        document = _find_evidence_document(
            connection,
            profile_id,
            evidence.source_content_sha256,
        )
        if document is None:
            raise StateConflictError(
                "ACHIEVEMENT_REPLAY_EVIDENCE_CONFLICT",
                "已有成果事件缺少本次请求声明的证据文档",
                {"event_id": int(existing_event["id"])},
            )
        _assert_same_evidence_document_metadata(document, evidence)
        document_id = int(document["id"])
        review = _find_evidence_review(
            connection,
            document_id,
            _review_fingerprint(evidence),
        )
        if review is None and str(existing_event["fingerprint_version"]) == "v1":
            review = _find_semantically_equal_evidence_review(
                connection,
                document_id,
                evidence,
            )
        if review is None:
            raise StateConflictError(
                "ACHIEVEMENT_REPLAY_EVIDENCE_REVIEW_CONFLICT",
                "已有成果事件缺少本次请求声明的证据复核版本",
                {"event_id": int(existing_event["id"]), "evidence_document_id": document_id},
            )
        requested_document_ids.append(document_id)
        requested_links.append(
            (document_id, evidence.relationship.value, int(review["id"]))
        )

    existing_links = sorted(
        (
            int(row["evidence_document_id"]),
            str(row["relationship"]),
            int(row["evidence_review_event_id"]),
        )
        for row in connection.execute(
            """
            SELECT
                link.evidence_document_id,
                link.relationship,
                review_link.evidence_review_event_id
            FROM applicant_achievement_evidence_links link
            JOIN applicant_achievement_evidence_review_links review_link
              ON review_link.achievement_evidence_link_id = link.id
            WHERE link.achievement_event_id = ?
            """,
            (int(existing_event["id"]),),
        ).fetchall()
    )
    if existing_links != sorted(requested_links):
        raise StateConflictError(
            "ACHIEVEMENT_REPLAY_EVIDENCE_CONFLICT",
            "已有成果事件的证据链接与本次请求不一致",
            {"event_id": int(existing_event["id"])},
        )

    return ApplicantAchievementAddResult(
        event_id=int(existing_event["id"]),
        created=False,
        evidence_document_ids=tuple(requested_document_ids),
    )


def _get_or_create_evidence(
    connection: sqlite3.Connection,
    profile_id: int,
    evidence: ApplicantEvidenceInput,
    trace_id: str,
    created_at: str,
) -> tuple[int, int]:
    existing = _find_evidence_document(
        connection,
        profile_id,
        evidence.source_content_sha256,
    )
    if existing is not None:
        _assert_same_evidence_document_metadata(existing, evidence)
        document_id = int(existing["id"])
    else:
        document_id = _insert_evidence_document(
            connection,
            profile_id,
            evidence,
            trace_id,
            created_at,
        )

    review_fingerprint = _review_fingerprint(evidence)
    review = _find_evidence_review(connection, document_id, review_fingerprint)
    if review is None:
        review = _find_semantically_equal_evidence_review(
            connection,
            document_id,
            evidence,
        )
    if review is not None:
        return document_id, int(review["id"])

    review_event_id = _insert_evidence_review(
        connection,
        document_id,
        evidence,
        review_fingerprint,
        trace_id,
        created_at,
    )
    _insert_audit_event(
        connection,
        trace_id,
        "applicant_evidence_review_added",
        "applicant_evidence_review_event",
        review_event_id,
        {
            "evidence_document_id": document_id,
            "review_fingerprint": review_fingerprint,
            "evidence_grade": evidence.evidence_grade.value,
            "evidence_status": evidence.evidence_status.value,
        },
        created_at,
    )
    return document_id, review_event_id


def _insert_evidence_document(
    connection: sqlite3.Connection,
    profile_id: int,
    evidence: ApplicantEvidenceInput,
    trace_id: str,
    created_at: str,
) -> int:

    cursor = connection.execute(
        """
        INSERT INTO applicant_evidence_documents(
            profile_id,
            source_title,
            source_url,
            source_access_scope,
            source_document_type,
            source_mime_type,
            source_content_sha256,
            source_file_size_bytes,
            source_retrieved_on,
            source_reviewed_on,
            review_method,
            evidence_grade,
            evidence_status,
            claim_text,
            note,
            trace_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            evidence.source_title,
            evidence.source_url,
            evidence.source_access_scope.value,
            evidence.source_document_type.value,
            evidence.source_mime_type,
            evidence.source_content_sha256,
            evidence.source_file_size_bytes,
            evidence.source_retrieved_on.isoformat(),
            evidence.source_reviewed_on.isoformat(),
            evidence.review_method.value,
            evidence.evidence_grade.value,
            evidence.evidence_status.value,
            evidence.claim_text,
            evidence.note,
            trace_id,
            created_at,
        ),
    )
    document_id = int(cursor.lastrowid)
    _insert_audit_event(
        connection,
        trace_id,
        "applicant_evidence_document_added",
        "applicant_evidence_document",
        document_id,
        {
            "profile_id": profile_id,
            "source_document_type": evidence.source_document_type.value,
            "source_access_scope": evidence.source_access_scope.value,
            "evidence_grade": evidence.evidence_grade.value,
            "evidence_status": evidence.evidence_status.value,
            "source_content_sha256": evidence.source_content_sha256,
        },
        created_at,
    )
    return document_id


def _find_evidence_document(
    connection: sqlite3.Connection,
    profile_id: int,
    source_content_sha256: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM applicant_evidence_documents
        WHERE profile_id = ? AND source_content_sha256 = ?
        """,
        (profile_id, source_content_sha256),
    ).fetchone()


def _assert_same_evidence_document_metadata(
    existing: sqlite3.Row,
    evidence: ApplicantEvidenceInput,
) -> None:
    existing_contract = (
        str(existing["source_title"]),
        str(existing["source_url"]),
        str(existing["source_access_scope"]),
        str(existing["source_document_type"]),
        str(existing["source_mime_type"]),
        str(existing["source_content_sha256"]),
        int(existing["source_file_size_bytes"]),
        str(existing["source_retrieved_on"]),
    )
    requested_contract = (
        evidence.source_title,
        evidence.source_url,
        evidence.source_access_scope.value,
        evidence.source_document_type.value,
        evidence.source_mime_type,
        evidence.source_content_sha256,
        evidence.source_file_size_bytes,
        evidence.source_retrieved_on.isoformat(),
    )
    if existing_contract != requested_contract:
        raise StateConflictError(
            "APPLICANT_EVIDENCE_METADATA_CONFLICT",
            "相同证据内容哈希已经具有不同元数据",
            {"evidence_document_id": int(existing["id"])},
        )


def _review_fingerprint(evidence: ApplicantEvidenceInput) -> str:
    payload = json.dumps(
        {
            "source_reviewed_on": evidence.source_reviewed_on.isoformat(),
            "review_method": evidence.review_method.value,
            "evidence_grade": evidence.evidence_grade.value,
            "evidence_status": evidence.evidence_status.value,
            "claim_text": evidence.claim_text,
            "note": evidence.note,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _find_evidence_review(
    connection: sqlite3.Connection,
    evidence_document_id: int,
    review_fingerprint: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM applicant_evidence_review_events
        WHERE evidence_document_id = ? AND review_fingerprint = ?
        """,
        (evidence_document_id, review_fingerprint),
    ).fetchone()


def _find_semantically_equal_evidence_review(
    connection: sqlite3.Connection,
    evidence_document_id: int,
    evidence: ApplicantEvidenceInput,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM applicant_evidence_review_events
        WHERE evidence_document_id = ?
          AND source_reviewed_on = ?
          AND review_method = ?
          AND evidence_grade = ?
          AND evidence_status = ?
          AND claim_text = ?
          AND note IS ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            evidence_document_id,
            evidence.source_reviewed_on.isoformat(),
            evidence.review_method.value,
            evidence.evidence_grade.value,
            evidence.evidence_status.value,
            evidence.claim_text,
            evidence.note,
        ),
    ).fetchone()


def _insert_evidence_review(
    connection: sqlite3.Connection,
    evidence_document_id: int,
    evidence: ApplicantEvidenceInput,
    review_fingerprint: str,
    trace_id: str,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO applicant_evidence_review_events(
            evidence_document_id,
            source_reviewed_on,
            review_method,
            evidence_grade,
            evidence_status,
            claim_text,
            note,
            review_fingerprint,
            trace_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_document_id,
            evidence.source_reviewed_on.isoformat(),
            evidence.review_method.value,
            evidence.evidence_grade.value,
            evidence.evidence_status.value,
            evidence.claim_text,
            evidence.note,
            review_fingerprint,
            trace_id,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _insert_achievement_event(
    connection: sqlite3.Connection,
    profile_id: int,
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
    event_fingerprint: str,
    fingerprint_version: str,
    trace_id: str,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO applicant_achievement_events(
            profile_id,
            achievement_key,
            category,
            title,
            issuer,
            achievement_year,
            period_label,
            awarded_on,
            scope_level,
            stage,
            result,
            participation_type,
            team_name,
            details_json,
            verification_status,
            event_fingerprint,
            fingerprint_version,
            note,
            trace_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            achievement.achievement_key,
            achievement.category.value,
            achievement.title,
            achievement.issuer,
            achievement.achievement_year,
            achievement.period_label,
            achievement.awarded_on.isoformat() if achievement.awarded_on else None,
            achievement.scope_level.value,
            achievement.stage.value,
            achievement.result,
            achievement.participation_type.value,
            achievement.team_name,
            canonical_details_json,
            achievement.verification_status.value,
            event_fingerprint,
            fingerprint_version,
            achievement.note,
            trace_id,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _insert_evidence_link(
    connection: sqlite3.Connection,
    event_id: int,
    evidence_document_id: int,
    evidence: ApplicantEvidenceInput,
    trace_id: str,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO applicant_achievement_evidence_links(
            achievement_event_id,
            evidence_document_id,
            relationship,
            trace_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            event_id,
            evidence_document_id,
            evidence.relationship.value,
            trace_id,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _insert_evidence_review_link(
    connection: sqlite3.Connection,
    achievement_evidence_link_id: int,
    evidence_review_event_id: int,
    trace_id: str,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO applicant_achievement_evidence_review_links(
            achievement_evidence_link_id,
            evidence_review_event_id,
            trace_id,
            created_at
        ) VALUES (?, ?, ?, ?)
        """,
        (
            achievement_evidence_link_id,
            evidence_review_event_id,
            trace_id,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _event_contract_from_row(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        int(row["profile_id"]),
        str(row["achievement_key"]),
        str(row["category"]),
        str(row["title"]),
        str(row["issuer"]),
        int(row["achievement_year"]),
        str(row["period_label"]),
        row["awarded_on"],
        str(row["scope_level"]),
        str(row["stage"]),
        str(row["result"]),
        str(row["participation_type"]),
        row["team_name"],
        str(row["details_json"]),
        str(row["verification_status"]),
        str(row["event_fingerprint"]),
        str(row["fingerprint_version"]),
        row["note"],
    )


def _event_contract_from_input(
    profile_id: int,
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
    event_fingerprint: str,
    fingerprint_version: str,
) -> tuple[Any, ...]:
    return (
        profile_id,
        achievement.achievement_key,
        achievement.category.value,
        achievement.title,
        achievement.issuer,
        achievement.achievement_year,
        achievement.period_label,
        achievement.awarded_on.isoformat() if achievement.awarded_on else None,
        achievement.scope_level.value,
        achievement.stage.value,
        achievement.result,
        achievement.participation_type.value,
        achievement.team_name,
        canonical_details_json,
        achievement.verification_status.value,
        event_fingerprint,
        fingerprint_version,
        achievement.note,
    )


def _event_semantic_contract_from_row(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        int(row["profile_id"]),
        str(row["achievement_key"]),
        str(row["category"]),
        str(row["title"]),
        str(row["issuer"]),
        int(row["achievement_year"]),
        str(row["period_label"]),
        row["awarded_on"],
        str(row["scope_level"]),
        str(row["stage"]),
        str(row["result"]),
        str(row["participation_type"]),
        row["team_name"],
        str(row["details_json"]),
        str(row["verification_status"]),
        row["note"],
    )


def _event_semantic_contract_from_input(
    profile_id: int,
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
) -> tuple[Any, ...]:
    return (
        profile_id,
        achievement.achievement_key,
        achievement.category.value,
        achievement.title,
        achievement.issuer,
        achievement.achievement_year,
        achievement.period_label,
        achievement.awarded_on.isoformat() if achievement.awarded_on else None,
        achievement.scope_level.value,
        achievement.stage.value,
        achievement.result,
        achievement.participation_type.value,
        achievement.team_name,
        canonical_details_json,
        achievement.verification_status.value,
        achievement.note,
    )


def _deserialize_event(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> Mapping[str, Any]:
    item = dict(row)
    item["details"] = json.loads(str(item.pop("details_json")))
    item["evidence"] = tuple(
        _deserialize_evidence(evidence_row)
        for evidence_row in connection.execute(
            """
            SELECT
                link.evidence_document_id,
                link.relationship,
                CASE
                    WHEN document.source_access_scope = 'public_web'
                    THEN document.source_url
                    ELSE NULL
                END AS source_url,
                document.source_access_scope,
                document.source_document_type,
                document.source_mime_type,
                document.source_content_sha256,
                document.source_file_size_bytes,
                document.source_retrieved_on,
                review.source_reviewed_on,
                review.review_method,
                review.evidence_grade,
                review.evidence_status,
                review.id AS evidence_review_event_id
            FROM applicant_achievement_evidence_links link
            JOIN applicant_evidence_documents document
              ON document.id = link.evidence_document_id
            JOIN applicant_achievement_evidence_review_links review_link
              ON review_link.achievement_evidence_link_id = link.id
            JOIN applicant_evidence_review_events review
              ON review.id = review_link.evidence_review_event_id
            WHERE link.achievement_event_id = ?
            ORDER BY link.id
            """,
            (int(row["event_id"]),),
        ).fetchall()
    )
    return item


def _deserialize_evidence(row: sqlite3.Row) -> Mapping[str, Any]:
    # source_title, claim_text and notes are intentionally not returned: imported
    # filenames can contain certificate numbers, and these values are not needed
    # for achievement-list decisions. Private/local URLs are also withheld; the
    # access scope and content hash preserve a non-secret provenance reference.
    return dict(row)


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_type: str,
    entity_type: str,
    entity_id: int,
    payload: Mapping[str, Any],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id,
            event_type,
            entity_type,
            entity_id,
            payload_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            trace_id,
            event_type,
            entity_type,
            str(entity_id),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            created_at,
        ),
    )


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
