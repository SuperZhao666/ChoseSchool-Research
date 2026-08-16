from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.candidate_model import (
    CandidateProfileFitReviewInput,
    CandidateTargetVersionInput,
    ProjectHistoryComparabilityReviewInput,
)
from chose_school.infrastructure.database import Database


class SqliteCandidateModelRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_context(self, profile_key: str) -> Mapping[str, Any] | None:
        return self._one(
            "SELECT id AS profile_id, profile_key, target_exam_year "
            "FROM applicant_profiles WHERE profile_key = ?",
            (profile_key,),
        )

    def find_observation_context(
        self, observation_id: int
    ) -> Mapping[str, Any] | None:
        return self._one(
            """
            SELECT
                observation.id AS observation_id,
                observation.project_id,
                observation.admission_year,
                school.canonical_name AS school,
                college.canonical_name AS college,
                COALESCE(NULLIF(trim(project.program_code), ''), 'unspecified') AS program_code,
                COALESCE(NULLIF(trim(project.program_name), ''), 'unspecified') AS program_name,
                COALESCE(NULLIF(trim(project.direction), ''), 'unspecified') AS direction,
                COALESCE(NULLIF(trim(project.campus), ''), 'unspecified') AS campus,
                COALESCE(NULLIF(trim(project.training_location), ''), 'unspecified') AS training_location,
                COALESCE(NULLIF(trim(project.study_mode), ''), 'unspecified') AS study_mode,
                COALESCE(NULLIF(trim(project.training_type_raw), ''), 'unspecified') AS training_type,
                COALESCE(NULLIF(trim(project.admission_type), ''), 'unspecified') AS admission_type,
                COALESCE(NULLIF(trim(project.degree_type), ''), 'unspecified') AS degree_type,
                COALESCE(NULLIF(trim(project.training_arrangement), ''), 'unspecified') AS training_arrangement,
                COUNT(DISTINCT CASE
                    WHEN link.relationship = 'supports'
                     AND source.evidence_grade = 'official'
                     AND source.document_type = 'official_catalog'
                     AND source.applicable_year = observation.admission_year
                     AND length(source.content_sha256) = 64
                     AND source.content_sha256 = lower(source.content_sha256)
                     AND source.content_sha256 NOT GLOB '*[^0-9a-f]*'
                     AND source.url LIKE 'https://%'
                    THEN source.id
                END) AS official_catalog_source_count
            FROM project_year_observations observation
            JOIN projects project ON project.id = observation.project_id
            JOIN schools school ON school.id = project.school_id
            JOIN colleges college ON college.id = project.college_id
            LEFT JOIN observation_sources link ON link.observation_id = observation.id
            LEFT JOIN v_evidence_sources_effective source ON source.id = link.source_id
            WHERE observation.id = ?
            GROUP BY observation.id
            """,
            (observation_id,),
        )

    def find_candidate_target_context(
        self, candidate_target_version_id: int
    ) -> Mapping[str, Any] | None:
        return self._one(
            """
            SELECT target.*,
                   target.school_key AS school,
                   target.college_key AS college,
                   target.direction_key AS direction,
                   target.campus_key AS campus,
                   target.training_location_key AS training_location,
                   target.study_mode_key AS study_mode,
                   target.training_type_key AS training_type,
                   target.admission_type_key AS admission_type,
                   target.degree_type_key AS degree_type,
                   target.training_arrangement_key AS training_arrangement
            FROM candidate_target_versions target
            WHERE target.id = ?
            """,
            (candidate_target_version_id,),
        )

    def find_comparability_review_context(
        self, review_id: int
    ) -> Mapping[str, Any] | None:
        return self._one(
            """
            SELECT id AS review_id, candidate_target_version_id,
                   historical_observation_id, review_sequence
            FROM project_history_comparability_reviews
            WHERE id = ?
            """,
            (review_id,),
        )

    def find_profile_fit_review_context(
        self, review_id: int
    ) -> Mapping[str, Any] | None:
        return self._one(
            """
            SELECT id AS review_id, profile_id, candidate_target_version_id,
                   review_sequence
            FROM candidate_profile_fit_reviews
            WHERE id = ?
            """,
            (review_id,),
        )

    def list_current_preference_event_ids(self, profile_id: int) -> Sequence[int]:
        with self._database.connect_read_only() as connection:
            rows = connection.execute(
                "SELECT id FROM v_current_applicant_preferences "
                "WHERE profile_id = ? ORDER BY id",
                (profile_id,),
            ).fetchall()
        return tuple(int(row["id"]) for row in rows)

    def list_current_context_event_ids(self, profile_id: int) -> Sequence[int]:
        with self._database.connect_read_only() as connection:
            rows = connection.execute(
                "SELECT id FROM v_current_applicant_context "
                "WHERE profile_id = ? ORDER BY id",
                (profile_id,),
            ).fetchall()
        return tuple(int(row["id"]) for row in rows)

    def find_evidence_source_contexts(
        self,
        source_ids: Sequence[int],
        target_observation_id: int | None,
        historical_observation_id: int,
    ) -> Sequence[Mapping[str, Any]]:
        if not source_ids:
            return ()
        placeholders = ", ".join("?" for _ in source_ids)
        with self._database.connect_read_only() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    source.id AS source_id,
                    source.evidence_grade,
                    source.url,
                    source.document_type,
                    source.content_sha256,
                    source.applicable_year,
                    CASE WHEN ? IS NOT NULL AND EXISTS (
                        SELECT 1 FROM observation_sources link
                        WHERE link.observation_id = ?
                          AND link.source_id = source.id
                          AND link.relationship = 'supports'
                    ) THEN 1 ELSE 0 END AS supports_target,
                    CASE WHEN EXISTS (
                        SELECT 1 FROM observation_sources link
                        WHERE link.observation_id = ?
                          AND link.source_id = source.id
                          AND link.relationship = 'supports'
                    ) THEN 1 ELSE 0 END AS supports_historical
                FROM v_evidence_sources_effective source
                WHERE source.id IN ({placeholders})
                ORDER BY source.id
                """,
                (
                    target_observation_id,
                    target_observation_id,
                    historical_observation_id,
                    *source_ids,
                ),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def add_candidate_target_version(
        self,
        profile_id: int,
        target: CandidateTargetVersionInput,
        canonical_identity: Mapping[str, str | int],
        identity_canonical_json: str,
        identity_canonical_sha256: str,
        candidate_key: str,
        target_project_id: int | None,
        version_number: int,
        trace_id: str,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO candidate_target_versions(
                    profile_id, candidate_key, identity_schema,
                    profile_key_snapshot, target_year, school_key, college_key,
                    program_code, program_name, direction_key, campus_key,
                    training_location_key, study_mode_key, training_type_key,
                    admission_type_key, degree_type_key, training_arrangement_key,
                    target_basis, target_project_id, target_observation_id,
                    action, identity_canonical_json, identity_canonical_sha256,
                    version_number, supersedes_version_id, reason, trace_id,
                    created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    profile_id,
                    candidate_key,
                    canonical_identity["schema"],
                    canonical_identity["profile_key"],
                    canonical_identity["target_year"],
                    canonical_identity["school"],
                    canonical_identity["college"],
                    canonical_identity["program_code"],
                    canonical_identity["program_name"],
                    canonical_identity["direction"],
                    canonical_identity["campus"],
                    canonical_identity["training_location"],
                    canonical_identity["study_mode"],
                    canonical_identity["training_type"],
                    canonical_identity["admission_type"],
                    canonical_identity["degree_type"],
                    canonical_identity["training_arrangement"],
                    target.target_basis.value,
                    target_project_id,
                    target.target_observation_id,
                    target.action.value,
                    identity_canonical_json,
                    identity_canonical_sha256,
                    version_number,
                    target.supersedes_version_id,
                    target.reason,
                    trace_id,
                    created_at,
                ),
            )
            target_id = int(cursor.lastrowid)
            connection.commit()
        return target_id

    def add_comparability_review(
        self,
        review: ProjectHistoryComparabilityReviewInput,
        dimension_contract_json: str,
        dimension_contract_sha256: str,
        evidence_bundle_json: str,
        evidence_bundle_sha256: str,
        review_sequence: int,
        trace_id: str,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO project_history_comparability_reviews(
                    candidate_target_version_id, historical_observation_id,
                    review_contract_version, conclusion,
                    dimension_contract_json, dimension_contract_sha256,
                    evidence_bundle_json, evidence_bundle_sha256,
                    review_sequence, supersedes_review_id, summary, trace_id,
                    created_at
                ) VALUES (?, ?, 'project-history-comparability-v1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.candidate_target_version_id,
                    review.historical_observation_id,
                    review.conclusion.value,
                    dimension_contract_json,
                    dimension_contract_sha256,
                    evidence_bundle_json,
                    evidence_bundle_sha256,
                    review_sequence,
                    review.supersedes_review_id,
                    review.summary,
                    trace_id,
                    created_at,
                ),
            )
            review_id = int(cursor.lastrowid)
            connection.commit()
        return review_id

    def add_profile_fit_review(
        self,
        profile_id: int,
        review: CandidateProfileFitReviewInput,
        input_snapshot_json: str,
        input_snapshot_sha256: str,
        dimension_results_json: str,
        dimension_results_sha256: str,
        evidence_gaps_json: str,
        evidence_gaps_sha256: str,
        review_sequence: int,
        trace_id: str,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO candidate_profile_fit_reviews(
                    profile_id, candidate_target_version_id,
                    review_contract_version, strategy_assignment_basis,
                    strategy_bucket, known_preference_fit, output_scope,
                    probability_status, input_snapshot_json,
                    input_snapshot_sha256, dimension_results_json,
                    dimension_results_sha256, evidence_gaps_json,
                    evidence_gaps_sha256, review_sequence,
                    supersedes_review_id, summary, trace_id, created_at
                ) VALUES (
                    ?, ?, 'candidate-profile-fit-v1',
                    'user_strategy_assignment', ?, ?, 'research_only',
                    'not_estimated', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    profile_id,
                    review.candidate_target_version_id,
                    review.strategy_bucket.value,
                    review.known_preference_fit.value,
                    input_snapshot_json,
                    input_snapshot_sha256,
                    dimension_results_json,
                    dimension_results_sha256,
                    evidence_gaps_json,
                    evidence_gaps_sha256,
                    review_sequence,
                    review.supersedes_review_id,
                    review.summary,
                    trace_id,
                    created_at,
                ),
            )
            review_id = int(cursor.lastrowid)
            connection.commit()
        return review_id

    def list_candidate_targets(
        self, profile_id: int, include_history: bool
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "candidate_target_versions"
            if include_history
            else "v_current_candidate_target_versions"
        )
        with self._database.connect_read_only() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM {source}
                WHERE profile_id = ?
                ORDER BY target_year, school_key, college_key, program_code,
                         version_number
                """,
                (profile_id,),
            ).fetchall()
        return tuple(_decode_candidate(row) for row in rows)

    def list_comparability_reviews(
        self,
        candidate_target_version_id: int | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "project_history_comparability_reviews"
            if include_history
            else "v_current_project_history_comparability_reviews"
        )
        predicate = ""
        parameters: list[Any] = []
        if candidate_target_version_id is not None:
            predicate = "WHERE candidate_target_version_id = ?"
            parameters.append(candidate_target_version_id)
        with self._database.connect_read_only() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM {source} {predicate}
                ORDER BY candidate_target_version_id,
                         historical_observation_id, review_sequence
                """,
                parameters,
            ).fetchall()
        return tuple(_decode_review(row) for row in rows)

    def list_profile_fit_reviews(
        self,
        candidate_target_version_id: int | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "candidate_profile_fit_reviews"
            if include_history
            else "v_current_candidate_profile_fit_reviews"
        )
        predicate = ""
        parameters: list[Any] = []
        if candidate_target_version_id is not None:
            predicate = "WHERE candidate_target_version_id = ?"
            parameters.append(candidate_target_version_id)
        with self._database.connect_read_only() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM {source} {predicate}
                ORDER BY candidate_target_version_id, review_sequence
                """,
                parameters,
            ).fetchall()
        return tuple(_decode_profile_fit_review(row) for row in rows)

    def _one(
        self, statement: str, parameters: Sequence[Any]
    ) -> Mapping[str, Any] | None:
        with self._database.connect_read_only() as connection:
            row = connection.execute(statement, parameters).fetchone()
        return dict(row) if row is not None else None


def _decode_candidate(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["identity"] = json.loads(str(item.pop("identity_canonical_json")))
    return item


def _decode_review(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["dimension_contract"] = json.loads(
        str(item.pop("dimension_contract_json"))
    )
    item["evidence_bundle"] = json.loads(str(item.pop("evidence_bundle_json")))
    return item


def _decode_profile_fit_review(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["input_snapshot"] = json.loads(str(item.pop("input_snapshot_json")))
    item["dimension_results"] = json.loads(
        str(item.pop("dimension_results_json"))
    )
    item["evidence_gaps"] = json.loads(str(item.pop("evidence_gaps_json")))
    return item
