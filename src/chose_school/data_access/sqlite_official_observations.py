from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

from chose_school.domain.enums import (
    EvidenceGrade,
    Strict22408Claim,
    Strict22408Status,
)
from chose_school.domain.errors import StateConflictError
from chose_school.domain.models import (
    OfficialProjectObservationInput,
    OfficialProjectObservationResult,
)
from chose_school.infrastructure.database import Database


_IMPORTER_VERSION = "official-project-observation-v1"
_SOURCE_ROW_NUMBER = 2


class SqliteOfficialProjectObservationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def add_official_observation(
        self,
        observation: OfficialProjectObservationInput,
        derived_status: Strict22408Status,
        trace_id: str,
    ) -> OfficialProjectObservationResult:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                now = _utc_now()
                project_id = _get_or_create_project(connection, observation, now)
                source_id = _get_or_create_source(connection, observation, now)
                payload = _observation_payload(observation)
                observation_fingerprint = _observation_fingerprint(
                    payload,
                    observation.source_content_sha256,
                )

                existing = _find_existing_observation(
                    connection,
                    observation_fingerprint,
                    source_id,
                )
                if existing is not None:
                    _assert_existing_contract(existing, observation, derived_status)
                    connection.commit()
                    return OfficialProjectObservationResult(
                        observation_id=int(existing["observation_id"]),
                        verification_id=int(existing["verification_id"]),
                        strict_status=derived_status,
                        created=False,
                    )

                _reject_same_source_identity_conflict(
                    connection,
                    project_id,
                    observation.admission_year,
                    source_id,
                )
                batch_id, raw_row_id = _insert_provenance_envelope(
                    connection,
                    observation,
                    payload,
                    observation_fingerprint,
                    trace_id,
                    now,
                )
                observation_id = _insert_observation(
                    connection,
                    project_id,
                    raw_row_id,
                    observation_fingerprint,
                    observation,
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
                verification_id = _insert_subject_verification(
                    connection,
                    observation_id,
                    source_id,
                    observation,
                    derived_status,
                    now,
                )
                _insert_audit_event(
                    connection,
                    trace_id,
                    "official_project_observation_added",
                    "project_year_observation",
                    str(observation_id),
                    {
                        "admission_year": observation.admission_year,
                        "college": observation.college,
                        "program_code": observation.program_code,
                        "project_id": project_id,
                        "provenance_batch_id": batch_id,
                        "raw_row_id": raw_row_id,
                        "school": observation.school,
                        "source_id": source_id,
                        "strict_status": derived_status.value,
                        "subject_codes": [
                            observation.politics_code,
                            observation.english_code,
                            observation.math_code,
                            observation.professional_code,
                        ],
                        "verification_id": verification_id,
                    },
                    now,
                )
                connection.commit()
                return OfficialProjectObservationResult(
                    observation_id=observation_id,
                    verification_id=verification_id,
                    strict_status=derived_status,
                    created=True,
                )
            except Exception:
                connection.rollback()
                raise


def _get_or_create_project(
    connection: sqlite3.Connection,
    observation: OfficialProjectObservationInput,
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
        """
        SELECT id FROM colleges
        WHERE school_id = ? AND canonical_name = ?
        """,
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

    identity_key = _project_identity_key(
        school_canonical,
        college_canonical,
        observation,
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
    observation: OfficialProjectObservationInput,
    now: str,
) -> int:
    identity_payload = (
        observation.source_content_sha256,
        observation.source_document_type.value,
        observation.applicable_year,
    )
    identity_key = _sha256_json(identity_payload)
    source = connection.execute(
        "SELECT id FROM evidence_sources WHERE identity_key = ?",
        (identity_key,),
    ).fetchone()
    if source is not None:
        return int(source["id"])

    cursor = connection.execute(
        """
        INSERT INTO evidence_sources(
            identity_key, title, institution, url, evidence_grade,
            published_date, retrieved_date, source_note, created_at, updated_at,
            document_type, content_sha256, applicable_year
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity_key,
            observation.source_title,
            observation.source_institution,
            observation.source_url,
            EvidenceGrade.OFFICIAL.value,
            observation.published_date.isoformat()
            if observation.published_date
            else None,
            observation.retrieved_date.isoformat(),
            observation.note,
            now,
            now,
            observation.source_document_type.value,
            observation.source_content_sha256,
            observation.applicable_year,
        ),
    )
    return int(cursor.lastrowid)


def _find_existing_observation(
    connection: sqlite3.Connection,
    observation_fingerprint: str,
    source_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            o.id AS observation_id,
            sv.id AS verification_id,
            sv.politics_code,
            sv.english_code,
            sv.math_code,
            sv.professional_code,
            sv.derived_status
        FROM project_year_observations o
        JOIN subject_verifications sv
          ON sv.observation_id = o.id
         AND sv.source_id = ?
        WHERE o.observation_fingerprint = ?
        """,
        (source_id, observation_fingerprint),
    ).fetchone()


def _assert_existing_contract(
    existing: sqlite3.Row,
    observation: OfficialProjectObservationInput,
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
        observation.politics_code,
        observation.english_code,
        observation.math_code,
        observation.professional_code,
        derived_status.value,
    )
    if existing_contract != requested_contract:
        raise StateConflictError(
            "OFFICIAL_OBSERVATION_CONFLICT",
            "the existing official observation has a different subject contract",
            {"observation_id": existing["observation_id"]},
        )


def _reject_same_source_identity_conflict(
    connection: sqlite3.Connection,
    project_id: int,
    admission_year: int,
    source_id: int,
) -> None:
    existing = connection.execute(
        """
        SELECT o.id
        FROM project_year_observations o
        JOIN observation_sources os ON os.observation_id = o.id
        WHERE o.project_id = ?
          AND o.admission_year = ?
          AND os.source_id = ?
        LIMIT 1
        """,
        (project_id, admission_year, source_id),
    ).fetchone()
    if existing is not None:
        raise StateConflictError(
            "OFFICIAL_OBSERVATION_CONFLICT",
            "the same official source already records this project-year identity differently",
            {"observation_id": existing["id"]},
        )


def _insert_provenance_envelope(
    connection: sqlite3.Connection,
    observation: OfficialProjectObservationInput,
    payload: Mapping[str, Any],
    observation_fingerprint: str,
    trace_id: str,
    now: str,
) -> tuple[str, int]:
    batch_id = f"official-observation:{trace_id}"
    connection.execute(
        """
        INSERT INTO import_batches(
            id, trace_id, source_name, source_path, source_sha256,
            importer_version, status, started_at, completed_at,
            source_file_count, raw_row_count, observation_count,
            issue_count, ignored_member_count
        ) VALUES (?, ?, ?, ?, ?, ?, 'succeeded', ?, ?, 1, 1, 1, 0, 0)
        """,
        (
            batch_id,
            trace_id,
            "official-project-observation",
            observation.source_url,
            observation_fingerprint,
            _IMPORTER_VERSION,
            now,
            now,
        ),
    )

    header = tuple(payload.keys())
    cursor = connection.execute(
        """
        INSERT INTO source_files(
            batch_id, archive_member, content_sha256, header_json,
            expected_column_count, row_count
        ) VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            batch_id,
            f"official_catalog/{observation.source_content_sha256}",
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
    return batch_id, int(cursor.lastrowid)


def _insert_observation(
    connection: sqlite3.Connection,
    project_id: int,
    raw_row_id: int,
    observation_fingerprint: str,
    observation: OfficialProjectObservationInput,
    derived_status: Strict22408Status,
    now: str,
) -> int:
    strict_claim = (
        Strict22408Claim.YES
        if derived_status is Strict22408Status.OFFICIAL_CONFIRMED
        else Strict22408Claim.NO
    )
    cursor = connection.execute(
        """
        INSERT INTO project_year_observations(
            project_id, raw_row_id, observation_fingerprint, admission_year,
            strict_22408_claim, strict_22408_evidence_status,
            strict_22408_status_raw, subject_politics_code,
            subject_english_code, subject_math_code, subject_professional_code,
            evidence_grade, source_level_raw, official_source, retrieval_date,
            notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            raw_row_id,
            observation_fingerprint,
            observation.admission_year,
            strict_claim.value,
            derived_status.value,
            derived_status.value,
            observation.politics_code,
            observation.english_code,
            observation.math_code,
            observation.professional_code,
            EvidenceGrade.OFFICIAL.value,
            observation.source_document_type.value,
            observation.source_url,
            observation.retrieved_date.isoformat(),
            observation.note,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _insert_subject_verification(
    connection: sqlite3.Connection,
    observation_id: int,
    source_id: int,
    observation: OfficialProjectObservationInput,
    derived_status: Strict22408Status,
    now: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO subject_verifications(
            observation_id, politics_code, english_code, math_code,
            professional_code, derived_status, source_id, note, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation_id,
            observation.politics_code,
            observation.english_code,
            observation.math_code,
            observation.professional_code,
            derived_status.value,
            source_id,
            observation.note,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _observation_payload(
    observation: OfficialProjectObservationInput,
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
    }


def _observation_fingerprint(
    payload: Mapping[str, Any],
    source_content_sha256: str,
) -> str:
    return _sha256_json((payload, source_content_sha256))


def _project_identity_key(
    school_canonical: str,
    college_canonical: str,
    observation: OfficialProjectObservationInput,
) -> str:
    identity_parts = (
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
    return _sha256_json(identity_parts)


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
    created_at: str,
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
            created_at,
        ),
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _canonical_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
