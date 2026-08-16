from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping

from chose_school.domain.models import SelectionReadinessFacts
from chose_school.infrastructure.database import Database


class SqliteSelectionReadinessRepository:
    """Read a consistent, side-effect-free projection for selection gates."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def read_facts(
        self,
        profile_id: int | None,
        target_exam_year: int,
    ) -> SelectionReadinessFacts:
        with self._database.connect_read_only() as connection:
            current_preferences = (
                tuple(
                    _deserialize_preference(row)
                    for row in connection.execute(
                        """
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
                        FROM v_current_applicant_preferences
                        WHERE profile_id = ?
                        ORDER BY dimension, subject_key
                        """,
                        (profile_id,),
                    )
                )
                if profile_id is not None
                else ()
            )
            catalog_counts = {
                str(row["strict_22408_status"]): int(row["observation_count"])
                for row in connection.execute(
                    """
                    SELECT strict_22408_status, COUNT(*) AS observation_count
                    FROM v_catalog
                    WHERE admission_year = ?
                    GROUP BY strict_22408_status
                    """,
                    (target_exam_year,),
                )
            }
            target_year_observation_count = sum(catalog_counts.values())
            active_candidate_counts = (
                _active_candidate_counts(
                    connection,
                    profile_id,
                    target_exam_year,
                )
                if profile_id is not None
                else {
                    "total": 0,
                    "research_hypothesis": 0,
                    "official_observation": 0,
                    "official_confirmed": 0,
                }
            )
            legacy_snapshot_count = (
                _scalar(
                    connection,
                    "SELECT COUNT(*) FROM decision_snapshots WHERE profile_id = ?",
                    (profile_id,),
                )
                if profile_id is not None
                else 0
            )
            legacy_candidate_count = (
                _scalar(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM decision_candidates candidate
                    JOIN decision_snapshots snapshot ON snapshot.id = candidate.snapshot_id
                    WHERE snapshot.profile_id = ?
                    """,
                    (profile_id,),
                )
                if profile_id is not None
                else 0
            )
            fairness_review_count = (
                _scalar(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM v_current_candidate_fairness_reviews
                    WHERE profile_id = ?
                    """,
                    (profile_id,),
                )
                if profile_id is not None
                else 0
            )
            adverse_fairness_review_count = (
                _scalar(
                    connection,
                    """
                    SELECT COUNT(*)
                    FROM v_current_candidate_fairness_reviews
                    WHERE profile_id = ? AND conclusion = 'adverse'
                    """,
                    (profile_id,),
                )
                if profile_id is not None
                else 0
            )
        return SelectionReadinessFacts(
            profile_id=profile_id,
            current_preferences=current_preferences,
            target_year_observation_count=target_year_observation_count,
            official_confirmed_target_year_count=catalog_counts.get(
                "official_confirmed",
                0,
            ),
            official_pending_target_year_count=catalog_counts.get(
                "official_pending_catalog",
                0,
            ),
            legacy_snapshot_count=legacy_snapshot_count,
            legacy_candidate_count=legacy_candidate_count,
            active_candidate_count=active_candidate_counts["total"],
            active_research_hypothesis_count=(
                active_candidate_counts["research_hypothesis"]
            ),
            active_official_observation_count=(
                active_candidate_counts["official_observation"]
            ),
            active_official_confirmed_count=(
                active_candidate_counts["official_confirmed"]
            ),
            fairness_review_count=fairness_review_count,
            adverse_fairness_review_count=adverse_fairness_review_count,
        )


def _active_candidate_counts(
    connection: sqlite3.Connection,
    profile_id: int,
    target_exam_year: int,
) -> dict[str, int]:
    """Count only current active targets for this profile and target year.

    The global catalog remains useful diagnostics, but catalog readiness must
    follow each official candidate's exact observation binding.  A research
    hypothesis has no observation by design and therefore cannot be counted as
    officially confirmed.
    """

    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(CASE
                WHEN target.target_basis = 'research_hypothesis' THEN 1
            END) AS research_hypothesis,
            COUNT(CASE
                WHEN target.target_basis = 'official_observation' THEN 1
            END) AS official_observation,
            COUNT(CASE
                WHEN target.target_basis = 'official_observation'
                 AND catalog.observation_id = target.target_observation_id
                 AND catalog.admission_year = target.target_year
                 AND catalog.strict_22408_status = 'official_confirmed'
                THEN 1
            END) AS official_confirmed
        FROM v_active_candidate_targets target
        LEFT JOIN v_catalog catalog
          ON catalog.observation_id = target.target_observation_id
        WHERE target.profile_id = ?
          AND target.target_year = ?
        """,
        (profile_id, target_exam_year),
    ).fetchone()
    return {
        "total": int(row["total"]),
        "research_hypothesis": int(row["research_hypothesis"]),
        "official_observation": int(row["official_observation"]),
        "official_confirmed": int(row["official_confirmed"]),
    }


def _deserialize_preference(row: Mapping[str, Any]) -> Mapping[str, Any]:
    item = dict(row)
    item["value"] = json.loads(str(item.pop("value_json")))
    return item


def _scalar(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...],
) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])
