from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.models import FairnessReviewInput
from chose_school.infrastructure.database import Database


class SqliteFairnessReviewRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_profile_id(self, profile_key: str) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM applicant_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        return int(row["id"]) if row else None

    def observation_exists(self, observation_id: int) -> bool:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM project_year_observations WHERE id = ?",
                (observation_id,),
            ).fetchone()
        return row is not None

    def add_fairness_review(
        self,
        profile_id: int,
        review: FairnessReviewInput,
        review_version: str,
        canonical_evidence_json: str,
        trace_id: str,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO candidate_fairness_reviews(
                    profile_id, observation_id, review_version, conclusion,
                    summary, evidence_json, trace_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    review.observation_id,
                    review_version,
                    review.conclusion.value,
                    review.summary,
                    canonical_evidence_json,
                    trace_id,
                    created_at,
                ),
            )
            review_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO audit_events(
                    trace_id, event_type, entity_type, entity_id,
                    payload_json, created_at
                ) VALUES (?, 'candidate_fairness_review_added',
                          'candidate_fairness_review', ?, ?, ?)
                """,
                (
                    trace_id,
                    str(review_id),
                    json.dumps(
                        {
                            "profile_id": profile_id,
                            "observation_id": review.observation_id,
                            "review_version": review_version,
                            "conclusion": review.conclusion.value,
                            "evidence_count": len(review.evidence),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    created_at,
                ),
            )
            connection.commit()
        return review_id

    def list_fairness_reviews(
        self,
        profile_id: int,
        observation_id: int | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]:
        source = (
            "candidate_fairness_reviews"
            if include_history
            else "v_current_candidate_fairness_reviews"
        )
        clauses = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if observation_id is not None:
            clauses.append("observation_id = ?")
            parameters.append(observation_id)
        order = "id" if include_history else "observation_id"
        with self._database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id AS review_id, profile_id, observation_id,
                       review_version, conclusion, summary, evidence_json,
                       trace_id, created_at
                FROM {source}
                WHERE {' AND '.join(clauses)}
                ORDER BY {order}
                """,
                parameters,
            ).fetchall()
        return tuple(_deserialize(row) for row in rows)


def _deserialize(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["evidence"] = json.loads(str(item.pop("evidence_json")))
    return item
