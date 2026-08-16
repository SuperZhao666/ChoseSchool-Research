from __future__ import annotations

import re

from chose_school.domain.enums import EvidenceDocumentType, EvidenceGrade
from chose_school.domain.errors import ValidationError


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
OFFICIAL_GRADES = {EvidenceGrade.OFFICIAL, EvidenceGrade.OFFICIAL_MIXED}
OFFICIAL_DOCUMENT_TYPES = {
    EvidenceDocumentType.OFFICIAL_CATALOG,
    EvidenceDocumentType.OFFICIAL_NOTICE,
    EvidenceDocumentType.RETEST_POLICY,
    EvidenceDocumentType.RETEST_LIST,
    EvidenceDocumentType.ADMISSION_LIST,
    EvidenceDocumentType.FEE_NOTICE,
    EvidenceDocumentType.OTHER_OFFICIAL,
}


def validate_evidence_metadata(
    evidence_grade: EvidenceGrade,
    document_type: EvidenceDocumentType,
    content_sha256: str | None,
    applicable_year: int,
) -> None:
    if not 2000 <= applicable_year <= 2100:
        raise ValidationError(
            "INVALID_APPLICABLE_YEAR",
            "evidence applicable year must be between 2000 and 2100",
            {"applicable_year": applicable_year},
        )
    if evidence_grade in OFFICIAL_GRADES:
        _validate_official_evidence(document_type, content_sha256)
    elif content_sha256 is not None and not _SHA256_PATTERN.fullmatch(content_sha256):
        _raise_invalid_hash(content_sha256)


def validate_catalog_verification_evidence(
    document_type: EvidenceDocumentType,
    content_sha256: str,
    applicable_year: int,
) -> None:
    validate_evidence_metadata(
        EvidenceGrade.OFFICIAL,
        document_type,
        content_sha256,
        applicable_year,
    )
    if document_type is not EvidenceDocumentType.OFFICIAL_CATALOG:
        raise ValidationError(
            "CATALOG_REQUIRED",
            "strict 22408 confirmation requires an official catalog document",
            {"document_type": document_type.value},
        )


def _validate_official_evidence(
    document_type: EvidenceDocumentType,
    content_sha256: str | None,
) -> None:
    if document_type not in OFFICIAL_DOCUMENT_TYPES:
        raise ValidationError(
            "INVALID_OFFICIAL_DOCUMENT_TYPE",
            "official evidence must use an official document type",
            {"document_type": document_type.value},
        )
    if content_sha256 is None or not _SHA256_PATTERN.fullmatch(content_sha256):
        _raise_invalid_hash(content_sha256)


def _raise_invalid_hash(content_sha256: str | None) -> None:
    raise ValidationError(
        "INVALID_SOURCE_SHA256",
        "evidence content SHA-256 must contain exactly 64 hexadecimal characters",
        {"content_sha256": content_sha256},
    )
