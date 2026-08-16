from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

from chose_school.domain.enums import (
    EvidenceDocumentType,
    EvidenceGrade,
    Strict22408Claim,
    Strict22408Status,
)
from chose_school.domain.errors import StateConflictError
from chose_school.domain.models import (
    SecondaryProjectObservationInput,
    SecondaryProjectObservationResult,
)
from chose_school.infrastructure.database import Database


_IMPORTER_VERSION = "secondary-project-observation-v1"
_SOURCE_ROW_NUMBER = 2


class SqliteSecondaryProjectObservationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def add_secondary_observation(
        self,
        observation: SecondaryProjectObservationInput,
        strict_claim: Strict22408Claim,
        derived_status: Strict22408Status,
        trace_id: str,
    ) -> SecondaryProjectObservationResult:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                now = _utc_now()
                project_id = _get_or_create_project(connection, observation, now)
                source_id = _get_or_create_source(connection, observation, now)
                payload = _observation_payload(observation)
                fingerprint = _sha256_json(
                    (
                        payload,
                        observation.source_content_sha256,
                        EvidenceDocumentType.SECONDARY_SUMMARY.value,
                    )
                )
                existing = connection.execute(
                    """
                    SELECT o.id, o.strict_22408_claim,
                           o.strict_22408_evidence_status
                    FROM project_year_observations o
                    JOIN observation_sources os ON os.observation_id = o.id
                    WHERE o.observation_fingerprint = ? AND os.source_id = ?
                    """,
                    (fingerprint, source_id),
                ).fetchone()
                if existing is not None:
                    _assert_existing_status(existing, strict_claim, derived_status)
                    connection.commit()
                    return SecondaryProjectObservationResult(
                        observation_id=int(existing["id"]),
                        status=derived_status,
                        created=False,
                    )

                conflict = connection.execute(
                    """
                    SELECT o.id
                    FROM project_year_observations o
                    JOIN observation_sources os ON os.observation_id = o.id
                    WHERE o.project_id = ? AND o.admission_year = ?
                      AND os.source_id = ?
                    LIMIT 1
                    """,
                    (project_id, observation.admission_year, source_id),
                ).fetchone()
                if conflict is not None:
                    raise StateConflictError(
                        "SECONDARY_OBSERVATION_SOURCE_CONFLICT",
                        "the same secondary source already interprets this project-year differently",
                        {"observation_id": int(conflict["id"])},
                    )

                raw_row_id = _insert_provenance(
                    connection,
                    observation,
                    payload,
                    fingerprint,
                    trace_id,
                    now,
                )
                observation_id = _insert_observation(
                    connection,
                    project_id,
                    raw_row_id,
                    fingerprint,
                    observation,
                    strict_claim,
                    derived_status,
                    now,
                )
                connection.execute(
                    """
                    INSERT INTO observation_sources(
                        observation_id, source_id, relationship
                    ) VALUES (?, ?, 'supports')
                    """,
                    (observation_id, source_id),
                )
                _insert_audit_event(
                    connection,
                    trace_id,
                    observation_id,
                    project_id,
                    source_id,
                    observation,
                    strict_claim,
                    derived_status,
                    now,
                )
                connection.commit()
                return SecondaryProjectObservationResult(
                    observation_id=observation_id,
                    status=derived_status,
                    created=True,
                )
            except Exception:
                connection.rollback()
                raise


def _get_or_create_project(
    connection: sqlite3.Connection,
    observation: SecondaryProjectObservationInput,
    now: str,
) -> int:
    school_canonical = _canonical_text(observation.school)
    school = connection.execute(
        "SELECT id FROM schools WHERE canonical_name = ?",
        (school_canonical,),
    ).fetchone()
    if school is None:
        cursor = connection.execute(
            """
            INSERT INTO schools(canonical_name, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (school_canonical, observation.school, now, now),
        )
        school_id = int(cursor.lastrowid)
    else:
        school_id = int(school["id"])

    college_canonical = _canonical_text(observation.college)
    college = connection.execute(
        "SELECT id FROM colleges WHERE school_id = ? AND canonical_name = ?",
        (school_id, college_canonical),
    ).fetchone()
    if college is None:
        cursor = connection.execute(
            """
            INSERT INTO colleges(
                school_id, canonical_name, display_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (school_id, college_canonical, observation.college, now, now),
        )
        college_id = int(cursor.lastrowid)
    else:
        college_id = int(college["id"])

    identity_key = _sha256_json(
        (
            school_canonical,
            college_canonical,
            observation.program_code,
            observation.program_name,
            observation.direction,
            observation.campus,
            observation.training_location,
            observation.study_mode,
            observation.training_type_raw,
            observation.admission_type,
            observation.degree_type,
            observation.training_arrangement,
        )
    )
    project = connection.execute(
        "SELECT id FROM projects WHERE identity_key = ?",
        (identity_key,),
    ).fetchone()
    if project is not None:
        return int(project["id"])
    cursor = connection.execute(
        """
        INSERT INTO projects(
            identity_key, school_id, college_id, program_code, program_name,
            direction, campus, training_location, study_mode, training_type_raw,
            admission_type, degree_type, training_arrangement, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity_key,
            school_id,
            college_id,
            observation.program_code,
            observation.program_name,
            observation.direction,
            observation.campus,
            observation.training_location,
            observation.study_mode,
            observation.training_type_raw,
            observation.admission_type,
            observation.degree_type,
            observation.training_arrangement,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _get_or_create_source(
    connection: sqlite3.Connection,
    observation: SecondaryProjectObservationInput,
    now: str,
) -> int:
    identity_key = _sha256_json(
        (
            observation.source_content_sha256,
            EvidenceDocumentType.SECONDARY_SUMMARY.value,
            observation.applicable_year,
            observation.source_url,
        )
    )
    existing = connection.execute(
        "SELECT * FROM evidence_sources WHERE identity_key = ?",
        (identity_key,),
    ).fetchone()
    expected = {
        "title": observation.source_title,
        "institution": observation.source_institution,
        "url": observation.source_url,
        "evidence_grade": EvidenceGrade.SECONDARY.value,
        "published_date": observation.published_date.isoformat(),
        "retrieved_date": observation.retrieved_date.isoformat(),
        "document_type": EvidenceDocumentType.SECONDARY_SUMMARY.value,
        "content_sha256": observation.source_content_sha256,
        "applicable_year": observation.applicable_year,
    }
    if existing is not None:
        differing = [key for key, value in expected.items() if existing[key] != value]
        if differing:
            raise StateConflictError(
                "SECONDARY_SOURCE_METADATA_CONFLICT",
                "the immutable secondary source identity has different metadata",
                {"source_id": int(existing["id"]), "fields": differing},
            )
        return int(existing["id"])
    cursor = connection.execute(
        """
        INSERT INTO evidence_sources(
            identity_key, title, institution, url, evidence_grade,
            published_date, retrieved_date, source_note, created_at, updated_at,
            document_type, content_sha256, applicable_year
        ) VALUES (?, ?, ?, ?, 'secondary', ?, ?, NULL, ?, ?,
                  'secondary_summary', ?, ?)
        """,
        (
            identity_key,
            observation.source_title,
            observation.source_institution,
            observation.source_url,
            observation.published_date.isoformat(),
            observation.retrieved_date.isoformat(),
            now,
            now,
            observation.source_content_sha256,
            observation.applicable_year,
        ),
    )
    return int(cursor.lastrowid)


def _assert_existing_status(
    existing: sqlite3.Row,
    strict_claim: Strict22408Claim,
    derived_status: Strict22408Status,
) -> None:
    if (
        existing["strict_22408_claim"] != strict_claim.value
        or existing["strict_22408_evidence_status"] != derived_status.value
    ):
        raise StateConflictError(
            "SECONDARY_OBSERVATION_SOURCE_CONFLICT",
            "the existing secondary observation has a different interpretation",
            {"observation_id": int(existing["id"])},
        )


def _insert_provenance(
    connection: sqlite3.Connection,
    observation: SecondaryProjectObservationInput,
    payload: Mapping[str, Any],
    fingerprint: str,
    trace_id: str,
    now: str,
) -> int:
    batch_id = f"secondary-observation:{trace_id}"
    connection.execute(
        """
        INSERT INTO import_batches(
            id, trace_id, source_name, source_path, source_sha256,
            importer_version, status, started_at, completed_at,
            source_file_count, raw_row_count, observation_count,
            issue_count, ignored_member_count
        ) VALUES (?, ?, 'secondary-project-observation', ?, ?, ?, 'succeeded',
                  ?, ?, 1, 1, 1, 0, 0)
        """,
        (
            batch_id,
            trace_id,
            observation.source_url,
            fingerprint,
            _IMPORTER_VERSION,
            now,
            now,
        ),
    )
    header = tuple(payload)
    cursor = connection.execute(
        """
        INSERT INTO source_files(
            batch_id, archive_member, content_sha256, header_json,
            expected_column_count, row_count
        ) VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            batch_id,
            f"secondary_summary/{observation.source_content_sha256}",
            observation.source_content_sha256,
            json.dumps(header, ensure_ascii=False),
            len(header),
        ),
    )
    source_file_id = int(cursor.lastrowid)
    raw_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    raw_cells = tuple(payload[field] for field in header)
    cursor = connection.execute(
        """
        INSERT INTO raw_catalog_rows(
            source_file_id, source_row_number, row_sha256, raw_json,
            raw_cells_json, cell_count, expected_cell_count, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_file_id,
            _SOURCE_ROW_NUMBER,
            hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
            raw_json,
            json.dumps(raw_cells, ensure_ascii=False),
            len(raw_cells),
            len(header),
            now,
        ),
    )
    return int(cursor.lastrowid)


def _insert_observation(
    connection: sqlite3.Connection,
    project_id: int,
    raw_row_id: int,
    fingerprint: str,
    observation: SecondaryProjectObservationInput,
    strict_claim: Strict22408Claim,
    derived_status: Strict22408Status,
    now: str,
) -> int:
    subject_contract = "+".join(
        (
            observation.politics_code or "",
            observation.english_code or "",
            observation.math_code or "",
            observation.professional_code or "",
        )
    ) if observation.politics_code is not None else None
    cursor = connection.execute(
        """
        INSERT INTO project_year_observations(
            project_id, raw_row_id, observation_fingerprint, admission_year,
            strict_22408_claim, strict_22408_evidence_status,
            strict_22408_status_raw, subject_politics_code,
            subject_english_code, subject_math_code, subject_professional_code,
            evidence_grade, source_level_raw, official_source, retrieval_date,
            notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'secondary',
                  'secondary_summary', NULL, ?, ?, ?, ?)
        """,
        (
            project_id,
            raw_row_id,
            fingerprint,
            observation.admission_year,
            strict_claim.value,
            derived_status.value,
            subject_contract,
            observation.politics_code,
            observation.english_code,
            observation.math_code,
            observation.professional_code,
            observation.retrieved_date.isoformat(),
            observation.note,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    observation_id: int,
    project_id: int,
    source_id: int,
    observation: SecondaryProjectObservationInput,
    strict_claim: Strict22408Claim,
    derived_status: Strict22408Status,
    now: str,
) -> None:
    payload = {
        "admission_year": observation.admission_year,
        "can_confirm_strict_22408": False,
        "establishes_official_catalog": False,
        "project_id": project_id,
        "source_id": source_id,
        "status": derived_status.value,
        "strict_claim": strict_claim.value,
        "subject_contract_complete": observation.politics_code is not None,
    }
    connection.execute(
        """
        INSERT INTO audit_events(
            trace_id, event_type, entity_type, entity_id, payload_json, created_at
        ) VALUES (?, 'secondary_project_observation_added',
                  'project_year_observation', ?, ?, ?)
        """,
        (
            trace_id,
            str(observation_id),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            now,
        ),
    )


def _observation_payload(
    observation: SecondaryProjectObservationInput,
) -> dict[str, str | int | None]:
    return {
        "school": observation.school,
        "college": observation.college,
        "program_code": observation.program_code,
        "program_name": observation.program_name,
        "direction": observation.direction,
        "campus": observation.campus,
        "training_location": observation.training_location,
        "study_mode": observation.study_mode,
        "training_type_raw": observation.training_type_raw,
        "admission_type": observation.admission_type,
        "degree_type": observation.degree_type,
        "training_arrangement": observation.training_arrangement,
        "admission_year": observation.admission_year,
        "subject_politics_code": observation.politics_code,
        "subject_english_code": observation.english_code,
        "subject_math_code": observation.math_code,
        "subject_professional_code": observation.professional_code,
        "source_title": observation.source_title,
        "source_url": observation.source_url,
        "source_institution": observation.source_institution,
        "source_content_sha256": observation.source_content_sha256,
        "applicable_year": observation.applicable_year,
        "published_date": observation.published_date.isoformat(),
        "retrieved_date": observation.retrieved_date.isoformat(),
        "source_excerpt": observation.source_excerpt,
        "project_identity_basis": observation.project_identity_basis,
        "note": observation.note,
    }


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _canonical_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
