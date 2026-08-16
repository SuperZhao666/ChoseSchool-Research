from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from chose_school.domain.models import FactClaimInput, FactDerivationInput, TypedFactValue
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.fact_registry import DERIVED_FACT_RULES, STATISTICAL_FACT_METHODS
from chose_school.infrastructure.database import Database


class SqliteFactRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def add_claim(
        self,
        claim: FactClaimInput,
        typed_value: TypedFactValue,
        trace_id: str,
    ) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                observation = connection.execute(
                    "SELECT id, admission_year FROM project_year_observations WHERE id = ?",
                    (claim.observation_id,),
                ).fetchone()
                if observation is None:
                    raise EntityNotFoundError(
                        "OBSERVATION_NOT_FOUND",
                        f"catalog observation does not exist: {claim.observation_id}",
                    )
                if observation["admission_year"] != claim.applicable_year:
                    raise ValidationError(
                        "EVIDENCE_YEAR_MISMATCH",
                        "evidence applicable year must equal the observation admission year",
                        {
                            "observation_year": observation["admission_year"],
                            "applicable_year": claim.applicable_year,
                        },
                    )
                definition = connection.execute(
                    "SELECT id, data_type FROM fact_definitions WHERE fact_key = ?",
                    (claim.fact_key,),
                ).fetchone()
                if definition is None:
                    raise EntityNotFoundError(
                        "FACT_DEFINITION_NOT_FOUND",
                        f"fact definition does not exist: {claim.fact_key}",
                    )
                if definition["data_type"] != typed_value.data_type.value:
                    raise ValidationError(
                        "FACT_TYPE_MISMATCH",
                        "typed fact value does not match fact definition",
                    )

                source_id = _get_or_create_source(connection, claim)
                claim_fingerprint = _claim_fingerprint(claim, typed_value, source_id)
                existing = connection.execute(
                    "SELECT id FROM fact_claims WHERE claim_fingerprint = ?",
                    (claim_fingerprint,),
                ).fetchone()
                if existing:
                    connection.commit()
                    return int(existing["id"])

                cursor = connection.execute(
                    """
                    INSERT INTO fact_claims(
                        claim_fingerprint, observation_id, fact_definition_id,
                        population_scope, statistic_scope, value_integer,
                        value_decimal, value_text, value_boolean, source_id,
                        evidence_grade, note, trace_id, created_at,
                        derivation_operator, derivation_left_fact_key,
                        derivation_left_value_integer,
                        derivation_right_fact_key,
                        derivation_right_value_integer,
                        sample_size, calculation_method_key,
                        calculation_input_sha256
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        claim_fingerprint,
                        claim.observation_id,
                        int(definition["id"]),
                        claim.population_scope,
                        claim.statistic_scope,
                        typed_value.integer_value,
                        typed_value.decimal_value,
                        typed_value.text_value,
                        int(typed_value.boolean_value)
                        if typed_value.boolean_value is not None
                        else None,
                        source_id,
                        claim.evidence_grade.value,
                        claim.note,
                        trace_id,
                        _utc_now(),
                        claim.derivation.operator if claim.derivation else None,
                        claim.derivation.left_fact_key if claim.derivation else None,
                        (
                            claim.derivation.left_integer_value
                            if claim.derivation
                            else None
                        ),
                        claim.derivation.right_fact_key if claim.derivation else None,
                        (
                            claim.derivation.right_integer_value
                            if claim.derivation
                            else None
                        ),
                        claim.sample_size,
                        claim.calculation_method_key,
                        claim.calculation_input_sha256,
                    ),
                )
                claim_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    "fact_claim_added",
                    "fact_claim",
                    str(claim_id),
                    _fact_claim_audit_payload(
                        claim,
                        typed_value,
                        source_id,
                        claim_fingerprint,
                    ),
                )
                connection.commit()
                return claim_id
            except Exception:
                connection.rollback()
                raise

    def resolve_claim(self, claim_id: int, reason: str, trace_id: str) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                claim = connection.execute(
                    """
                    SELECT observation_id, fact_definition_id, population_scope,
                           statistic_scope
                    FROM fact_claims WHERE id = ?
                    """,
                    (claim_id,),
                ).fetchone()
                if claim is None:
                    raise EntityNotFoundError(
                        "FACT_CLAIM_NOT_FOUND",
                        f"fact claim does not exist: {claim_id}",
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO fact_resolutions(
                        observation_id, fact_definition_id, population_scope,
                        statistic_scope, selected_claim_id, resolution_action,
                        reason, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'accept', ?, ?, ?)
                    """,
                    (
                        claim["observation_id"],
                        claim["fact_definition_id"],
                        claim["population_scope"],
                        claim["statistic_scope"],
                        claim_id,
                        reason,
                        trace_id,
                        _utc_now(),
                    ),
                )
                resolution_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    "fact_claim_resolved",
                    "fact_resolution",
                    str(resolution_id),
                    {"selected_claim_id": claim_id, "reason": reason},
                )
                connection.commit()
                return resolution_id
            except Exception:
                connection.rollback()
                raise

    def unresolve_claim(self, claim_id: int, reason: str, trace_id: str) -> int:
        with self._database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                claim = connection.execute(
                    """
                    SELECT observation_id, fact_definition_id, population_scope,
                           statistic_scope
                    FROM fact_claims WHERE id = ?
                    """,
                    (claim_id,),
                ).fetchone()
                if claim is None:
                    raise EntityNotFoundError(
                        "FACT_CLAIM_NOT_FOUND",
                        f"fact claim does not exist: {claim_id}",
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO fact_resolutions(
                        observation_id, fact_definition_id, population_scope,
                        statistic_scope, selected_claim_id, resolution_action,
                        reason, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, NULL, 'unresolved', ?, ?, ?)
                    """,
                    (
                        claim["observation_id"],
                        claim["fact_definition_id"],
                        claim["population_scope"],
                        claim["statistic_scope"],
                        reason,
                        trace_id,
                        _utc_now(),
                    ),
                )
                resolution_id = int(cursor.lastrowid)
                _insert_audit_event(
                    connection,
                    trace_id,
                    "fact_resolution_unresolved",
                    "fact_resolution",
                    str(resolution_id),
                    {"identity_claim_id": claim_id, "reason": reason},
                )
                connection.commit()
                return resolution_id
            except Exception:
                connection.rollback()
                raise

    def list_claims(self, observation_id: int) -> Sequence[Mapping[str, Any]]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    vc.*,
                    CASE
                        WHEN cr.selected_claim_id = vc.claim_id
                         AND cr.resolution_action = 'accept' THEN 1
                        ELSE 0
                    END AS is_current_resolution,
                    cr.resolution_id,
                    cr.reason AS resolution_reason
                FROM v_fact_claims vc
                LEFT JOIN v_current_fact_resolutions cr
                  ON cr.observation_id = vc.observation_id
                 AND cr.fact_key = vc.fact_key
                 AND cr.population_scope = vc.population_scope
                 AND cr.statistic_scope = vc.statistic_scope
                WHERE vc.observation_id = ?
                ORDER BY vc.fact_key, vc.population_scope, vc.statistic_scope,
                         vc.created_at, vc.claim_id
                """,
                (observation_id,),
            )
            return tuple(dict(row) for row in rows)

    def list_conflicts(self, limit: int) -> Sequence[Mapping[str, Any]]:
        with self._database.connect() as connection:
            return tuple(
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM v_fact_conflicts
                    ORDER BY observation_id, fact_key, population_scope, statistic_scope
                    LIMIT ?
                    """,
                    (limit,),
                )
            )


def _get_or_create_source(
    connection: sqlite3.Connection,
    claim: FactClaimInput,
) -> int:
    identity_payload = (
        claim.source_content_sha256.lower() if claim.source_content_sha256 else None,
        claim.source_document_type.value,
        claim.applicable_year,
        claim.source_url,
    )
    identity_key = hashlib.sha256(
        json.dumps(identity_payload, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    existing = connection.execute(
        "SELECT id FROM evidence_sources WHERE identity_key = ?",
        (identity_key,),
    ).fetchone()
    if existing is not None:
        return int(existing["id"])

    now = _utc_now()
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
            claim.source_title,
            claim.source_institution,
            claim.source_url,
            claim.evidence_grade.value,
            claim.published_date.isoformat() if claim.published_date else None,
            claim.retrieved_date.isoformat(),
            claim.source_note,
            now,
            now,
            claim.source_document_type.value,
            claim.source_content_sha256.lower() if claim.source_content_sha256 else None,
            claim.applicable_year,
        ),
    )
    return int(cursor.lastrowid)


def _claim_fingerprint(
    claim: FactClaimInput,
    typed_value: TypedFactValue,
    source_id: int,
) -> str:
    base_payload = (
        claim.observation_id,
        claim.fact_key,
        claim.population_scope,
        claim.statistic_scope,
        typed_value.data_type.value,
        typed_value.integer_value,
        typed_value.decimal_value,
        typed_value.text_value,
        typed_value.boolean_value,
        source_id,
    )
    # 普通事实继续沿用原指纹格式，避免历史请求重放时生成重复主张。
    # 推导事实和新统计事实分别使用包含可验证结构的 v2 指纹。
    if claim.fact_key in DERIVED_FACT_RULES:
        derivation = claim.derivation
        payload = (
            *base_payload,
            "derivation_v2",
            derivation.operator if derivation else None,
            derivation.left_fact_key if derivation else None,
            derivation.left_integer_value if derivation else None,
            derivation.right_fact_key if derivation else None,
            derivation.right_integer_value if derivation else None,
            (claim.note or "").strip(),
        )
    elif claim.fact_key in STATISTICAL_FACT_METHODS:
        payload = (
            *base_payload,
            "statistical_calculation_v2",
            claim.sample_size,
            claim.calculation_method_key,
            claim.calculation_input_sha256,
        )
    else:
        payload = base_payload
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _fact_claim_audit_payload(
    claim: FactClaimInput,
    typed_value: TypedFactValue,
    source_id: int,
    claim_fingerprint: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "observation_id": claim.observation_id,
        "fact_key": claim.fact_key,
        "population_scope": claim.population_scope,
        "statistic_scope": claim.statistic_scope,
        "source_id": source_id,
        "claim_fingerprint": claim_fingerprint,
    }
    if claim.derivation is not None:
        payload["derivation"] = _derivation_payload(claim.derivation)
        payload["derived_integer_value"] = typed_value.integer_value
    if claim.fact_key in STATISTICAL_FACT_METHODS:
        payload["calculation"] = {
            "sample_size": claim.sample_size,
            "method_key": claim.calculation_method_key,
            "input_sha256": claim.calculation_input_sha256,
        }
    return payload


def _derivation_payload(derivation: FactDerivationInput) -> dict[str, Any]:
    return {
        "operator": derivation.operator,
        "left_fact_key": derivation.left_fact_key,
        "left_integer_value": derivation.left_integer_value,
        "right_fact_key": derivation.right_fact_key,
        "right_integer_value": derivation.right_integer_value,
    }


def _insert_audit_event(
    connection: sqlite3.Connection,
    trace_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
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
