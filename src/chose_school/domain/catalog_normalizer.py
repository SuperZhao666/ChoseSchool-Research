from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from chose_school.domain.enums import (
    EvidenceGrade,
    IssueSeverity,
    Strict22408Claim,
    Strict22408Status,
)
from chose_school.domain.models import (
    CatalogObservation,
    NormalizedRow,
    RawCatalogRow,
    ValidationIssue,
)


EXPECTED_CATALOG_HEADER = (
    "school",
    "college",
    "program_code",
    "program_name",
    "direction",
    "campus",
    "training_location",
    "full_time_or_part_time",
    "training_type",
    "year",
    "is_strict_22408",
    "total_plan",
    "recommendation_actual",
    "special_plan",
    "effective_general_exam_quota",
    "retest_cutoff",
    "retest_count",
    "general_exam_admit_count",
    "admit_initial_min",
    "admit_initial_median",
    "admit_initial_mean",
    "initial_exam_weight",
    "retest_weight",
    "machine_test_weight",
    "machine_test_elimination_line",
    "tuition_per_year",
    "study_length",
    "first_choice_protection",
    "source_level",
    "official_source",
    "retrieval_date",
    "notes",
)

INTEGER_FIELDS = (
    "total_plan",
    "recommendation_actual",
    "special_plan",
    "effective_general_exam_quota",
    "retest_count",
    "general_exam_admit_count",
)

DECIMAL_FIELDS = (
    "retest_cutoff",
    "admit_initial_min",
    "admit_initial_median",
    "admit_initial_mean",
    "machine_test_elimination_line",
    "tuition_per_year",
    "study_length",
)

WEIGHT_FIELDS = (
    "initial_exam_weight",
    "retest_weight",
    "machine_test_weight",
)

TARGET_COMPUTING_PROGRAM_CODES = {
    "081200",
    "083500",
    "083900",
    "085400",
    "085404",
    "085405",
    "085410",
    "085411",
    "085412",
}

_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
_DECIMAL_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")
_PROGRAM_CODE_PATTERN = re.compile(r"^\d{6}$")


def normalize_catalog_row(raw_row: RawCatalogRow) -> NormalizedRow:
    issues: list[ValidationIssue] = []
    repair_values, repair_issue = _apply_known_legacy_repair(raw_row)
    if repair_issue is not None:
        issues.append(repair_issue)
    values = {key: _clean_text(value) for key, value in repair_values.items()}

    _validate_structure(raw_row, issues)
    school = values.get("school")
    college = values.get("college")
    if not school:
        issues.append(_error("MISSING_SCHOOL", "school is required", "school"))
    if not college:
        issues.append(_error("MISSING_COLLEGE", "college is required", "college"))
    if not school or not college:
        return NormalizedRow(raw_row=raw_row, observation=None, issues=tuple(issues))

    program_code = values.get("program_code")
    if program_code and not _PROGRAM_CODE_PATTERN.fullmatch(program_code):
        issues.append(
            _warning(
                "INVALID_PROGRAM_CODE",
                "program code must remain a six-digit string",
                "program_code",
                program_code,
            )
        )
        if "/" in program_code:
            issues.append(
                _warning(
                    "COMPOSITE_PROGRAM_CODE",
                    "multiple program codes share one aggregate row and were not split automatically",
                    "program_code",
                    program_code,
                )
            )

    parsed_integers = {
        field: _parse_integer(field, values.get(field), issues)
        for field in INTEGER_FIELDS
    }
    parsed_decimals = {
        field: _parse_decimal(field, values.get(field), issues)
        for field in DECIMAL_FIELDS
    }
    parsed_weights = {
        field: _parse_weight(field, values.get(field), issues)
        for field in WEIGHT_FIELDS
    }

    admission_year = _parse_year(values.get("year"), issues)
    retrieval_date = _parse_date(values.get("retrieval_date"), issues)
    strict_claim = _normalize_strict_claim(values.get("is_strict_22408"))
    evidence_grade = _normalize_evidence_grade(values.get("source_level"))
    evidence_status = _derive_imported_evidence_status(
        strict_claim,
        values.get("is_strict_22408"),
        evidence_grade,
        admission_year,
        values.get("notes"),
    )
    admission_type, degree_type, training_arrangement = _split_training_type(
        values.get("training_type"), issues
    )
    first_choice_protection = _parse_boolean(
        "first_choice_protection",
        values.get("first_choice_protection"),
        issues,
    )

    if len(raw_row.cells) != len(raw_row.header):
        evidence_status = Strict22408Status.CONFLICT

    if strict_claim is Strict22408Claim.YES:
        issues.append(
            _warning(
                "STRICT_22408_UNVERIFIED",
                "source claims strict 22408, but four subject codes are not structured in this CSV",
                "is_strict_22408",
                values.get("is_strict_22408"),
            )
        )
    if program_code and program_code not in TARGET_COMPUTING_PROGRAM_CODES:
        issues.append(
            _warning(
                "PROGRAM_OUTSIDE_COMPUTING_SCOPE",
                "program code is outside the configured computing-project scope",
                "program_code",
                program_code,
            )
        )

    official_source = values.get("official_source")
    if official_source is None:
        issues.append(
            _warning(
                "MISSING_SOURCE_REFERENCE",
                "record has no source reference and cannot be independently audited",
                "official_source",
            )
        )
    if official_source == "同上":
        issues.append(
            _warning(
                "SOURCE_NOT_SELF_CONTAINED",
                "source must be independently traceable and cannot be '同上'",
                "official_source",
                official_source,
            )
        )
    if official_source and "http://" not in official_source and "https://" not in official_source:
        issues.append(
            _info(
                "SOURCE_URL_MISSING",
                "source text has no directly traceable URL",
                "official_source",
                official_source,
            )
        )

    observation = CatalogObservation(
        school=school,
        college=college,
        program_code=program_code,
        program_name=values.get("program_name"),
        direction=values.get("direction"),
        campus=values.get("campus"),
        training_location=values.get("training_location"),
        study_mode=values.get("full_time_or_part_time"),
        training_type_raw=values.get("training_type"),
        admission_type=admission_type,
        degree_type=degree_type,
        training_arrangement=training_arrangement,
        admission_year=admission_year,
        strict_claim=strict_claim,
        strict_status=evidence_status,
        strict_status_raw=values.get("is_strict_22408"),
        total_plan=parsed_integers["total_plan"],
        recommendation_actual=parsed_integers["recommendation_actual"],
        special_plan=parsed_integers["special_plan"],
        effective_general_exam_quota=parsed_integers["effective_general_exam_quota"],
        retest_cutoff=parsed_decimals["retest_cutoff"],
        retest_count=parsed_integers["retest_count"],
        general_exam_admit_count=parsed_integers["general_exam_admit_count"],
        admit_initial_min=parsed_decimals["admit_initial_min"],
        admit_initial_median=parsed_decimals["admit_initial_median"],
        admit_initial_mean=parsed_decimals["admit_initial_mean"],
        initial_exam_weight=parsed_weights["initial_exam_weight"],
        retest_weight=parsed_weights["retest_weight"],
        machine_test_weight=parsed_weights["machine_test_weight"],
        machine_test_elimination_line=parsed_decimals["machine_test_elimination_line"],
        tuition_per_year=parsed_decimals["tuition_per_year"],
        study_length_years=parsed_decimals["study_length"],
        first_choice_protection=first_choice_protection,
        evidence_grade=evidence_grade,
        source_level_raw=values.get("source_level"),
        official_source=official_source,
        retrieval_date=retrieval_date,
        notes=values.get("notes"),
        raw_values=values,
    )
    _validate_cross_field_rules(observation, issues)
    return NormalizedRow(raw_row=raw_row, observation=observation, issues=tuple(issues))


def _validate_structure(
    raw_row: RawCatalogRow,
    issues: list[ValidationIssue],
) -> None:
    if raw_row.header != EXPECTED_CATALOG_HEADER:
        missing = sorted(set(EXPECTED_CATALOG_HEADER) - set(raw_row.header))
        unexpected = sorted(set(raw_row.header) - set(EXPECTED_CATALOG_HEADER))
        issues.append(
            _error(
                "HEADER_MISMATCH",
                f"catalog header mismatch; missing={missing}, unexpected={unexpected}",
            )
        )
    if len(set(raw_row.header)) != len(raw_row.header):
        issues.append(_error("DUPLICATE_HEADER", "catalog header contains duplicates"))
    if len(raw_row.cells) != len(raw_row.header):
        issues.append(
            _error(
                "ROW_WIDTH_MISMATCH",
                f"row has {len(raw_row.cells)} cells; expected {len(raw_row.header)}",
            )
        )


def _validate_cross_field_rules(
    observation: CatalogObservation,
    issues: list[ValidationIssue],
) -> None:
    if (
        observation.retest_count is not None
        and observation.general_exam_admit_count is not None
        and observation.general_exam_admit_count > observation.retest_count
    ):
        issues.append(
            _warning(
                "ADMIT_COUNT_EXCEEDS_RETEST_COUNT",
                "general-exam admits exceed retest participants",
                "general_exam_admit_count",
                str(observation.general_exam_admit_count),
            )
        )

    if (
        observation.retest_cutoff is not None
        and observation.admit_initial_min is not None
        and observation.admit_initial_min < observation.retest_cutoff
    ):
        issues.append(
            _warning(
                "ADMIT_SCORE_BELOW_RETEST_CUTOFF",
                "admitted initial-exam minimum is below the recorded retest cutoff",
                "admit_initial_min",
                str(observation.admit_initial_min),
            )
        )

    if (
        observation.admit_initial_min is not None
        and observation.admit_initial_mean is not None
        and observation.admit_initial_mean < observation.admit_initial_min
    ):
        issues.append(
            _error(
                "MEAN_SCORE_BELOW_MINIMUM",
                "admitted mean cannot be below admitted minimum",
                "admit_initial_mean",
                str(observation.admit_initial_mean),
            )
        )

    if (
        observation.initial_exam_weight is not None
        and observation.retest_weight is not None
        and abs(
            observation.initial_exam_weight + observation.retest_weight - 1.0
        )
        > 0.02
    ):
        issues.append(
            _warning(
                "WEIGHT_SUM_MISMATCH",
                "initial-exam and retest weights do not sum to 100%",
            )
        )


def _parse_integer(
    field_name: str,
    raw_value: str | None,
    issues: list[ValidationIssue],
) -> int | None:
    if raw_value is None:
        return None
    if not _INTEGER_PATTERN.fullmatch(raw_value):
        issues.append(
            _warning(
                "NON_ATOMIC_INTEGER",
                "compound or non-integer value was preserved but not coerced",
                field_name,
                raw_value,
            )
        )
        return None
    parsed = int(raw_value)
    if parsed < 0:
        issues.append(_error("NEGATIVE_COUNT", "count cannot be negative", field_name, raw_value))
        return None
    return parsed


def _parse_decimal(
    field_name: str,
    raw_value: str | None,
    issues: list[ValidationIssue],
) -> float | None:
    if raw_value is None:
        return None
    if not _DECIMAL_PATTERN.fullmatch(raw_value):
        issues.append(
            _warning(
                "NON_ATOMIC_DECIMAL",
                "compound numeric value was preserved but not coerced",
                field_name,
                raw_value,
            )
        )
        return None
    parsed = float(raw_value)
    if parsed < 0:
        issues.append(_error("NEGATIVE_VALUE", "value cannot be negative", field_name, raw_value))
        return None
    return parsed


def _parse_weight(
    field_name: str,
    raw_value: str | None,
    issues: list[ValidationIssue],
) -> float | None:
    if raw_value is None:
        return None
    cleaned = raw_value[:-1] if raw_value.endswith("%") else raw_value
    if not _DECIMAL_PATTERN.fullmatch(cleaned):
        issues.append(
            _warning(
                "NON_ATOMIC_WEIGHT",
                "compound weight was preserved but not coerced",
                field_name,
                raw_value,
            )
        )
        return None
    parsed = float(cleaned)
    if raw_value.endswith("%") or 1 < parsed <= 100:
        parsed /= 100
    if not 0 <= parsed <= 1:
        issues.append(_error("WEIGHT_OUT_OF_RANGE", "weight must be between 0 and 1", field_name, raw_value))
        return None
    return parsed


def _parse_boolean(
    field_name: str,
    raw_value: str | None,
    issues: list[ValidationIssue],
) -> bool | None:
    if raw_value is None:
        return None
    normalized = raw_value.casefold()
    if normalized in {"yes", "true", "是", "保护"}:
        return True
    if normalized in {"no", "false", "否", "不保护"}:
        return False
    issues.append(
        _warning(
            "AMBIGUOUS_BOOLEAN",
            "boolean value contains qualifiers and was not guessed",
            field_name,
            raw_value,
        )
    )
    return None


def _parse_year(raw_value: str | None, issues: list[ValidationIssue]) -> int | None:
    if raw_value is None:
        issues.append(_warning("MISSING_YEAR", "admission year is missing", "year"))
        return None
    if not re.fullmatch(r"20\d{2}", raw_value):
        issues.append(_warning("INVALID_YEAR", "year must be four digits", "year", raw_value))
        return None
    return int(raw_value)


def _parse_date(raw_value: str | None, issues: list[ValidationIssue]) -> date | None:
    if raw_value is None:
        return None
    for date_format in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw_value, date_format).date()
        except ValueError:
            continue
    issues.append(
        _warning(
            "INVALID_RETRIEVAL_DATE",
            "retrieval date is not an accepted date format",
            "retrieval_date",
            raw_value,
        )
    )
    return None


def _normalize_strict_claim(raw_value: str | None) -> Strict22408Claim:
    if raw_value is None:
        return Strict22408Claim.UNKNOWN
    normalized = raw_value.casefold()
    negative_tokens = ("no", "否", "非22408", "英语一", "数学一", "自命题", "11408")
    if any(token in normalized for token in negative_tokens):
        return Strict22408Claim.NO
    positive_tokens = ("yes", "是", "22408")
    if any(token in normalized for token in positive_tokens):
        return Strict22408Claim.YES
    return Strict22408Claim.UNKNOWN


def _derive_imported_evidence_status(
    claim: Strict22408Claim,
    raw_claim: str | None,
    evidence_grade: EvidenceGrade,
    admission_year: int | None,
    notes: str | None,
) -> Strict22408Status:
    normalized = f"{raw_claim or ''} {notes or ''}".casefold()
    if "冲突" in normalized:
        return Strict22408Status.CONFLICT
    if claim is Strict22408Claim.YES and evidence_grade in {
        EvidenceGrade.SECONDARY,
        EvidenceGrade.TERTIARY,
    }:
        return Strict22408Status.SECONDARY_ONLY
    if (
        claim is Strict22408Claim.YES
        and evidence_grade in {EvidenceGrade.OFFICIAL, EvidenceGrade.OFFICIAL_MIXED}
        and admission_year == 2027
        and any(token in normalized for token in ("待", "观察", "目录", "最终"))
    ):
        return Strict22408Status.OFFICIAL_PENDING_CATALOG
    return Strict22408Status.UNVERIFIED


def _normalize_evidence_grade(raw_value: str | None) -> EvidenceGrade:
    if raw_value is None or raw_value == "同上":
        return EvidenceGrade.UNKNOWN
    normalized = raw_value.casefold()
    upper_value = raw_value.upper()
    has_a = re.search(r"(^|[^A-Z])A($|[^A-Z])", upper_value) is not None
    has_b = re.search(r"(^|[^A-Z])B($|[^A-Z])", upper_value) is not None
    has_c = re.search(r"(^|[^A-Z])C($|[^A-Z])", upper_value) is not None
    if ("一级" in normalized and "二级" in normalized) or (has_a and has_b):
        return EvidenceGrade.OFFICIAL_MIXED
    if "一级" in normalized or has_a or "官方" in normalized:
        return EvidenceGrade.OFFICIAL
    if "二级" in normalized or has_b:
        return EvidenceGrade.SECONDARY
    if "三级" in normalized or has_c:
        return EvidenceGrade.TERTIARY
    return EvidenceGrade.UNKNOWN


def _split_training_type(
    raw_value: str | None,
    issues: list[ValidationIssue],
) -> tuple[str | None, str | None, str | None]:
    if raw_value is None:
        return None, None, None
    if raw_value == "统考":
        return "统考", None, None
    if raw_value == "统考(中外双学位)":
        return "统考", None, "中外双学位"
    if raw_value == "统考(联合培养)":
        return "统考", None, "联合培养"
    if raw_value in {"专硕", "专业学位"}:
        return None, "专业学位", None
    issues.append(
        _info(
            "TRAINING_TYPE_UNCLASSIFIED",
            "training_type mixes several business dimensions and was preserved as raw text",
            "training_type",
            raw_value,
        )
    )
    return None, None, None


def _apply_known_legacy_repair(
    raw_row: RawCatalogRow,
) -> tuple[dict[str, str], ValidationIssue | None]:
    values = dict(raw_row.values)
    if not (
        raw_row.archive_member.endswith("22408_db_A5.csv")
        and raw_row.row_number in {38, 39, 40, 41}
    ):
        return values, None

    repaired = dict(values)
    repaired["notes"] = values.get("official_source", "")
    repaired["official_source"] = values.get("source_level", "")
    repaired["source_level"] = values.get("first_choice_protection", "")
    repaired["first_choice_protection"] = values.get("study_length", "")
    repaired["study_length"] = values.get("tuition_per_year", "")
    repaired["tuition_per_year"] = values.get("machine_test_elimination_line", "")
    repaired["machine_test_elimination_line"] = values.get("machine_test_weight", "")
    repaired["machine_test_weight"] = values.get("retest_weight", "")
    repaired["retest_weight"] = values.get("initial_exam_weight", "")
    repaired["initial_exam_weight"] = values.get("admit_initial_mean", "")
    repaired["admit_initial_mean"] = ""
    return repaired, _info(
        "KNOWN_LEGACY_FIELD_SHIFT_REPAIRED",
        "A5 row 38-41 semantic shift was repaired in the normalized shadow only; raw cells remain immutable",
    )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = unicodedata.normalize("NFKC", value).strip()
    return cleaned or None


def _info(
    code: str,
    message: str,
    field_name: str | None = None,
    raw_value: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(code, IssueSeverity.INFO, message, field_name, raw_value)


def _warning(
    code: str,
    message: str,
    field_name: str | None = None,
    raw_value: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(code, IssueSeverity.WARNING, message, field_name, raw_value)


def _error(
    code: str,
    message: str,
    field_name: str | None = None,
    raw_value: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(code, IssueSeverity.ERROR, message, field_name, raw_value)
