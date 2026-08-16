from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from chose_school.domain.enums import Strict22408Status
from chose_school.domain.errors import EntityNotFoundError, StateConflictError, ValidationError
from chose_school.domain.models import SubjectVerificationInput
from chose_school.infrastructure.database import Database


class SqliteSubjectVerificationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def add_subject_verification(
        self,
        verification: SubjectVerificationInput,
        derived_status: Strict22408Status,
        trace_id: str,
    ) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                observation = connection.execute(
                    """
                    SELECT o.id, o.admission_year, s.display_name AS school_name
                    FROM project_year_observations o
                    JOIN projects p ON p.id = o.project_id
                    JOIN schools s ON s.id = p.school_id
                    WHERE o.id = ?
                    """,
                    (verification.observation_id,),
                ).fetchone()
                if observation is None:
                    raise EntityNotFoundError(
                        "OBSERVATION_NOT_FOUND",
                        f"catalog observation does not exist: {verification.observation_id}",
                    )
                if observation["admission_year"] != verification.applicable_year:
                    raise ValidationError(
                        "EVIDENCE_YEAR_MISMATCH",
                        "evidence applicable year must equal the observation admission year",
                        {
                            "observation_year": observation["admission_year"],
                            "applicable_year": verification.applicable_year,
                        },
                    )
                if not _institution_matches(
                    str(observation["school_name"]),
                    verification.source_institution or "",
                ):
                    raise ValidationError(
                        "SOURCE_INSTITUTION_MISMATCH",
                        "official catalog institution must match the observation school",
                        {
                            "school": observation["school_name"],
                            "source_institution": verification.source_institution,
                        },
                    )

                source_id = _get_or_create_official_source(connection, verification)
                existing = connection.execute(
                    """
                    SELECT id, politics_code, english_code, math_code,
                           professional_code, derived_status
                    FROM subject_verifications
                    WHERE observation_id = ? AND source_id = ?
                    """,
                    (verification.observation_id, source_id),
                ).fetchone()
                if existing:
                    _assert_same_verification(existing, verification, derived_status)
                    connection.commit()
                    return int(existing["id"])

                cursor = connection.execute(
                    """
                    INSERT INTO subject_verifications(
                        observation_id, politics_code, english_code, math_code,
                        professional_code, derived_status, source_id, note, verified_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        verification.observation_id,
                        verification.politics_code,
                        verification.english_code,
                        verification.math_code,
                        verification.professional_code,
                        derived_status.value,
                        source_id,
                        verification.note,
                        _utc_now(),
                    ),
                )
                verification_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    "subject_verification_added",
                    "subject_verification",
                    str(verification_id),
                    {
                        "observation_id": verification.observation_id,
                        "subject_codes": [
                            verification.politics_code,
                            verification.english_code,
                            verification.math_code,
                            verification.professional_code,
                        ],
                        "derived_status": derived_status.value,
                        "source_url": verification.source_url,
                    },
                )
                connection.commit()
                return verification_id
            except Exception:
                connection.rollback()
                raise


def _get_or_create_official_source(
    connection: sqlite3.Connection,
    verification: SubjectVerificationInput,
) -> int:
    identity_payload = (
        verification.source_content_sha256.lower(),
        verification.source_document_type.value,
        verification.applicable_year,
    )
    identity_key = hashlib.sha256(
        json.dumps(identity_payload, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    now = _utc_now()
    connection.execute(
        """
        INSERT INTO evidence_sources(
            identity_key, title, institution, url, evidence_grade,
            published_date, retrieved_date, source_note, created_at, updated_at,
            document_type, content_sha256, applicable_year
        ) VALUES (?, ?, ?, ?, 'official', ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(identity_key) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (
            identity_key,
            verification.source_title,
            verification.source_institution,
            verification.source_url,
            verification.published_date.isoformat()
            if verification.published_date
            else None,
            verification.retrieved_date.isoformat(),
            verification.note,
            now,
            now,
            verification.source_document_type.value,
            verification.source_content_sha256.lower(),
            verification.applicable_year,
        ),
    )
    return int(
        connection.execute(
            "SELECT id FROM evidence_sources WHERE identity_key = ?",
            (identity_key,),
        ).fetchone()["id"]
    )


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, object],
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


def _assert_same_verification(
    existing: sqlite3.Row,
    verification: SubjectVerificationInput,
    derived_status: Strict22408Status,
) -> None:
    existing_contract = (
        existing["politics_code"],
        existing["english_code"],
        existing["math_code"],
        existing["professional_code"],
        existing["derived_status"],
    )
    requested_contract = (
        verification.politics_code,
        verification.english_code,
        verification.math_code,
        verification.professional_code,
        derived_status.value,
    )
    if existing_contract != requested_contract:
        raise StateConflictError(
            "SOURCE_CONTENT_CONTRADICTION",
            "the same evidence content hash cannot support two subject-code contracts",
            {"verification_id": existing["id"]},
        )


def _institution_matches(school_name: str, institution: str) -> bool:
    normalized_school = _normalize_institution(school_name)
    normalized_institution = _normalize_institution(institution)
    return normalized_school in normalized_institution or normalized_institution in normalized_school


def _normalize_institution(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())
