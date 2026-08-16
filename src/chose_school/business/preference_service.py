from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from chose_school.business.ports import PreferenceStore
from chose_school.domain.enums import PreferenceAcceptanceLevel, PreferenceDimension
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.models import PreferenceEventInput, PreferenceReadinessSummary
from chose_school.domain.models import Settings


_PROGRAM_CODE_PATTERN = re.compile(r"^[0-9]{6}$")
_RETEST_FORMAT_KEYS = frozenset(
    {
        "machine_test",
        "written_test",
        "pure_interview",
        "theory_closed_book",
        "high_weight_interview",
    }
)
_JOINT_TRAINING_KEYS = frozenset(
    {"offsite", "enterprise", "international", "unknown_assignment"}
)
_SCHOOL_TIER_KEYS = frozenset(
    {
        "985_priority_211_hedge",
        "985_only",
        "211_floor",
        "non_211_acceptable",
    }
)
_ADMISSION_FAIRNESS_KEYS = frozenset(
    {
        "ordinary_undergraduate_nondiscrimination",
        "evidence_backed_fair_reputation",
    }
)
_TUITION_BASES = frozenset({"annual", "total"})
_MAX_SUBJECT_KEY_LENGTH = 120
_PREFERENCE_CONTRACT_VERSION = "personal-selection-preference-v2"
_REGION_SCOPE_KEY = "actual_training_scope"
_REGION_SCOPE_MODES = frozenset({"near_region", "mainland", "custom"})
_PROGRAM_CODE_SCOPE_KEY = "any_other_eligible_code"
_PROGRAM_CODE_KEYS = (
    "085404",
    "085405",
    "085410",
    "085411",
    "085412",
    "085400",
    "145200",
)
_REQUIRED_PREFERENCE_IDENTITIES = (
    (PreferenceDimension.REGION.value, _REGION_SCOPE_KEY),
    *(
        (PreferenceDimension.JOINT_TRAINING.value, subject_key)
        for subject_key in sorted(_JOINT_TRAINING_KEYS)
    ),
    (PreferenceDimension.TUITION_CEILING.value, "default"),
    *(
        (PreferenceDimension.PROGRAM_CODE.value, subject_key)
        for subject_key in _PROGRAM_CODE_KEYS
    ),
    (PreferenceDimension.PROGRAM_CODE.value, _PROGRAM_CODE_SCOPE_KEY),
    (PreferenceDimension.SCHOOL_TIER_REQUIREMENT.value, "211_floor"),
    (
        PreferenceDimension.SCHOOL_TIER_REQUIREMENT.value,
        "non_211_acceptable",
    ),
    *(
        (PreferenceDimension.RETEST_FORMAT.value, subject_key)
        for subject_key in sorted(_RETEST_FORMAT_KEYS)
    ),
    *(
        (PreferenceDimension.ADMISSION_FAIRNESS.value, subject_key)
        for subject_key in sorted(_ADMISSION_FAIRNESS_KEYS)
    ),
)
_REQUIRED_PREFERENCE_IDENTITY_SET = frozenset(_REQUIRED_PREFERENCE_IDENTITIES)


class PreferenceService:
    """Append and query explicit personal selection boundaries."""

    def __init__(self, store: PreferenceStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def add_preference(
        self,
        preference: PreferenceEventInput,
        trace_id: str,
    ) -> int:
        if not trace_id.strip():
            raise ValidationError(
                "TRACE_ID_REQUIRED",
                "追加个人偏好必须提供TraceId",
            )
        normalized = self._normalize(preference)
        profile_id = self._require_profile_id()
        canonical_value_json = _canonicalize_value(normalized.value)
        return self._store.add_preference_event(
            profile_id,
            normalized,
            canonical_value_json,
            trace_id,
        )

    def list_preferences(
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
                normalized_dimension = PreferenceDimension(dimension).value
            except ValueError as error:
                raise ValidationError(
                    "INVALID_PREFERENCE_DIMENSION",
                    f"不支持的偏好维度：{dimension}",
                ) from error
        normalized_subject = None
        if subject_key is not None:
            normalized_subject = subject_key.strip()
            if not normalized_subject:
                raise ValidationError(
                    "INVALID_PREFERENCE_SUBJECT",
                    "偏好对象不能为空",
                )
        return self._store.list_preferences(
            profile_id,
            normalized_dimension,
            normalized_subject,
            include_history,
        )

    def summarize_readiness(self) -> PreferenceReadinessSummary:
        return summarize_preference_readiness(tuple(self.list_preferences()))

    def _require_profile_id(self) -> int:
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        return profile_id

    def _normalize(self, preference: PreferenceEventInput) -> PreferenceEventInput:
        subject_key = preference.subject_key.strip()
        if not subject_key or len(subject_key) > _MAX_SUBJECT_KEY_LENGTH:
            raise ValidationError(
                "INVALID_PREFERENCE_SUBJECT",
                "偏好对象不能为空且不得超过120个字符",
                {"dimension": preference.dimension.value},
            )

        _validate_subject_key(preference.dimension, subject_key)
        try:
            value = dict(preference.value)
        except (TypeError, ValueError) as error:
            raise ValidationError(
                "INVALID_PREFERENCE_VALUE",
                "个人偏好值必须是JSON对象",
            ) from error
        if preference.dimension is PreferenceDimension.TUITION_CEILING:
            _validate_tuition_ceiling(value)

        note = preference.note.strip() if preference.note else None
        return PreferenceEventInput(
            dimension=preference.dimension,
            subject_key=subject_key,
            acceptance_level=preference.acceptance_level,
            value=value,
            note=note or None,
        )


def summarize_preference_readiness(
    current_preferences: Sequence[Mapping[str, Any]],
) -> PreferenceReadinessSummary:
    current_by_identity = {
        (str(row["dimension"]), str(row["subject_key"])): row
        for row in current_preferences
    }
    missing: list[str] = []
    unknown: list[str] = []
    unsupported: list[str] = []
    answered_count = 0
    for identity in _REQUIRED_PREFERENCE_IDENTITIES:
        identity_label = _preference_identity_label(identity)
        row = current_by_identity.get(identity)
        if row is None:
            missing.append(identity_label)
            continue
        if row["acceptance_level"] == PreferenceAcceptanceLevel.UNKNOWN.value:
            unknown.append(identity_label)
            continue
        answered_count += 1
        unsupported_reason = _required_answer_unsupported_reason(identity, row)
        if unsupported_reason is not None:
            unsupported.append(f"{identity_label}:{unsupported_reason}")

    contradictions = _school_tier_contradictions(current_by_identity)
    ranking_preferences = tuple(
        _preference_identity_label(identity)
        for identity in sorted(current_by_identity)
        if identity not in _REQUIRED_PREFERENCE_IDENTITY_SET
    )
    is_complete = (
        answered_count == len(_REQUIRED_PREFERENCE_IDENTITIES)
        and not missing
        and not unknown
        and not unsupported
        and not contradictions
    )
    return PreferenceReadinessSummary(
        contract_version=_PREFERENCE_CONTRACT_VERSION,
        required_subject_count=len(_REQUIRED_PREFERENCE_IDENTITIES),
        answered_subject_count=answered_count,
        current_preference_event_count=len(current_preferences),
        is_preference_intake_complete=is_complete,
        missing_subjects=tuple(missing),
        unknown_subjects=tuple(unknown),
        contradictory_subjects=tuple(contradictions),
        unsupported_subjects=tuple(unsupported),
        ranking_preferences=ranking_preferences,
    )


def _validate_subject_key(dimension: PreferenceDimension, subject_key: str) -> None:
    if dimension is PreferenceDimension.PROGRAM_CODE:
        if (
            subject_key != _PROGRAM_CODE_SCOPE_KEY
            and not _PROGRAM_CODE_PATTERN.fullmatch(subject_key)
        ):
            raise ValidationError(
                "INVALID_PREFERENCE_PROGRAM_CODE",
                "专业代码偏好必须使用六位数字代码或any_other_eligible_code",
                {"subject_key": subject_key},
            )
        return

    allowed_by_dimension = {
        PreferenceDimension.RETEST_FORMAT: _RETEST_FORMAT_KEYS,
        PreferenceDimension.JOINT_TRAINING: _JOINT_TRAINING_KEYS,
        PreferenceDimension.SCHOOL_TIER_REQUIREMENT: _SCHOOL_TIER_KEYS,
        PreferenceDimension.ADMISSION_FAIRNESS: _ADMISSION_FAIRNESS_KEYS,
    }
    allowed = allowed_by_dimension.get(dimension)
    if allowed is not None and subject_key not in allowed:
        raise ValidationError(
            "INVALID_PREFERENCE_SUBJECT",
            f"不支持的{dimension.value}偏好对象：{subject_key}",
            {"allowed": sorted(allowed), "subject_key": subject_key},
        )


def _validate_tuition_ceiling(value: Mapping[str, Any]) -> None:
    mode = value.get("mode")
    if mode == "no_hard_cap":
        unexpected = sorted(set(value) - {"mode"})
        if unexpected:
            raise ValidationError(
                "INVALID_TUITION_CEILING",
                "无学费硬上限只需mode=no_hard_cap",
                {"unexpected_fields": unexpected},
            )
        return
    if mode not in (None, "cap"):
        raise ValidationError(
            "INVALID_TUITION_CEILING",
            "学费策略mode必须是cap或no_hard_cap",
            {"mode": mode},
        )
    amount = value.get("amount")
    basis = value.get("basis")
    currency = value.get("currency")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValidationError(
            "INVALID_TUITION_CEILING",
            "学费上限必须包含大于0的数值amount",
        )
    if basis not in _TUITION_BASES:
        raise ValidationError(
            "INVALID_TUITION_CEILING",
            "学费上限basis必须是annual或total",
            {"basis": basis},
        )
    if currency != "CNY":
        raise ValidationError(
            "INVALID_TUITION_CEILING",
            "学费上限currency当前只接受CNY",
            {"currency": currency},
        )


def _preference_identity_label(identity: tuple[str, str]) -> str:
    return f"{identity[0]}:{identity[1]}"


def _required_answer_unsupported_reason(
    identity: tuple[str, str],
    row: Mapping[str, Any],
) -> str | None:
    dimension, subject_key = identity
    acceptance_level = str(row["acceptance_level"])
    value = row.get("value")
    if not isinstance(value, Mapping):
        return "VALUE_MUST_BE_OBJECT"

    if dimension == PreferenceDimension.REGION.value:
        if acceptance_level != PreferenceAcceptanceLevel.ACCEPT.value:
            return "REGION_SCOPE_MUST_BE_ACCEPT"
        mode = value.get("mode")
        if mode not in _REGION_SCOPE_MODES:
            return "REGION_SCOPE_MODE_UNSUPPORTED"
        locations = value.get("locations")
        if mode == "custom":
            if (
                not isinstance(locations, list)
                or not locations
                or any(
                    not isinstance(location, str) or not location.strip()
                    for location in locations
                )
            ):
                return "CUSTOM_REGION_LOCATIONS_REQUIRED"
        elif locations is not None:
            return "REGION_SCOPE_LOCATIONS_UNEXPECTED"

    if dimension == PreferenceDimension.TUITION_CEILING.value:
        if subject_key != "default":
            return "TUITION_SUBJECT_UNSUPPORTED"
        if acceptance_level != PreferenceAcceptanceLevel.ACCEPT.value:
            return "TUITION_CEILING_MUST_BE_ACCEPT"
        if not _is_supported_tuition_value(value):
            return "TUITION_VALUE_UNSUPPORTED"

    if dimension == PreferenceDimension.ADMISSION_FAIRNESS.value:
        if acceptance_level != PreferenceAcceptanceLevel.ACCEPT.value:
            return "FAIRNESS_REQUIREMENT_MUST_BE_ACCEPT"

    if dimension == PreferenceDimension.SCHOOL_TIER_REQUIREMENT.value:
        if acceptance_level not in (
            PreferenceAcceptanceLevel.ACCEPT.value,
            PreferenceAcceptanceLevel.REJECT.value,
        ):
            return "SCHOOL_TIER_MUST_BE_ACCEPT_OR_REJECT"
    return None


def _is_supported_tuition_value(value: Mapping[str, Any]) -> bool:
    if value.get("mode") == "no_hard_cap":
        return set(value) == {"mode"}
    if value.get("mode") not in (None, "cap"):
        return False
    amount = value.get("amount")
    return (
        not isinstance(amount, bool)
        and isinstance(amount, (int, float))
        and amount > 0
        and value.get("basis") in _TUITION_BASES
        and value.get("currency") == "CNY"
    )


def _school_tier_contradictions(
    current_by_identity: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[str, ...]:
    dimension = PreferenceDimension.SCHOOL_TIER_REQUIREMENT.value
    floor_identity = (dimension, "211_floor")
    non_211_identity = (dimension, "non_211_acceptable")
    floor = current_by_identity.get(floor_identity)
    non_211 = current_by_identity.get(non_211_identity)
    if floor is None or non_211 is None:
        return ()
    levels = {
        str(floor["acceptance_level"]),
        str(non_211["acceptance_level"]),
    }
    if levels == {
        PreferenceAcceptanceLevel.ACCEPT.value,
        PreferenceAcceptanceLevel.REJECT.value,
    }:
        return ()
    return (
        "school_tier_requirement:211_floor"
        "|non_211_acceptable:MUST_BE_COMPLEMENTARY",
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
            "INVALID_PREFERENCE_VALUE",
            "偏好value-json必须是可序列化的JSON对象",
        ) from error
