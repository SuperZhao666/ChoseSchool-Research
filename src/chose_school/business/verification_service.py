from __future__ import annotations

import re

from chose_school.business.ports import SubjectVerificationStore
from chose_school.domain.enums import Strict22408Status
from chose_school.domain.evidence_rules import validate_catalog_verification_evidence
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import Settings, SubjectVerificationInput


_SUBJECT_CODE_PATTERN = re.compile(r"^\d{3}$")


class SubjectVerificationService:
    def __init__(
        self,
        store: SubjectVerificationStore,
        settings: Settings,
    ) -> None:
        self._store = store
        self._settings = settings

    def verify(
        self,
        verification: SubjectVerificationInput,
        trace_id: str,
    ) -> tuple[int, Strict22408Status]:
        subject_codes = (
            verification.politics_code,
            verification.english_code,
            verification.math_code,
            verification.professional_code,
        )
        if any(not _SUBJECT_CODE_PATTERN.fullmatch(code) for code in subject_codes):
            raise ValidationError(
                "INVALID_SUBJECT_CODE",
                "every subject code must contain exactly three digits",
            )
        if not verification.source_url.startswith(("http://", "https://")):
            raise ValidationError(
                "INVALID_SOURCE_URL",
                "official verification requires a traceable HTTP(S) source URL",
            )
        if not (verification.source_institution or "").strip():
            raise ValidationError(
                "SOURCE_INSTITUTION_REQUIRED",
                "official catalog verification requires the source institution",
            )
        validate_catalog_verification_evidence(
            verification.source_document_type,
            verification.source_content_sha256,
            verification.applicable_year,
        )

        expected = (
            self._settings.strict_politics_code,
            self._settings.strict_english_code,
            self._settings.strict_math_code,
            self._settings.strict_professional_code,
        )
        derived_status = (
            Strict22408Status.OFFICIAL_CONFIRMED
            if subject_codes == expected
            else Strict22408Status.OFFICIAL_NON_STRICT
        )
        verification_id = self._store.add_subject_verification(
            verification,
            derived_status,
            trace_id,
        )
        return verification_id, derived_status
