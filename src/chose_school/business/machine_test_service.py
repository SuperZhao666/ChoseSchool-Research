from __future__ import annotations

from dataclasses import replace
from math import isfinite
from typing import Any, Mapping, Sequence

from chose_school.business.ports import MachineTestStore
from chose_school.domain.enums import (
    MachineMeasurementStatus,
    MachineScoringMethod,
    MachineTestDifficulty,
)
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.models import (
    MachineAssessmentSummary,
    MachineComparisonGroup,
    MachineDurationAssessment,
    MachineTestAddResult,
    MachineTestInput,
    Settings,
)


_MIN_DURATION_MINUTES = 30
_MAX_DURATION_MINUTES = 360
_MAX_PROBLEM_COUNT = 100
_MAX_LANGUAGE_LENGTH = 60
_MAX_TEXT_LENGTH = 240


class MachineTestService:
    """Record and summarize non-comparable timed programming baselines."""

    def __init__(self, store: MachineTestStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings
        self._required_durations = _validate_required_durations(
            settings.required_machine_durations
        )

    def add_machine_test(
        self,
        machine_test: MachineTestInput,
        trace_id: str,
    ) -> MachineTestAddResult:
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValidationError(
                "TRACE_ID_REQUIRED",
                "记录机试基线必须提供TraceId",
            )
        normalized = _normalize_machine_test(machine_test)
        profile_id = self._require_profile_id()
        session_id = self._store.add_machine_test(profile_id, normalized, trace_id)
        return MachineTestAddResult(
            session_id=session_id,
            is_valid=_is_valid_measurement(normalized),
        )

    def list_sessions(
        self,
        duration_minutes: int | None = None,
        language: str | None = None,
        problem_count: int | None = None,
        valid_only: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        if duration_minutes is not None:
            _validate_duration(duration_minutes)
        normalized_language = None
        if language is not None:
            normalized_language = _normalize_required_text(
                language,
                "language",
                _MAX_LANGUAGE_LENGTH,
            )
        if problem_count is not None:
            _validate_integer_range(
                problem_count,
                "problem_count",
                1,
                _MAX_PROBLEM_COUNT,
            )
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            return ()
        return self._store.list_machine_tests(
            profile_id,
            duration_minutes,
            normalized_language,
            problem_count,
            valid_only,
        )

    def summarize(self) -> MachineAssessmentSummary:
        sessions = tuple(self.list_sessions())
        duration_results = tuple(
            _summarize_duration(duration, sessions)
            for duration in self._required_durations
        )
        valid_session_count = sum(bool(row["is_valid"]) for row in sessions)
        return MachineAssessmentSummary(
            total_session_count=len(sessions),
            valid_session_count=valid_session_count,
            is_duration_coverage_complete=all(
                result.status is MachineMeasurementStatus.VALID_MEASURED
                for result in duration_results
            ),
            required_durations=self._required_durations,
            durations=duration_results,
        )

    def _require_profile_id(self) -> int:
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        return profile_id


def _normalize_machine_test(machine_test: MachineTestInput) -> MachineTestInput:
    _validate_boolean_fields(machine_test)
    if not isinstance(machine_test.difficulty, MachineTestDifficulty):
        raise ValidationError(
            "INVALID_MACHINE_TEST_DIFFICULTY",
            "difficulty必须使用受支持的机试难度枚举",
        )
    if not isinstance(machine_test.scoring_method, MachineScoringMethod):
        raise ValidationError(
            "INVALID_MACHINE_SCORING_METHOD",
            "scoring_method必须使用受支持的计分方式枚举",
        )
    _validate_duration(machine_test.duration_minutes)
    _validate_integer_range(
        machine_test.problem_count,
        "problem_count",
        1,
        _MAX_PROBLEM_COUNT,
    )
    _validate_integer_range(
        machine_test.independently_solved_count,
        "independently_solved_count",
        0,
        machine_test.problem_count,
    )
    _validate_integer_range(machine_test.attempt_number, "attempt_number", 1, None)
    if machine_test.debugging_minutes is not None:
        _validate_integer_range(
            machine_test.debugging_minutes,
            "debugging_minutes",
            0,
            machine_test.duration_minutes,
        )
    _validate_score_contract(machine_test)

    first_solve_minutes = machine_test.first_solve_minutes
    if machine_test.independently_solved_count == 0:
        if first_solve_minutes is not None:
            raise ValidationError(
                "INVALID_FIRST_SOLVE_TIME",
                "独立通过题数为0时，首题通过分钟必须留空",
            )
    else:
        if first_solve_minutes is None:
            raise ValidationError(
                "INVALID_FIRST_SOLVE_TIME",
                "独立通过至少1题时，必须记录首题通过分钟",
            )
        _validate_integer_range(
            first_solve_minutes,
            "first_solve_minutes",
            1,
            machine_test.duration_minutes,
        )

    language = _normalize_required_text(
        machine_test.language,
        "language",
        _MAX_LANGUAGE_LENGTH,
    )
    environment = _normalize_required_text(
        machine_test.environment,
        "environment",
        _MAX_TEXT_LENGTH,
    )
    problem_source = _normalize_required_text(
        machine_test.problem_source,
        "problem_source",
        _MAX_TEXT_LENGTH,
    )
    is_valid = _is_valid_measurement(machine_test)
    invalid_reason = _normalize_optional_text(machine_test.invalid_reason)
    if is_valid and invalid_reason:
        raise ValidationError(
            "UNEXPECTED_INVALID_REASON",
            "有效机试样本不能同时填写invalid_reason；一般异常请写入notes",
        )
    if not is_valid and not invalid_reason:
        raise ValidationError(
            "MACHINE_TEST_INVALID_REASON_REQUIRED",
            "非首次见题、查资料、接受帮助、暂停计时或非严格限时时，必须填写invalid_reason",
        )

    return replace(
        machine_test,
        language=language,
        environment=environment,
        problem_source=problem_source,
        invalid_reason=invalid_reason,
        primary_blocker=_normalize_optional_text(machine_test.primary_blocker),
        notes=_normalize_optional_text(machine_test.notes),
    )


def _summarize_duration(
    duration_minutes: int,
    sessions: Sequence[Mapping[str, Any]],
) -> MachineDurationAssessment:
    matching = [
        row for row in sessions if int(row["duration_minutes"]) == duration_minutes
    ]
    valid = [row for row in matching if bool(row["is_valid"])]
    if valid:
        status = MachineMeasurementStatus.VALID_MEASURED
    elif matching:
        status = MachineMeasurementStatus.INVALID_ONLY
    else:
        status = MachineMeasurementStatus.NOT_MEASURED
    return MachineDurationAssessment(
        duration_minutes=duration_minutes,
        status=status,
        total_session_count=len(matching),
        valid_session_count=len(valid),
        comparison_groups=_build_comparison_groups(valid),
    )


def _build_comparison_groups(
    sessions: Sequence[Mapping[str, Any]],
) -> tuple[MachineComparisonGroup, ...]:
    grouped: dict[tuple[str, int, str, str, float | None], list[Mapping[str, Any]]] = {}
    for session in sessions:
        key = (
            str(session["language"]),
            int(session["problem_count"]),
            str(session["difficulty_label"]),
            str(session["scoring_method"]),
            _optional_float(session["maximum_score"]),
        )
        grouped.setdefault(key, []).append(session)

    ordered_keys = sorted(
        grouped,
        key=lambda key: (key[0], key[1], key[2], key[3], key[4] is None, key[4] or 0.0),
    )
    return tuple(
        MachineComparisonGroup(
            language=key[0],
            problem_count=key[1],
            difficulty_label=key[2],
            scoring_method=key[3],
            maximum_score=key[4],
            valid_session_count=len(grouped[key]),
            latest_valid_session=grouped[key][-1],
        )
        for key in ordered_keys
    )


def _is_valid_measurement(machine_test: MachineTestInput) -> bool:
    return (
        machine_test.first_exposure
        and not machine_test.consulted_materials
        and not machine_test.received_assistance
        and not machine_test.paused_timer
        and machine_test.strict_timed
    )


def _validate_boolean_fields(machine_test: MachineTestInput) -> None:
    for field_name in (
        "first_exposure",
        "consulted_materials",
        "received_assistance",
        "paused_timer",
        "strict_timed",
    ):
        if not isinstance(getattr(machine_test, field_name), bool):
            raise ValidationError(
                "INVALID_MACHINE_TEST_BOOLEAN",
                f"{field_name}必须是布尔值",
                {"field": field_name},
            )


def _validate_score_contract(machine_test: MachineTestInput) -> None:
    raw_score = machine_test.raw_score
    maximum_score = machine_test.maximum_score
    if (raw_score is None) != (maximum_score is None):
        raise ValidationError(
            "INCOMPLETE_MACHINE_TEST_SCORE",
            "raw_score与maximum_score必须同时填写或同时留空",
        )
    if raw_score is not None and maximum_score is not None:
        _validate_finite_number(raw_score, "raw_score")
        _validate_finite_number(maximum_score, "maximum_score")
        if maximum_score <= 0 or raw_score < 0 or raw_score > maximum_score:
            raise ValidationError(
                "INVALID_MACHINE_TEST_SCORE",
                "机试原始分必须位于0到满分之间，且满分必须大于0",
            )
    if machine_test.scoring_method in (
        MachineScoringMethod.POINTS,
        MachineScoringMethod.MIXED,
    ) and raw_score is None:
        raise ValidationError(
            "MACHINE_TEST_SCORE_REQUIRED",
            "points或mixed计分必须同时填写raw_score与maximum_score",
        )


def _validate_finite_number(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValidationError(
            "INVALID_MACHINE_TEST_SCORE",
            f"{field_name}必须是有限数字",
            {"field": field_name},
        )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _validate_required_durations(values: tuple[int, ...]) -> tuple[int, ...]:
    if not values or len(values) != len(set(values)):
        raise ValidationError(
            "INVALID_MACHINE_DURATION_CONFIG",
            "required_machine_durations必须是非空且不重复的分钟列表",
        )
    for value in values:
        _validate_duration(value)
    return tuple(values)


def _validate_duration(value: int) -> None:
    _validate_integer_range(
        value,
        "duration_minutes",
        _MIN_DURATION_MINUTES,
        _MAX_DURATION_MINUTES,
    )


def _validate_integer_range(
    value: int,
    field_name: str,
    minimum: int,
    maximum: int | None,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            "INVALID_MACHINE_TEST_INTEGER",
            f"{field_name}必须是整数",
            {"field": field_name},
        )
    if value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(
            "INVALID_MACHINE_TEST_INTEGER",
            f"{field_name}超出允许范围",
            {"field": field_name, "minimum": minimum, "maximum": maximum},
        )


def _normalize_required_text(value: str, field_name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValidationError(
            "INVALID_MACHINE_TEST_TEXT",
            f"{field_name}不能为空且不得超过{maximum}个字符",
            {"field": field_name},
        )
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
