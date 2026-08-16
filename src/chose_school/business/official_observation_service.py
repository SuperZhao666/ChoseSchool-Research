from __future__ import annotations

import re
from dataclasses import replace

from chose_school.business.ports import OfficialProjectObservationStore
from chose_school.domain.enums import Strict22408Status
from chose_school.domain.evidence_rules import validate_catalog_verification_evidence
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import (
    OfficialProjectObservationInput,
    OfficialProjectObservationResult,
    Settings,
)


_PROGRAM_CODE_PATTERN = re.compile(r"^\d{6}$")
_SUBJECT_CODE_PATTERN = re.compile(r"^\d{3}$")


class OfficialObservationService:
    def __init__(
        self,
        store: OfficialProjectObservationStore,
        settings: Settings,
    ) -> None:
        self._store = store
        self._settings = settings

    def add_observation(
        self,
        observation: OfficialProjectObservationInput,
        trace_id: str,
    ) -> OfficialProjectObservationResult:
        normalized = _normalize_observation(observation)
        _validate_identity(normalized)
        _validate_source(normalized)
        derived_status = _derive_status(normalized, self._settings)
        return self._store.add_official_observation(
            normalized,
            derived_status,
            trace_id,
        )


def _normalize_observation(
    observation: OfficialProjectObservationInput,
) -> OfficialProjectObservationInput:
    return replace(
        observation,
        school=observation.school.strip(),
        college=observation.college.strip(),
        program_code=observation.program_code.strip(),
        program_name=observation.program_name.strip(),
        politics_code=observation.politics_code.strip(),
        english_code=observation.english_code.strip(),
        math_code=observation.math_code.strip(),
        professional_code=observation.professional_code.strip(),
        source_title=observation.source_title.strip(),
        source_url=observation.source_url.strip(),
        source_institution=observation.source_institution.strip(),
        source_content_sha256=observation.source_content_sha256.lower(),
        direction=_optional_text(observation.direction),
        campus=_optional_text(observation.campus),
        training_location=_optional_text(observation.training_location),
        study_mode=_optional_text(observation.study_mode),
        training_type_raw=_optional_text(observation.training_type_raw),
        admission_type=_optional_text(observation.admission_type),
        degree_type=_optional_text(observation.degree_type),
        training_arrangement=_optional_text(observation.training_arrangement),
        note=_optional_text(observation.note),
    )


def _validate_identity(observation: OfficialProjectObservationInput) -> None:
    required_text = {
        "school": observation.school,
        "college": observation.college,
        "program_name": observation.program_name,
    }
    empty_fields = [name for name, value in required_text.items() if not value]
    if empty_fields:
        raise ValidationError(
            "EMPTY_OFFICIAL_OBSERVATION_FIELD",
            "official project identity fields cannot be empty",
            {"fields": empty_fields},
        )
    if not _PROGRAM_CODE_PATTERN.fullmatch(observation.program_code):
        raise ValidationError(
            "INVALID_PROGRAM_CODE",
            "program_code must contain exactly six digits",
        )
    subject_codes = (
        observation.politics_code,
        observation.english_code,
        observation.math_code,
        observation.professional_code,
    )
    if any(not _SUBJECT_CODE_PATTERN.fullmatch(code) for code in subject_codes):
        raise ValidationError(
            "INVALID_SUBJECT_CODE",
            "every subject code must contain exactly three digits",
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


def _validate_source(observation: OfficialProjectObservationInput) -> None:
    if not observation.source_title:
        raise ValidationError("EMPTY_SOURCE_TITLE", "source title is required")
    if not observation.source_url.startswith(("http://", "https://")):
        raise ValidationError(
            "INVALID_SOURCE_URL",
            "official observation requires a traceable HTTP(S) source URL",
        )
    if not observation.source_institution:
        raise ValidationError(
            "SOURCE_INSTITUTION_REQUIRED",
            "official observation requires the source institution",
        )
    if not _institution_matches(observation.school, observation.source_institution):
        raise ValidationError(
            "SOURCE_INSTITUTION_MISMATCH",
            "official catalog institution must match the observation school",
            {
                "school": observation.school,
                "source_institution": observation.source_institution,
            },
        )
    validate_catalog_verification_evidence(
        observation.source_document_type,
        observation.source_content_sha256,
        observation.applicable_year,
    )


def _derive_status(
    observation: OfficialProjectObservationInput,
    settings: Settings,
) -> Strict22408Status:
    subject_codes = (
        observation.politics_code,
        observation.english_code,
        observation.math_code,
        observation.professional_code,
    )
    expected = (
        settings.strict_politics_code,
        settings.strict_english_code,
        settings.strict_math_code,
        settings.strict_professional_code,
    )
    if subject_codes == expected:
        return Strict22408Status.OFFICIAL_CONFIRMED
    return Strict22408Status.OFFICIAL_NON_STRICT


def _institution_matches(school_name: str, institution: str) -> bool:
    normalized_school = _normalize_institution(school_name)
    normalized_institution = _normalize_institution(institution)
    return (
        normalized_school in normalized_institution
        or normalized_institution in normalized_school
    )


def _normalize_institution(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
