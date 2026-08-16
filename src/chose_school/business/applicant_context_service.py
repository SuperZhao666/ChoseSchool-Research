from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from chose_school.business.ports import ApplicantContextStore
from chose_school.domain.enums import ApplicantContextDimension
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.models import ApplicantContextEventInput, Settings


_MAX_SUBJECT_KEY_LENGTH = 120
_MAX_NOTE_LENGTH = 2000
_STUDY_PROGRESS_STATUSES = frozenset(
    {"not_started", "in_progress", "partial", "completed"}
)
_MEASUREMENT_STATUSES = frozenset({"not_measured", "measured"})
_CONSTRAINT_STATUSES = frozenset({"not_current_constraint", "active_constraint"})


class ApplicantContextService:
    """Append qualitative applicant context without manufacturing scores."""

    def __init__(self, store: ApplicantContextStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def add_context(self, event: ApplicantContextEventInput, trace_id: str) -> int:
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValidationError("TRACE_ID_REQUIRED", "追加个人现状必须提供TraceId")
        normalized = _normalize_context(event)
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        value_json = _canonicalize_value(normalized.value)
        return self._store.add_context_event(
            profile_id,
            normalized,
            value_json,
            trace_id,
        )

    def list_contexts(
        self,
        dimension: str | None = None,
        subject_key: str | None = None,
        include_history: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            return ()
        normalized_dimension = None
        if dimension:
            try:
                normalized_dimension = ApplicantContextDimension(dimension).value
            except ValueError as error:
                raise ValidationError(
                    "INVALID_CONTEXT_DIMENSION",
                    f"不支持的个人现状维度：{dimension}",
                ) from error
        normalized_subject = None
        if subject_key is not None:
            normalized_subject = subject_key.strip()
            if not normalized_subject:
                raise ValidationError("INVALID_CONTEXT_SUBJECT", "个人现状对象不能为空")
        return self._store.list_context_events(
            profile_id,
            normalized_dimension,
            normalized_subject,
            include_history,
        )


def _normalize_context(event: ApplicantContextEventInput) -> ApplicantContextEventInput:
    subject_key = event.subject_key.strip()
    if not subject_key or len(subject_key) > _MAX_SUBJECT_KEY_LENGTH:
        raise ValidationError(
            "INVALID_CONTEXT_SUBJECT",
            "个人现状对象不能为空且不得超过120个字符",
        )
    try:
        value = dict(event.value)
    except (TypeError, ValueError) as error:
        raise ValidationError("INVALID_CONTEXT_VALUE", "个人现状值必须是JSON对象") from error
    if not value:
        raise ValidationError("INVALID_CONTEXT_VALUE", "个人现状值不得为空")
    if event.dimension is ApplicantContextDimension.STUDY_PROGRESS:
        _require_status(value, _STUDY_PROGRESS_STATUSES, "学习进度")
    elif event.dimension is ApplicantContextDimension.MEASUREMENT_STATUS:
        _require_status(value, _MEASUREMENT_STATUSES, "测量状态")
    elif event.dimension is ApplicantContextDimension.PERSONAL_CONSTRAINT:
        _require_status(value, _CONSTRAINT_STATUSES, "现实约束")
    note = event.note.strip() if event.note else None
    if note is not None and len(note) > _MAX_NOTE_LENGTH:
        raise ValidationError("INVALID_CONTEXT_NOTE", "个人现状说明不得超过2000个字符")
    return ApplicantContextEventInput(
        dimension=event.dimension,
        subject_key=subject_key,
        value=value,
        note=note or None,
    )


def _require_status(
    value: Mapping[str, Any],
    allowed: frozenset[str],
    label: str,
) -> None:
    status = value.get("status")
    if status not in allowed:
        raise ValidationError(
            "INVALID_CONTEXT_STATUS",
            f"{label}status不受支持",
            {"allowed": sorted(allowed), "status": status},
        )


def _canonicalize_value(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "INVALID_CONTEXT_VALUE",
            "个人现状value-json必须是可序列化的JSON对象",
        ) from error
