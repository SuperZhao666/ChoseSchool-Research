from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any


CANDIDATE_MODEL_DOCTOR_METRICS = (
    "candidate_identity_hash_mismatch",
    "candidate_missing_audit",
    "candidate_duplicate_audit",
    "candidate_chain_invalid",
    "comparability_contract_hash_mismatch",
    "comparability_missing_audit",
    "comparability_duplicate_audit",
    "comparability_chain_invalid",
    "comparability_subject_contract_invalid",
    "profile_fit_contract_hash_mismatch",
    "profile_fit_input_reference_invalid",
    "profile_fit_missing_audit",
    "profile_fit_duplicate_audit",
    "profile_fit_chain_invalid",
)


def candidate_model_doctor_metrics(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    available = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if not {
        "candidate_target_versions",
        "project_history_comparability_reviews",
    }.issubset(available):
        return {name: 0 for name in CANDIDATE_MODEL_DOCTOR_METRICS}

    candidate_hash_mismatch = 0
    for row in connection.execute(
        """
        SELECT candidate_key, identity_canonical_json,
               identity_canonical_sha256
        FROM candidate_target_versions
        """
    ):
        canonical = _canonicalize(row["identity_canonical_json"])
        expected = _sha256(canonical) if canonical is not None else None
        if (
            canonical != row["identity_canonical_json"]
            or expected != row["identity_canonical_sha256"]
            or row["candidate_key"] != f"candidate-v1:{expected}"
        ):
            candidate_hash_mismatch += 1

    review_hash_mismatch = 0
    for row in connection.execute(
        """
        SELECT dimension_contract_json, dimension_contract_sha256,
               evidence_bundle_json, evidence_bundle_sha256
        FROM project_history_comparability_reviews
        """
    ):
        dimension = _canonicalize(row["dimension_contract_json"])
        evidence = _canonicalize(row["evidence_bundle_json"])
        if (
            dimension != row["dimension_contract_json"]
            or evidence != row["evidence_bundle_json"]
            or dimension is None
            or evidence is None
            or _sha256(dimension) != row["dimension_contract_sha256"]
            or _sha256(evidence) != row["evidence_bundle_sha256"]
        ):
            review_hash_mismatch += 1

    profile_fit_available = "candidate_profile_fit_reviews" in available
    profile_fit_hash_mismatch = 0
    if profile_fit_available:
        for row in connection.execute(
            """
            SELECT input_snapshot_json, input_snapshot_sha256,
                   dimension_results_json, dimension_results_sha256,
                   evidence_gaps_json, evidence_gaps_sha256
            FROM candidate_profile_fit_reviews
            """
        ):
            values = (
                (row["input_snapshot_json"], row["input_snapshot_sha256"]),
                (row["dimension_results_json"], row["dimension_results_sha256"]),
                (row["evidence_gaps_json"], row["evidence_gaps_sha256"]),
            )
            if any(
                (canonical := _canonicalize(raw_json)) is None
                or canonical != raw_json
                or _sha256(canonical) != expected_hash
                for raw_json, expected_hash in values
            ):
                profile_fit_hash_mismatch += 1

    profile_fit_metrics = {
        "profile_fit_contract_hash_mismatch": profile_fit_hash_mismatch,
        "profile_fit_input_reference_invalid": 0,
        "profile_fit_missing_audit": 0,
        "profile_fit_duplicate_audit": 0,
        "profile_fit_chain_invalid": 0,
    }
    if profile_fit_available:
        profile_fit_metrics.update(
            {
                "profile_fit_input_reference_invalid": _scalar(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM candidate_profile_fit_reviews review
                    WHERE NOT EXISTS (
                        SELECT 1 FROM candidate_target_versions target
                        WHERE target.id = review.candidate_target_version_id
                          AND target.profile_id = review.profile_id
                          AND target.candidate_key = json_extract(
                              review.input_snapshot_json, '$.candidate_key'
                          )
                    )
                       OR json_extract(
                              review.input_snapshot_json, '$.profile_id'
                          ) != review.profile_id
                       OR json_extract(
                              review.input_snapshot_json,
                              '$.candidate_target_version_id'
                          ) != review.candidate_target_version_id
                       OR EXISTS (
                           SELECT 1 FROM json_each(
                               review.input_snapshot_json,
                               '$.preference_event_ids'
                           ) item
                           WHERE NOT EXISTS (
                               SELECT 1 FROM applicant_preference_events event
                               WHERE event.id = CAST(item.value AS INTEGER)
                                 AND event.profile_id = review.profile_id
                           )
                       )
                       OR EXISTS (
                           SELECT 1 FROM json_each(
                               review.input_snapshot_json,
                               '$.context_event_ids'
                           ) item
                           WHERE NOT EXISTS (
                               SELECT 1 FROM applicant_context_events event
                               WHERE event.id = CAST(item.value AS INTEGER)
                                 AND event.profile_id = review.profile_id
                           )
                       )
                    """,
                ),
                "profile_fit_missing_audit": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM candidate_profile_fit_reviews review
                    WHERE NOT EXISTS (
                        SELECT 1 FROM audit_events audit
                        WHERE audit.trace_id = review.trace_id
                          AND audit.event_type =
                              'candidate_profile_fit_review_added'
                          AND audit.entity_type =
                              'candidate_profile_fit_review'
                          AND audit.entity_id = CAST(review.id AS TEXT)
                    )
                    """,
                ),
                "profile_fit_duplicate_audit": _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM candidate_profile_fit_reviews review
                    WHERE 1 < (
                        SELECT COUNT(*) FROM audit_events audit
                        WHERE audit.trace_id = review.trace_id
                          AND audit.event_type =
                              'candidate_profile_fit_review_added'
                          AND audit.entity_type =
                              'candidate_profile_fit_review'
                          AND audit.entity_id = CAST(review.id AS TEXT)
                    )
                    """,
                ),
                "profile_fit_chain_invalid": _scalar(
                    connection,
                    """
                    WITH RECURSIVE
                    roots AS (
                        SELECT id, profile_id, candidate_target_version_id
                        FROM candidate_profile_fit_reviews
                        WHERE supersedes_review_id IS NULL
                          AND review_sequence = 1
                    ),
                    reachable(id, profile_id, candidate_target_version_id) AS (
                        SELECT id, profile_id, candidate_target_version_id
                        FROM roots
                        UNION
                        SELECT child.id, child.profile_id,
                               child.candidate_target_version_id
                        FROM candidate_profile_fit_reviews child
                        JOIN reachable predecessor
                          ON child.supersedes_review_id = predecessor.id
                         AND child.profile_id = predecessor.profile_id
                         AND child.candidate_target_version_id =
                             predecessor.candidate_target_version_id
                    )
                    SELECT COUNT(*)
                    FROM candidate_profile_fit_reviews review
                    WHERE NOT EXISTS (
                        SELECT 1 FROM reachable
                        WHERE reachable.id = review.id
                    )
                       OR (
                           review.supersedes_review_id IS NOT NULL
                           AND NOT EXISTS (
                               SELECT 1
                               FROM candidate_profile_fit_reviews predecessor
                               WHERE predecessor.id =
                                   review.supersedes_review_id
                                 AND predecessor.profile_id = review.profile_id
                                 AND predecessor.candidate_target_version_id =
                                     review.candidate_target_version_id
                                 AND predecessor.review_sequence + 1 =
                                     review.review_sequence
                           )
                       )
                    """,
                ),
            }
        )

    return {
        "candidate_identity_hash_mismatch": candidate_hash_mismatch,
        "candidate_missing_audit": _scalar(
            connection,
            """
            SELECT COUNT(*) FROM candidate_target_versions target
            WHERE NOT EXISTS (
                SELECT 1 FROM audit_events audit
                WHERE audit.trace_id = target.trace_id
                  AND audit.event_type = 'candidate_target_version_added'
                  AND audit.entity_type = 'candidate_target_version'
                  AND audit.entity_id = CAST(target.id AS TEXT)
            )
            """,
        ),
        "candidate_duplicate_audit": _scalar(
            connection,
            """
            SELECT COUNT(*) FROM candidate_target_versions target
            WHERE 1 < (
                SELECT COUNT(*) FROM audit_events audit
                WHERE audit.trace_id = target.trace_id
                  AND audit.event_type = 'candidate_target_version_added'
                  AND audit.entity_type = 'candidate_target_version'
                  AND audit.entity_id = CAST(target.id AS TEXT)
            )
            """,
        ),
        "candidate_chain_invalid": _scalar(
            connection,
            """
            WITH RECURSIVE
            roots AS (
                SELECT id, candidate_key FROM candidate_target_versions
                WHERE supersedes_version_id IS NULL AND version_number = 1
            ),
            reachable(id, candidate_key) AS (
                SELECT id, candidate_key FROM roots
                UNION
                SELECT child.id, child.candidate_key
                FROM candidate_target_versions child
                JOIN reachable predecessor
                  ON child.supersedes_version_id = predecessor.id
                 AND child.candidate_key = predecessor.candidate_key
            )
            SELECT COUNT(*)
            FROM candidate_target_versions target
            WHERE NOT EXISTS (
                SELECT 1 FROM reachable WHERE reachable.id = target.id
            )
               OR (
                    target.supersedes_version_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM candidate_target_versions predecessor
                        WHERE predecessor.id = target.supersedes_version_id
                          AND predecessor.candidate_key = target.candidate_key
                          AND predecessor.version_number + 1 = target.version_number
                    )
               )
            """,
        ),
        "comparability_contract_hash_mismatch": review_hash_mismatch,
        "comparability_missing_audit": _scalar(
            connection,
            """
            SELECT COUNT(*) FROM project_history_comparability_reviews review
            WHERE NOT EXISTS (
                SELECT 1 FROM audit_events audit
                WHERE audit.trace_id = review.trace_id
                  AND audit.event_type = 'project_history_comparability_review_added'
                  AND audit.entity_type = 'project_history_comparability_review'
                  AND audit.entity_id = CAST(review.id AS TEXT)
            )
            """,
        ),
        "comparability_duplicate_audit": _scalar(
            connection,
            """
            SELECT COUNT(*) FROM project_history_comparability_reviews review
            WHERE 1 < (
                SELECT COUNT(*) FROM audit_events audit
                WHERE audit.trace_id = review.trace_id
                  AND audit.event_type = 'project_history_comparability_review_added'
                  AND audit.entity_type = 'project_history_comparability_review'
                  AND audit.entity_id = CAST(review.id AS TEXT)
            )
            """,
        ),
        "comparability_chain_invalid": _scalar(
            connection,
            """
            WITH RECURSIVE
            roots AS (
                SELECT id, candidate_target_version_id, historical_observation_id
                FROM project_history_comparability_reviews
                WHERE supersedes_review_id IS NULL AND review_sequence = 1
            ),
            reachable(id, candidate_target_version_id, historical_observation_id) AS (
                SELECT id, candidate_target_version_id, historical_observation_id
                FROM roots
                UNION
                SELECT child.id, child.candidate_target_version_id,
                       child.historical_observation_id
                FROM project_history_comparability_reviews child
                JOIN reachable predecessor
                  ON child.supersedes_review_id = predecessor.id
                 AND child.candidate_target_version_id =
                     predecessor.candidate_target_version_id
                 AND child.historical_observation_id =
                     predecessor.historical_observation_id
            )
            SELECT COUNT(*)
            FROM project_history_comparability_reviews review
            WHERE NOT EXISTS (
                SELECT 1 FROM reachable WHERE reachable.id = review.id
            )
               OR (
                    review.supersedes_review_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM project_history_comparability_reviews predecessor
                        WHERE predecessor.id = review.supersedes_review_id
                          AND predecessor.candidate_target_version_id =
                              review.candidate_target_version_id
                          AND predecessor.historical_observation_id =
                              review.historical_observation_id
                          AND predecessor.review_sequence + 1 = review.review_sequence
                    )
               )
            """,
        ),
        "comparability_subject_contract_invalid": _scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM v_current_project_history_comparability_reviews review
            JOIN candidate_target_versions target
              ON target.id = review.candidate_target_version_id
            JOIN project_year_observations historical
              ON historical.id = review.historical_observation_id
            LEFT JOIN v_catalog target_catalog
              ON target_catalog.observation_id = target.target_observation_id
             AND target_catalog.admission_year = target.target_year
            LEFT JOIN v_catalog historical_catalog
              ON historical_catalog.observation_id = historical.id
             AND historical_catalog.admission_year = historical.admission_year
            WHERE review.conclusion = 'comparable'
              AND (
                  target.target_basis != 'official_observation'
                  OR target_catalog.strict_22408_status
                        IS NOT 'official_confirmed'
                  OR historical_catalog.strict_22408_status
                        IS NOT 'official_confirmed'
              )
            """,
        ),
        **profile_fit_metrics,
    }


def _canonicalize(raw_json: Any) -> str | None:
    if not isinstance(raw_json, str):
        return None
    try:
        value = json.loads(raw_json)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _scalar(connection: sqlite3.Connection, statement: str) -> int:
    return int(connection.execute(statement).fetchone()[0])
