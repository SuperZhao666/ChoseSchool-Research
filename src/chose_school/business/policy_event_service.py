from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from typing import Any, Mapping, Sequence

from chose_school.business.ports import PolicyEventStore
from chose_school.domain.enums import (
    EvidenceDocumentType,
    EvidenceGrade,
    PolicyEventType,
)
from chose_school.domain.errors import ValidationError
from chose_school.domain.evidence_rules import validate_evidence_metadata
from chose_school.domain.models import (
    PolicyEventAddResult,
    PolicyEventFilter,
    PolicyEventInput,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MIN_YEAR = 2000
_MAX_YEAR = 2100
_MAX_SCOPE_LENGTH = 1000
_MAX_TITLE_LENGTH = 500
_MAX_DESCRIPTION_LENGTH = 4000


class PolicyEventService:
    """Records official notices without converting them into catalog facts."""

    def __init__(self, store: PolicyEventStore) -> None:
        self._store = store

    def add_event(
        self,
        event: PolicyEventInput,
        trace_id: str,
    ) -> PolicyEventAddResult:
        normalized_trace_id = trace_id.strip()
        if not normalized_trace_id:
            raise ValidationError("TRACE_ID_REQUIRED", "政策事件写入必须具有TraceId")
        normalized = _normalize_event(event)
        _validate_event(normalized)
        return self._store.add_policy_event(normalized, normalized_trace_id)

    def list_events(
        self,
        event_filter: PolicyEventFilter,
    ) -> Sequence[Mapping[str, Any]]:
        if not 1 <= event_filter.limit <= 1000:
            raise ValidationError(
                "INVALID_QUERY_LIMIT",
                "政策事件查询limit必须位于1到1000之间",
                {"limit": event_filter.limit},
            )
        if event_filter.effective_year is not None:
            _validate_year(event_filter.effective_year)
        normalized_school = _optional_text(event_filter.school_keyword)
        if event_filter.observation_id is not None and event_filter.observation_id <= 0:
            raise ValidationError(
                "INVALID_OBSERVATION_ID",
                "observation_id必须为正整数",
            )
        return self._store.list_policy_events(
            replace(event_filter, school_keyword=normalized_school)
        )


def _normalize_event(event: PolicyEventInput) -> PolicyEventInput:
    return replace(
        event,
        school=unicodedata.normalize("NFKC", event.school).strip(),
        scope_text=unicodedata.normalize("NFKC", event.scope_text).strip(),
        title=unicodedata.normalize("NFKC", event.title).strip(),
        description=unicodedata.normalize("NFKC", event.description).strip(),
        source_title=unicodedata.normalize("NFKC", event.source_title).strip(),
        source_url=event.source_url.strip(),
        source_institution=unicodedata.normalize(
            "NFKC", event.source_institution
        ).strip(),
        source_content_sha256=event.source_content_sha256.strip().lower(),
        note=_optional_text(event.note),
    )


def _validate_event(event: PolicyEventInput) -> None:
    _validate_required_text(event)
    _validate_lengths(event)
    _validate_year(event.effective_year)
    if event.effective_year != event.applicable_year:
        raise ValidationError(
            "EVIDENCE_YEAR_MISMATCH",
            "政策证据适用年度必须等于政策生效年度",
            {
                "effective_year": event.effective_year,
                "applicable_year": event.applicable_year,
            },
        )
    if event.event_type is not PolicyEventType.SUBJECT_ADJUSTMENT_NOTICE:
        raise ValidationError(
            "INVALID_POLICY_EVENT_TYPE",
            "当前仅支持初试科目调整公告",
            {"event_type": event.event_type.value},
        )
    if event.source_document_type is not EvidenceDocumentType.OFFICIAL_NOTICE:
        raise ValidationError(
            "POLICY_NOTICE_REQUIRED",
            "科目调整政策事件必须使用official_notice；正式目录请使用正式目录流程",
            {"document_type": event.source_document_type.value},
        )
    validate_evidence_metadata(
        EvidenceGrade.OFFICIAL,
        event.source_document_type,
        event.source_content_sha256,
        event.applicable_year,
    )
    if not _SHA256_PATTERN.fullmatch(event.source_content_sha256):
        raise ValidationError(
            "INVALID_SOURCE_SHA256",
            "政策证据内容SHA-256必须是64位小写十六进制",
        )
    if not event.source_url.startswith(("http://", "https://")):
        raise ValidationError(
            "INVALID_SOURCE_URL",
            "政策事件必须提供可追溯的HTTP(S)官方URL",
        )
    if not _institution_matches(event.school, event.source_institution):
        raise ValidationError(
            "SOURCE_INSTITUTION_MISMATCH",
            "政策来源机构必须与目标学校匹配",
            {
                "school": event.school,
                "source_institution": event.source_institution,
            },
        )
    if event.observation_id is not None and event.observation_id <= 0:
        raise ValidationError(
            "INVALID_OBSERVATION_ID",
            "observation_id必须为正整数",
        )
    if event.supersedes_event_id is not None and event.supersedes_event_id <= 0:
        raise ValidationError(
            "INVALID_SUPERSEDES_EVENT_ID",
            "supersedes_event_id必须为正整数",
        )


def _validate_required_text(event: PolicyEventInput) -> None:
    required = {
        "school": event.school,
        "scope_text": event.scope_text,
        "title": event.title,
        "description": event.description,
        "source_title": event.source_title,
        "source_url": event.source_url,
        "source_institution": event.source_institution,
    }
    empty = [name for name, value in required.items() if not value]
    if empty:
        if "source_institution" in empty:
            raise ValidationError(
                "SOURCE_INSTITUTION_REQUIRED",
                "政策事件必须提供来源机构",
            )
        raise ValidationError(
            "EMPTY_POLICY_EVENT_FIELD",
            "政策事件必填文本不得为空",
            {"fields": empty},
        )


def _validate_lengths(event: PolicyEventInput) -> None:
    limits = {
        "scope_text": (event.scope_text, _MAX_SCOPE_LENGTH),
        "title": (event.title, _MAX_TITLE_LENGTH),
        "description": (event.description, _MAX_DESCRIPTION_LENGTH),
    }
    exceeded = [name for name, (value, maximum) in limits.items() if len(value) > maximum]
    if exceeded:
        raise ValidationError(
            "POLICY_EVENT_TEXT_TOO_LONG",
            "政策事件文本超过允许长度",
            {"fields": exceeded},
        )


def _validate_year(year: int) -> None:
    if not _MIN_YEAR <= year <= _MAX_YEAR:
        raise ValidationError(
            "INVALID_APPLICABLE_YEAR",
            "政策适用年度必须位于2000到2100之间",
            {"year": year},
        )


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
    normalized = unicodedata.normalize("NFKC", value).strip()
    return normalized or None
