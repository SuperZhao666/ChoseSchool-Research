from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from chose_school.business.ports import FactStore
from chose_school.domain.enums import EvidenceGrade, FactDataType
from chose_school.domain.evidence_rules import (
    OFFICIAL_DOCUMENT_TYPES,
    OFFICIAL_GRADES,
    validate_evidence_metadata,
)
from chose_school.domain.errors import ValidationError
from chose_school.domain.fact_registry import (
    FACT_DATA_TYPES,
    FACT_KEYS_FORBID_ORDINARY_GENERAL_EXAM_SCOPE,
    FACT_KEYS_REQUIRING_DERIVATION_NOTE,
    DERIVED_FACT_RULES,
    STATISTICAL_FACT_METHODS,
    WEIGHT_FACT_KEYS,
)
from chose_school.domain.models import FactClaimInput, FactDerivationInput, TypedFactValue


_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
_DECIMAL_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)%?$")
_LOWER_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FactService:
    def __init__(self, store: FactStore) -> None:
        self._store = store

    def add_claim(self, claim: FactClaimInput, trace_id: str) -> int:
        if claim.observation_id < 1:
            raise ValidationError("INVALID_OBSERVATION_ID", "observation_id must be positive")
        if claim.fact_key not in FACT_DATA_TYPES:
            raise ValidationError("UNSUPPORTED_FACT_KEY", f"unsupported fact key: {claim.fact_key}")
        if not claim.population_scope.strip() or not claim.statistic_scope.strip():
            raise ValidationError("EMPTY_FACT_SCOPE", "fact scope cannot be empty")
        if (
            claim.fact_key in FACT_KEYS_FORBID_ORDINARY_GENERAL_EXAM_SCOPE
            and _overclaims_ordinary_general_exam(claim.population_scope)
        ):
            raise ValidationError(
                "FACT_SCOPE_OVERCLAIMS_ORDINARY_GENERAL_EXAM",
                "this fact key cannot use the ordinary_general_exam population scope",
            )
        if (
            claim.fact_key in FACT_KEYS_REQUIRING_DERIVATION_NOTE
            and not (claim.note or "").strip()
        ):
            raise ValidationError(
                "DERIVED_FACT_NOTE_REQUIRED",
                "derived facts require a note naming the formula and operands",
            )
        if claim.evidence_grade in {
            EvidenceGrade.OFFICIAL,
            EvidenceGrade.OFFICIAL_MIXED,
        } and not (claim.source_url or "").startswith(("http://", "https://")):
            raise ValidationError(
                "INVALID_SOURCE_URL",
                "official fact claims require a traceable HTTP(S) URL",
            )
        validate_evidence_metadata(
            claim.evidence_grade,
            claim.source_document_type,
            claim.source_content_sha256,
            claim.applicable_year,
        )

        typed_value = _parse_typed_value(
            claim.fact_key,
            FACT_DATA_TYPES[claim.fact_key],
            claim.raw_value,
        )
        _validate_derivation(claim, typed_value)
        _validate_statistical_calculation(claim)
        return self._store.add_claim(claim, typed_value, trace_id)

    def resolve_claim(self, claim_id: int, reason: str, trace_id: str) -> int:
        if claim_id < 1:
            raise ValidationError("INVALID_CLAIM_ID", "claim_id must be positive")
        if not reason.strip():
            raise ValidationError("EMPTY_RESOLUTION_REASON", "resolution reason is required")
        return self._store.resolve_claim(claim_id, reason.strip(), trace_id)

    def unresolve_claim(self, claim_id: int, reason: str, trace_id: str) -> int:
        if claim_id < 1:
            raise ValidationError("INVALID_CLAIM_ID", "claim_id must be positive")
        if not reason.strip():
            raise ValidationError("EMPTY_RESOLUTION_REASON", "resolution reason is required")
        return self._store.unresolve_claim(claim_id, reason.strip(), trace_id)

    def list_claims(self, observation_id: int) -> Sequence[Mapping[str, Any]]:
        if observation_id < 1:
            raise ValidationError("INVALID_OBSERVATION_ID", "observation_id must be positive")
        return self._store.list_claims(observation_id)

    def list_conflicts(self, limit: int) -> Sequence[Mapping[str, Any]]:
        if not 1 <= limit <= 100_000:
            raise ValidationError("INVALID_LIMIT", "limit must be between 1 and 100000")
        return self._store.list_conflicts(limit)


def _parse_typed_value(
    fact_key: str,
    data_type: FactDataType,
    raw_value: str,
) -> TypedFactValue:
    value = raw_value.strip()
    if not value:
        raise ValidationError("EMPTY_FACT_VALUE", "fact value cannot be empty")
    if data_type is FactDataType.INTEGER:
        if not _INTEGER_PATTERN.fullmatch(value):
            raise ValidationError("NON_ATOMIC_INTEGER", "integer fact values must be atomic integers")
        parsed = int(value)
        if parsed < 0:
            raise ValidationError("NEGATIVE_FACT_VALUE", "integer fact values cannot be negative")
        return TypedFactValue(data_type=data_type, integer_value=parsed)
    if data_type is FactDataType.DECIMAL:
        if not _DECIMAL_PATTERN.fullmatch(value):
            raise ValidationError("NON_ATOMIC_DECIMAL", "decimal fact values must be atomic numbers")
        is_percent = value.endswith("%")
        parsed = float(value[:-1] if is_percent else value)
        if is_percent:
            parsed /= 100
        if parsed < 0:
            raise ValidationError("NEGATIVE_FACT_VALUE", "decimal fact values cannot be negative")
        if fact_key in WEIGHT_FACT_KEYS and not 0 <= parsed <= 1:
            raise ValidationError(
                "WEIGHT_OUT_OF_RANGE",
                "weight facts must be between 0 and 1 or use a percent sign",
            )
        return TypedFactValue(data_type=data_type, decimal_value=parsed)
    if data_type is FactDataType.BOOLEAN:
        normalized = value.casefold()
        if normalized in {"true", "yes", "是", "1"}:
            return TypedFactValue(data_type=data_type, boolean_value=True)
        if normalized in {"false", "no", "否", "0"}:
            return TypedFactValue(data_type=data_type, boolean_value=False)
        raise ValidationError(
            "INVALID_BOOLEAN_FACT",
            "boolean fact values must be true/false, yes/no, or 是/否",
        )
    return TypedFactValue(data_type=data_type, text_value=value)


def _overclaims_ordinary_general_exam(population_scope: str) -> bool:
    normalized = population_scope.strip().casefold().replace("-", "_").replace(" ", "_")
    return (
        "ordinary_general_exam" in normalized
        or "普通统考" in population_scope
        or "普通招考" in population_scope
        or "排除专项" in population_scope
        or "无专项" in population_scope
    )


def _validate_derivation(
    claim: FactClaimInput,
    typed_value: TypedFactValue,
) -> None:
    expected_rule = DERIVED_FACT_RULES.get(claim.fact_key)
    if expected_rule is None:
        if claim.derivation is not None:
            raise ValidationError(
                "NON_DERIVED_FACT_HAS_DERIVATION",
                "non-derived fact keys cannot carry derivation metadata",
            )
        return

    derivation = claim.derivation
    if derivation is None:
        raise ValidationError(
            "DERIVED_FACT_METADATA_REQUIRED",
            "derived facts require structured operator and operand metadata",
        )
    expected_operator, expected_left_key, expected_right_key = expected_rule
    if derivation.operator != expected_operator:
        raise ValidationError(
            "INVALID_DERIVATION_OPERATOR",
            f"{claim.fact_key} requires the {expected_operator} operator",
        )
    if (
        derivation.left_fact_key != expected_left_key
        or derivation.right_fact_key != expected_right_key
    ):
        raise ValidationError(
            "INVALID_DERIVATION_OPERANDS",
            (
                f"{claim.fact_key} requires {expected_left_key} "
                f"{expected_operator} {expected_right_key}"
            ),
        )
    left_value = _require_non_negative_integer_operand(
        derivation,
        "left_integer_value",
    )
    right_value = _require_non_negative_integer_operand(
        derivation,
        "right_integer_value",
    )
    if claim.evidence_grade not in OFFICIAL_GRADES or (
        claim.source_document_type not in OFFICIAL_DOCUMENT_TYPES
    ):
        raise ValidationError(
            "DERIVED_FACT_OFFICIAL_SOURCE_REQUIRED",
            "derived quota operands must come from the claim's single official source",
        )
    if typed_value.integer_value != left_value - right_value:
        raise ValidationError(
            "DERIVATION_RESULT_MISMATCH",
            "derived fact value must equal left integer minus right integer",
            {
                "left_integer_value": left_value,
                "right_integer_value": right_value,
                "expected_value": left_value - right_value,
                "actual_value": typed_value.integer_value,
            },
        )


def _require_non_negative_integer_operand(
    derivation: FactDerivationInput,
    field_name: str,
) -> int:
    value = getattr(derivation, field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(
            "INVALID_DERIVATION_INTEGER",
            "derived fact operands must be non-negative integers",
            {"field": field_name},
        )
    return value


def _validate_statistical_calculation(claim: FactClaimInput) -> None:
    expected_method = STATISTICAL_FACT_METHODS.get(claim.fact_key)
    supplied = (
        claim.sample_size,
        claim.calculation_method_key,
        claim.calculation_input_sha256,
    )
    if expected_method is None:
        if any(value is not None for value in supplied):
            raise ValidationError(
                "NON_STATISTICAL_FACT_HAS_CALCULATION_METADATA",
                "only score-distribution fact keys can carry calculation metadata",
            )
        return

    if (
        isinstance(claim.sample_size, bool)
        or not isinstance(claim.sample_size, int)
        or claim.sample_size <= 0
    ):
        raise ValidationError(
            "STATISTICAL_SAMPLE_SIZE_REQUIRED",
            "score-distribution facts require a positive integer sample_size",
        )
    if claim.calculation_method_key != expected_method:
        raise ValidationError(
            "STATISTICAL_METHOD_MISMATCH",
            f"{claim.fact_key} requires calculation method {expected_method}",
        )
    if not _LOWER_SHA256_PATTERN.fullmatch(
        claim.calculation_input_sha256 or ""
    ):
        raise ValidationError(
            "INVALID_CALCULATION_INPUT_SHA256",
            "calculation_input_sha256 must be exactly 64 lowercase hexadecimal characters",
        )
