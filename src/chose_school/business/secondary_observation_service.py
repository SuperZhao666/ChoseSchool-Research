from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from datetime import date
from urllib.parse import urlsplit

from chose_school.business.secondary_observation_port import (
    SecondaryProjectObservationStore,
)
from chose_school.domain.enums import (
    EvidenceDocumentType,
    EvidenceGrade,
    Strict22408Claim,
    Strict22408Status,
)
from chose_school.domain.evidence_rules import validate_evidence_metadata
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import (
    SecondaryProjectObservationInput,
    SecondaryProjectObservationResult,
    Settings,
)


_PROGRAM_CODE_PATTERN = re.compile(r"^\d{6}$")
_SUBJECT_CODE_PATTERN = re.compile(r"^\d{3}$")


class SecondaryObservationService:
    """Validate a secondary-source interpretation without granting official status."""

    def __init__(
        self,
        store: SecondaryProjectObservationStore,
        settings: Settings,
    ) -> None:
        self._store = store
        self._settings = settings

    def add_observation(
        self,
        observation: SecondaryProjectObservationInput,
        trace_id: str,
    ) -> SecondaryProjectObservationResult:
        normalized = _normalize_observation(observation)
        _validate_trace_id(trace_id)
        _validate_project_identity(normalized)
        _validate_source(normalized)
        strict_claim, derived_status = _derive_secondary_status(
            normalized,
            self._settings,
        )
        return self._store.add_secondary_observation(
            normalized,
            strict_claim,
            derived_status,
            trace_id.strip(),
        )


def _normalize_observation(
    observation: SecondaryProjectObservationInput,
) -> SecondaryProjectObservationInput:
    return replace(
        observation,
        school=_required_identity_text(observation.school),
        college=_required_identity_text(observation.college),
        program_code=_required_identity_text(observation.program_code),
        program_name=_required_identity_text(observation.program_name),
        source_title=_required_source_text(observation.source_title),
        source_url=_required_source_text(observation.source_url),
        source_institution=_required_source_text(observation.source_institution),
        source_content_sha256=_required_source_text(
            observation.source_content_sha256
        ).lower(),
        source_excerpt=_required_source_text(observation.source_excerpt),
        project_identity_basis=_required_source_text(
            observation.project_identity_basis
        ),
        politics_code=_optional_identity_text(observation.politics_code),
        english_code=_optional_identity_text(observation.english_code),
        math_code=_optional_identity_text(observation.math_code),
        professional_code=_optional_identity_text(observation.professional_code),
        direction=_optional_identity_text(observation.direction),
        campus=_optional_identity_text(observation.campus),
        training_location=_optional_identity_text(observation.training_location),
        study_mode=_optional_identity_text(observation.study_mode),
        training_type_raw=_optional_identity_text(observation.training_type_raw),
        admission_type=_optional_identity_text(observation.admission_type),
        degree_type=_optional_identity_text(observation.degree_type),
        training_arrangement=_optional_identity_text(
            observation.training_arrangement
        ),
        note=_optional_source_text(observation.note),
    )


def _validate_trace_id(trace_id: str) -> None:
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ValidationError(
            "TRACE_ID_REQUIRED",
            "secondary observation writes require a non-empty TraceId",
        )


def _validate_project_identity(
    observation: SecondaryProjectObservationInput,
) -> None:
    required_text = {
        "school": observation.school,
        "college": observation.college,
        "program_code": observation.program_code,
        "program_name": observation.program_name,
    }
    empty_fields = [name for name, value in required_text.items() if not value]
    if empty_fields:
        raise ValidationError(
            "EMPTY_SECONDARY_OBSERVATION_FIELD",
            "secondary project identity fields cannot be empty",
            {"fields": empty_fields},
        )
    if not _PROGRAM_CODE_PATTERN.fullmatch(observation.program_code):
        raise ValidationError(
            "INVALID_PROGRAM_CODE",
            "program_code must contain exactly six digits",
        )
    if observation.admission_year != observation.applicable_year:
        raise ValidationError(
            "EVIDENCE_YEAR_MISMATCH",
            "evidence applicable year must equal the observation admission year",
            {
                "observation_year": observation.admission_year,
                "applicable_year": observation.applicable_year,
            },
        )


def _validate_source(observation: SecondaryProjectObservationInput) -> None:
    required_text = {
        "source_title": observation.source_title,
        "source_url": observation.source_url,
        "source_institution": observation.source_institution,
        "source_content_sha256": observation.source_content_sha256,
        "source_excerpt": observation.source_excerpt,
        "project_identity_basis": observation.project_identity_basis,
    }
    empty_fields = [name for name, value in required_text.items() if not value]
    if empty_fields:
        raise ValidationError(
            "SECONDARY_SOURCE_METADATA_REQUIRED",
            "secondary source metadata and interpretation evidence are required",
            {"fields": empty_fields},
        )
    parsed_url = urlsplit(observation.source_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValidationError(
            "INVALID_SOURCE_URL",
            "secondary observation requires a traceable HTTP(S) source URL",
        )
    validate_evidence_metadata(
        EvidenceGrade.SECONDARY,
        EvidenceDocumentType.SECONDARY_SUMMARY,
        observation.source_content_sha256,
        observation.applicable_year,
    )
    if not isinstance(observation.published_date, date):
        raise ValidationError(
            "PUBLISHED_DATE_REQUIRED",
            "secondary observation requires a published date",
        )
    if not isinstance(observation.retrieved_date, date):
        raise ValidationError(
            "RETRIEVED_DATE_REQUIRED",
            "secondary observation requires a retrieved date",
        )
    if observation.published_date > observation.retrieved_date:
        raise ValidationError(
            "SOURCE_DATE_ORDER_INVALID",
            "published date cannot be later than retrieved date",
            {
                "published_date": observation.published_date.isoformat(),
                "retrieved_date": observation.retrieved_date.isoformat(),
            },
        )


def _derive_secondary_status(
    observation: SecondaryProjectObservationInput,
    settings: Settings,
) -> tuple[Strict22408Claim, Strict22408Status]:
    subject_codes = (
        observation.politics_code,
        observation.english_code,
        observation.math_code,
        observation.professional_code,
    )
    supplied_count = sum(code is not None for code in subject_codes)
    if supplied_count == 0:
        return Strict22408Claim.UNKNOWN, Strict22408Status.UNVERIFIED
    if supplied_count != len(subject_codes):
        raise ValidationError(
            "PARTIAL_SECONDARY_SUBJECT_CONTRACT",
            "secondary subject codes must provide all four codes or none",
            {"supplied_count": supplied_count},
        )
    if any(not _SUBJECT_CODE_PATTERN.fullmatch(code or "") for code in subject_codes):
        raise ValidationError(
            "INVALID_SUBJECT_CODE",
            "every supplied subject code must contain exactly three digits",
        )
    expected = (
        settings.strict_politics_code,
        settings.strict_english_code,
        settings.strict_math_code,
        settings.strict_professional_code,
    )
    strict_claim = (
        Strict22408Claim.YES
        if subject_codes == expected
        else Strict22408Claim.NO
    )
    return strict_claim, Strict22408Status.SECONDARY_ONLY


def _required_identity_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFKC", value).strip()


def _optional_identity_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _required_identity_text(value)
    return normalized or None


def _required_source_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _optional_source_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _required_source_text(value)
    return normalized or None
