from __future__ import annotations

import re
import statistics
import unicodedata
from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from chose_school.business.ports import AssessmentStore, SelectionReadinessStore
from chose_school.business.selection_readiness_policy import (
    apply_selection_readiness,
)
from chose_school.domain.enums import (
    MockAttendanceStatus,
    MockDifficulty,
    MockInvalidReasonCode,
    MockPaperFamily,
    ScoreBand,
)
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import (
    AssessmentBandSummary,
    AssessmentSummary,
    AssessmentWindowStatistics,
    MockExamInput,
    MockExamLedgerAddResult,
    MockExamLedgerInput,
    MockSubjectResultInput,
    Settings,
)


_CONSERVATIVE_RANK_FROM_LOW = 2
_TYPICAL_RANK_FROM_LOW = 3
_MOCK_RULE_VERSION = "mock-window-v2"
_EXPECTED_SESSION_COUNT = 5
_MAX_SESSION_QUERY_LIMIT = 10000
_TEXT_LIMIT = 240
_NOTE_LIMIT = 2000
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def _load_exam_time_zone() -> timezone | ZoneInfo:
    """Use IANA rules when available; modern mainland exam dates are UTC+8."""

    try:
        return ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        # Windows Python installations may not ship the IANA tz database. The
        # ledger accepts modern exam dates only, for which Shanghai is UTC+8.
        return timezone(timedelta(hours=8), name="Asia/Shanghai")


_EXAM_TIME_ZONE = _load_exam_time_zone()
_AUTHENTIC_SLOT_TIMES = (
    (time(8, 30), time(11, 30)),
    (time(14, 0), time(17, 0)),
    (time(8, 30), time(11, 30)),
    (time(14, 0), time(17, 0)),
)
_SCORE_BAND_RULES = (
    (float("-inf"), 290.0, ScoreBand.BELOW_290),
    (290.0, 305.0, ScoreBand.FROM_290_TO_304),
    (305.0, 315.0, ScoreBand.FROM_305_TO_314),
    (315.0, 325.0, ScoreBand.FROM_315_TO_324),
    (325.0, 335.0, ScoreBand.FROM_325_TO_334),
    (335.0, 345.0, ScoreBand.FROM_335_TO_344),
    (345.0, 360.0, ScoreBand.FROM_345_TO_359),
    (360.0, 380.0, ScoreBand.FROM_360_TO_379),
    (380.0, float("inf"), ScoreBand.AT_LEAST_380),
)
_SCORE_BAND_ORDER = {
    band.value: index for index, (_, _, band) in enumerate(_SCORE_BAND_RULES)
}


class AssessmentService:
    """Own the append-only mock ledger and its conservative score window."""

    def __init__(
        self,
        store: AssessmentStore,
        readiness_store: SelectionReadinessStore,
        settings: Settings,
    ) -> None:
        self._store = store
        self._readiness_store = readiness_store
        self._settings = settings
        _validate_window_settings(settings)
        self._expected_subject_codes = (
            settings.strict_politics_code,
            settings.strict_english_code,
            settings.strict_math_code,
            settings.strict_professional_code,
        )

    def initialize_default_profile(self, trace_id: str) -> int:
        _validate_trace_id(trace_id)
        return self._store.ensure_default_profile(
            profile_key=self._settings.profile_key,
            undergraduate_school=self._settings.undergraduate_school,
            undergraduate_major=self._settings.undergraduate_major,
            target_year=self._settings.target_exam_year,
            politics_code=self._settings.strict_politics_code,
            english_code=self._settings.strict_english_code,
            math_code=self._settings.strict_math_code,
            professional_code=self._settings.strict_professional_code,
            target_degree_type=self._settings.target_degree_type,
            target_tier=self._settings.target_tier,
            trace_id=trace_id,
        )

    def add_mock_exam(self, mock_exam: MockExamInput, trace_id: str) -> int:
        """Preserve the legacy exact-score command without making it decision eligible."""

        _validate_trace_id(trace_id)
        self._validate_legacy_scores(mock_exam)
        profile_id = self.initialize_default_profile(trace_id)
        return self._store.add_mock_exam(profile_id, mock_exam, trace_id)

    def add_mock_exam_ledger(
        self,
        mock_exam: MockExamLedgerInput,
        trace_id: str,
    ) -> MockExamLedgerAddResult:
        _validate_trace_id(trace_id)
        normalized = self._normalize_mock_ledger(mock_exam)
        profile_id = self.initialize_default_profile(trace_id)
        return self._store.add_mock_exam_ledger(profile_id, normalized, trace_id)

    def list_mock_exams(
        self,
        include_legacy: bool = False,
        eligible_only: bool = False,
        session_id: int | None = None,
        limit: int = 100,
    ) -> Sequence[Mapping[str, Any]]:
        if session_id is not None:
            _validate_integer(session_id, "session_id", 1, None)
        _validate_integer(limit, "limit", 1, _MAX_SESSION_QUERY_LIMIT)
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            return ()
        return self._store.list_mock_exam_sessions(
            profile_id,
            include_legacy,
            eligible_only,
            session_id,
            limit,
        )

    def exclude_mock_exam(
        self,
        session_id: int,
        reason: str,
        trace_id: str,
    ) -> int:
        _validate_trace_id(trace_id)
        _validate_integer(session_id, "session_id", 1, None)
        normalized_reason = _normalize_required_text(reason, "reason", 1000)
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            raise ValidationError(
                "PROFILE_NOT_INITIALIZED",
                "个人画像尚未初始化，不能排除套卷会话",
            )
        return self._store.exclude_mock_exam(
            profile_id,
            session_id,
            normalized_reason,
            trace_id,
        )

    def summarize(self) -> AssessmentSummary:
        sessions = tuple(
            self.list_mock_exams(
                include_legacy=True,
                eligible_only=False,
                limit=_MAX_SESSION_QUERY_LIMIT,
            )
        )
        if sessions:
            eligible_sessions = tuple(
                session
                for session in sessions
                if bool(session["is_assessment_eligible"])
            )
            groups = _build_comparison_groups(eligible_sessions)
            active_key = (
                str(eligible_sessions[-1]["comparison_key"])
                if eligible_sessions
                else None
            )
            active_sessions = tuple(
                session
                for session in eligible_sessions
                if session["comparison_key"] == active_key
            )
            window = active_sessions[-self._settings.mock_rolling_window_size :]
            score_summary = _summarize_window(
                settings=self._settings,
                sessions=sessions,
                eligible_sessions=eligible_sessions,
                comparison_groups=groups,
                active_key=active_key,
                window=window,
            )
        else:
            score_summary = _empty_summary(self._settings)
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        readiness_facts = self._readiness_store.read_facts(
            profile_id,
            self._settings.target_exam_year,
        )
        return apply_selection_readiness(
            score_summary,
            readiness_facts,
            self._settings,
        )

    def _normalize_mock_ledger(
        self,
        mock_exam: MockExamLedgerInput,
    ) -> MockExamLedgerInput:
        if type(mock_exam.started_on) is not date or type(mock_exam.completed_on) is not date:
            raise ValidationError(
                "INVALID_MOCK_DATE",
                "start-date与end-date必须是YYYY-MM-DD日期",
            )
        _validate_integer(mock_exam.attempt_number, "attempt_number", 1, None)
        _validate_boolean_fields(mock_exam)
        if not isinstance(mock_exam.paper_family, MockPaperFamily):
            raise ValidationError("INVALID_MOCK_PAPER_FAMILY", "paper_family枚举无效")
        if not isinstance(mock_exam.difficulty, MockDifficulty):
            raise ValidationError("INVALID_MOCK_DIFFICULTY", "difficulty枚举无效")
        if mock_exam.invalid_reason_code is not None and not isinstance(
            mock_exam.invalid_reason_code,
            MockInvalidReasonCode,
        ):
            raise ValidationError(
                "INVALID_MOCK_REASON_CODE",
                "invalid_reason_code枚举无效",
            )
        if mock_exam.attempt_number > 1 and mock_exam.first_exposure:
            raise ValidationError(
                "REPEAT_MOCK_CANNOT_BE_FIRST_EXPOSURE",
                "重复尝试不能标记为首次见卷",
            )

        normalized_subjects = self._normalize_subject_results(
            mock_exam.subject_results,
            mock_exam.started_on,
            mock_exam.completed_on,
            mock_exam.authentic_time_slots,
        )
        execution_valid = _is_execution_protocol_valid(mock_exam)
        reason_note = _normalize_optional_text(
            mock_exam.invalid_reason_note,
            _NOTE_LIMIT,
        )
        if execution_valid and (mock_exam.invalid_reason_code is not None or reason_note):
            raise ValidationError(
                "UNEXPECTED_MOCK_INVALID_REASON",
                "完整有效协议不能同时填写无效原因；正常低分或失误写入notes",
            )
        if not execution_valid and (
            mock_exam.invalid_reason_code is None or not reason_note
        ):
            raise ValidationError(
                "MOCK_INVALID_REASON_REQUIRED",
                "任一执行协议条件失败时必须同时填写受控无效原因代码和说明",
            )

        content_hash = _normalize_optional_text(mock_exam.paper_content_sha256, 64)
        if content_hash is not None and _SHA256_PATTERN.fullmatch(content_hash) is None:
            raise ValidationError(
                "INVALID_MOCK_CONTENT_SHA256",
                "paper-content-sha256必须是64位十六进制",
            )
        return replace(
            mock_exam,
            paper_name=_normalize_required_text(
                mock_exam.paper_name,
                "paper_name",
                _TEXT_LIMIT,
            ),
            paper_key=_normalize_identity_key(
                mock_exam.paper_key,
                "paper_key",
                120,
            ),
            paper_source=_normalize_required_text(
                mock_exam.paper_source,
                "paper_source",
                _TEXT_LIMIT,
            ),
            paper_content_sha256=(content_hash.lower() if content_hash else None),
            scoring_rule_key=_normalize_identity_key(
                mock_exam.scoring_rule_key,
                "scoring_rule_key",
                120,
            ),
            subject_results=normalized_subjects,
            invalid_reason_note=reason_note,
            notes=_normalize_optional_text(mock_exam.notes, _NOTE_LIMIT),
        )

    def _normalize_subject_results(
        self,
        subject_results: Mapping[str, MockSubjectResultInput],
        started_on: date,
        completed_on: date,
        authentic_time_slots: bool,
    ) -> Mapping[str, MockSubjectResultInput]:
        if set(subject_results) != set(self._expected_subject_codes):
            raise ValidationError(
                "MOCK_SUBJECT_CONTRACT_MISMATCH",
                "subject-results必须且只能包含101、204、302、408四科",
                {"received_codes": sorted(subject_results)},
            )
        maximum_by_code = dict(
            zip(self._expected_subject_codes, (100.0, 100.0, 150.0, 150.0))
        )
        normalized: dict[str, MockSubjectResultInput] = {}
        for subject_index, subject_code in enumerate(self._expected_subject_codes):
            result = _normalize_subject_result(
                subject_code,
                subject_results[subject_code],
                maximum_by_code[subject_code],
            )
            expected_day = (
                started_on
                if subject_code in self._expected_subject_codes[:2]
                else completed_on
            )
            if authentic_time_slots and result.started_at is not None:
                expected_start, expected_end = _AUTHENTIC_SLOT_TIMES[subject_index]
                _validate_authentic_subject_slot(
                    subject_code,
                    result.started_at,
                    result.ended_at,
                    expected_day,
                    expected_start,
                    expected_end,
                )
            normalized[subject_code] = result
        return normalized

    @staticmethod
    def _validate_legacy_scores(mock_exam: MockExamInput) -> None:
        _validate_integer(mock_exam.attempt_number, "attempt_number", 1, None)
        limits = {
            "politics_score": 100.0,
            "english_score": 100.0,
            "math_score": 150.0,
            "computer_science_score": 150.0,
        }
        for field_name, maximum in limits.items():
            value = getattr(mock_exam, field_name)
            _validate_finite_score(value, field_name, maximum)


def _summarize_window(
    settings: Settings,
    sessions: Sequence[Mapping[str, Any]],
    eligible_sessions: Sequence[Mapping[str, Any]],
    comparison_groups: tuple[Mapping[str, Any], ...],
    active_key: str | None,
    window: Sequence[Mapping[str, Any]],
) -> AssessmentSummary:
    lower_totals = tuple(float(session["total_lower"]) for session in window)
    upper_totals = tuple(float(session["total_upper"]) for session in window)
    has_intervals = any(bool(session["has_score_interval"]) for session in window)
    is_score_window_ready = len(window) >= settings.minimum_mock_sessions
    ranked_sessions = sorted(
        window,
        key=lambda session: (float(session["total_lower"]), int(session["session_id"])),
    )
    conservative_session = (
        ranked_sessions[_CONSERVATIVE_RANK_FROM_LOW - 1]
        if is_score_window_ready
        else None
    )
    typical_session = (
        ranked_sessions[_TYPICAL_RANK_FROM_LOW - 1]
        if is_score_window_ready
        else None
    )
    subject_lower_series, subject_upper_series = _subject_series(window)
    exact_window = bool(window) and not has_intervals
    exact_totals = lower_totals if exact_window else ()
    exact_subject_means = (
        {
            _subject_output_key(code): round(statistics.fmean(values), 2)
            for code, values in subject_lower_series.items()
        }
        if exact_window
        else {}
    )
    statistics_summary = AssessmentWindowStatistics(
        total_lower_mean=_rounded_mean(lower_totals),
        total_upper_mean=_rounded_mean(upper_totals),
        conservative_total_lower=_session_total(conservative_session, "total_lower"),
        conservative_total_upper=_session_total(conservative_session, "total_upper"),
        typical_total_lower=_session_total(typical_session, "total_lower"),
        typical_total_upper=_session_total(typical_session, "total_upper"),
        total_lower_sequence=lower_totals,
        total_upper_sequence=upper_totals,
        subject_lower_series=subject_lower_series,
        subject_upper_series=subject_upper_series,
    )
    band_summary = _build_band_summary(lower_totals, conservative_session)
    invalid_count = sum(
        session["eligibility_status"]
        not in ("valid", "legacy_unverified", "excluded")
        for session in sessions
    )
    return AssessmentSummary(
        session_count=len(window),
        total_mean=_rounded_mean(exact_totals),
        total_standard_deviation=_rounded_standard_deviation(exact_totals),
        conservative_total=(
            _session_total(conservative_session, "total_lower")
            if exact_window
            else None
        ),
        is_decision_ready=is_score_window_ready,
        subject_means=exact_subject_means,
        rule_version=_MOCK_RULE_VERSION,
        as_of=datetime.now(timezone.utc).isoformat(),
        required_session_count=settings.minimum_mock_sessions,
        rolling_window_size=settings.mock_rolling_window_size,
        total_session_count=len(sessions),
        legacy_session_count=sum(
            session["eligibility_status"] == "legacy_unverified"
            for session in sessions
        ),
        invalid_session_count=invalid_count,
        excluded_session_count=sum(
            session["eligibility_status"] == "excluded" for session in sessions
        ),
        eligible_total_count=len(eligible_sessions),
        active_comparison_key=active_key,
        comparison_groups=comparison_groups,
        window_session_ids=tuple(int(session["session_id"]) for session in window),
        window_sessions=tuple(_window_session_payload(session) for session in window),
        is_score_window_ready=is_score_window_ready,
        is_selection_ready=False,
        selection_blocking_reasons=(),
        has_score_intervals=has_intervals,
        statistics=statistics_summary,
        band=band_summary,
        subject_risk_status=(
            "review_required" if is_score_window_ready else "insufficient_samples"
        ),
    )


def _empty_summary(settings: Settings) -> AssessmentSummary:
    return AssessmentSummary(
        session_count=0,
        total_mean=None,
        total_standard_deviation=None,
        conservative_total=None,
        is_decision_ready=False,
        subject_means={},
        rule_version=_MOCK_RULE_VERSION,
        as_of=datetime.now(timezone.utc).isoformat(),
        required_session_count=settings.minimum_mock_sessions,
        rolling_window_size=settings.mock_rolling_window_size,
        is_score_window_ready=False,
        is_selection_ready=False,
        selection_blocking_reasons=(),
        statistics=AssessmentWindowStatistics(
            total_lower_mean=None,
            total_upper_mean=None,
            conservative_total_lower=None,
            conservative_total_upper=None,
            typical_total_lower=None,
            typical_total_upper=None,
            total_lower_sequence=(),
            total_upper_sequence=(),
            subject_lower_series={},
            subject_upper_series={},
        ),
        band=AssessmentBandSummary(None, (), None, False),
    )


def _build_comparison_groups(
    sessions: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for session in sessions:
        grouped[str(session["comparison_key"])].append(session)
    return tuple(
        {
            "comparison_key": key,
            "eligible_session_count": len(grouped[key]),
            "latest_session_id": int(grouped[key][-1]["session_id"]),
            "latest_completed_on": grouped[key][-1]["completed_on"],
            "is_active": key == (sessions[-1]["comparison_key"] if sessions else None),
        }
        for key in sorted(grouped)
    )


def _subject_series(
    sessions: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, tuple[float, ...]], Mapping[str, tuple[float, ...]]]:
    lower: dict[str, list[float]] = defaultdict(list)
    upper: dict[str, list[float]] = defaultdict(list)
    for session in sessions:
        for result in session["subject_results"]:
            code = str(result["subject_code"])
            lower[code].append(float(result["score_lower"]))
            upper[code].append(float(result["score_upper"]))
    ordered_codes = ("101", "204", "302", "408")
    return (
        {code: tuple(lower[code]) for code in ordered_codes if code in lower},
        {code: tuple(upper[code]) for code in ordered_codes if code in upper},
    )


def _build_band_summary(
    lower_totals: Sequence[float],
    conservative_session: Mapping[str, Any] | None,
) -> AssessmentBandSummary:
    if conservative_session is None:
        return AssessmentBandSummary(None, (), None, False)
    conservative_band = _classify_score_band(
        float(conservative_session["total_lower"])
    ).value
    occupied = tuple(
        sorted(
            {_classify_score_band(value).value for value in lower_totals},
            key=lambda band: _SCORE_BAND_ORDER[band],
        )
    )
    guard_applied = len(occupied) > 1
    role_band = occupied[0] if guard_applied else conservative_band
    return AssessmentBandSummary(
        conservative_band=conservative_band,
        occupied_bands=occupied,
        role_band=role_band,
        multi_band_guard_applied=guard_applied,
    )


def _classify_score_band(score: float) -> ScoreBand:
    for lower, upper, band in _SCORE_BAND_RULES:
        if lower <= score < upper:
            return band
    raise AssertionError(f"score band is undefined: {score}")


def _window_session_payload(session: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "session_id": int(session["session_id"]),
        "paper_key": session["paper_key"],
        "paper_name": session["paper_name"],
        "started_on": session["taken_on"],
        "completed_on": session["completed_on"],
        "attempt_number": int(session["attempt_number"]),
        "comparison_key": session["comparison_key"],
        "score_precision_mode": session["score_precision_mode"],
        "total_lower": float(session["total_lower"]),
        "total_upper": float(session["total_upper"]),
        "subject_results": session["subject_results"],
    }


def _normalize_subject_result(
    subject_code: str,
    result: MockSubjectResultInput,
    maximum_score: float,
) -> MockSubjectResultInput:
    if not isinstance(result.attendance_status, MockAttendanceStatus):
        raise ValidationError(
            "INVALID_MOCK_ATTENDANCE",
            f"{subject_code} attendance_status无效",
        )
    note = _normalize_optional_text(result.note, _NOTE_LIMIT)
    if result.attendance_status is MockAttendanceStatus.ABSENT:
        if any(
            value is not None
            for value in (
                result.score_lower,
                result.score_upper,
                result.started_at,
                result.ended_at,
            )
        ):
            raise ValidationError(
                "ABSENT_MOCK_SUBJECT_HAS_RESULT",
                f"{subject_code}缺考时分数与起止时间必须留空",
            )
        return replace(result, note=note)

    _validate_aware_time_range(subject_code, result.started_at, result.ended_at)
    if result.attendance_status is MockAttendanceStatus.PRESENT_BLANK:
        for value in (result.score_lower, result.score_upper):
            if value not in (None, 0, 0.0):
                raise ValidationError(
                    "PRESENT_BLANK_SCORE_MUST_BE_ZERO",
                    f"{subject_code}到场空白只能记录0分",
                )
        return replace(result, score_lower=0.0, score_upper=0.0, note=note)

    if result.score_lower is None or result.score_upper is None:
        raise ValidationError(
            "MOCK_SCORE_BOUNDS_REQUIRED",
            f"{subject_code}到场评分必须提供score_lower与score_upper",
        )
    lower = _validate_finite_score(result.score_lower, "score_lower", maximum_score)
    upper = _validate_finite_score(result.score_upper, "score_upper", maximum_score)
    if lower > upper:
        raise ValidationError(
            "INVALID_MOCK_SCORE_INTERVAL",
            f"{subject_code}分数下界不得高于上界",
        )
    return replace(result, score_lower=lower, score_upper=upper, note=note)


def _validate_aware_time_range(
    subject_code: str,
    started_at: datetime | None,
    ended_at: datetime | None,
) -> None:
    if started_at is None or ended_at is None:
        raise ValidationError(
            "MOCK_SUBJECT_TIME_REQUIRED",
            f"{subject_code}到场科目必须记录开始与结束时间",
        )
    if started_at.utcoffset() is None or ended_at.utcoffset() is None:
        raise ValidationError(
            "MOCK_SUBJECT_TIMEZONE_REQUIRED",
            f"{subject_code}时间必须包含时区偏移",
        )
    duration_seconds = (ended_at - started_at).total_seconds()
    if duration_seconds <= 0 or duration_seconds % 60 != 0:
        raise ValidationError(
            "INVALID_MOCK_SUBJECT_TIME_RANGE",
            f"{subject_code}结束时间必须晚于开始时间，且精确到整分钟",
        )


def _validate_authentic_subject_slot(
    subject_code: str,
    started_at: datetime,
    ended_at: datetime | None,
    expected_day: date,
    expected_start: time,
    expected_end: time,
) -> None:
    if ended_at is None:
        raise ValidationError(
            "MOCK_SUBJECT_TIME_REQUIRED",
            f"{subject_code}真实考试时段必须同时记录开始与结束时间",
        )
    local_start = started_at.astimezone(_EXAM_TIME_ZONE)
    local_end = ended_at.astimezone(_EXAM_TIME_ZONE)
    actual_start = local_start.time().replace(tzinfo=None)
    actual_end = local_end.time().replace(tzinfo=None)
    if (
        local_start.date() != expected_day
        or local_end.date() != expected_day
        or actual_start != expected_start
        or actual_end != expected_end
    ):
        raise ValidationError(
            "MOCK_SUBJECT_SLOT_MISMATCH",
            f"{subject_code}起止时间不符合北京时间{expected_start:%H:%M}—{expected_end:%H:%M}；请修正时间或取消authentic-time-slots并说明无效原因",
        )
def _is_execution_protocol_valid(mock_exam: MockExamLedgerInput) -> bool:
    return (
        mock_exam.first_exposure
        and mock_exam.complete_paper_set
        and mock_exam.strict_schedule
        and mock_exam.authentic_time_slots
        and mock_exam.strict_timed
        and not mock_exam.consulted_materials
        and not mock_exam.received_assistance
        and not mock_exam.paused_timer
        and not mock_exam.reviewed_answers_early
        and (mock_exam.completed_on - mock_exam.started_on).days == 1
    )


def _validate_boolean_fields(mock_exam: MockExamLedgerInput) -> None:
    for field_name in (
        "first_exposure",
        "complete_paper_set",
        "strict_schedule",
        "authentic_time_slots",
        "strict_timed",
        "consulted_materials",
        "received_assistance",
        "paused_timer",
        "reviewed_answers_early",
    ):
        if not isinstance(getattr(mock_exam, field_name), bool):
            raise ValidationError(
                "INVALID_MOCK_BOOLEAN",
                f"{field_name}必须是布尔值",
                {"field": field_name},
            )


def _validate_window_settings(settings: Settings) -> None:
    if (
        settings.minimum_mock_sessions != _EXPECTED_SESSION_COUNT
        or settings.mock_rolling_window_size != _EXPECTED_SESSION_COUNT
    ):
        raise ValidationError(
            "INVALID_MOCK_WINDOW_CONFIG",
            "当前mock-window-v2规则要求minimum_sessions与rolling_window_size均为5",
        )


def _validate_trace_id(trace_id: str) -> None:
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ValidationError("TRACE_ID_REQUIRED", "套卷账本写操作必须提供TraceId")


def _validate_integer(
    value: int,
    field_name: str,
    minimum: int,
    maximum: int | None,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            "INVALID_MOCK_INTEGER",
            f"{field_name}必须是整数",
            {"field": field_name},
        )
    if value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(
            "INVALID_MOCK_INTEGER",
            f"{field_name}超出允许范围",
            {"field": field_name, "minimum": minimum, "maximum": maximum},
        )


def _validate_finite_score(value: float, field_name: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValidationError(
            "INVALID_MOCK_SCORE",
            f"{field_name}必须是有限数字",
            {"field": field_name},
        )
    numeric = float(value)
    if numeric < 0 or numeric > maximum:
        raise ValidationError(
            "SCORE_OUT_OF_RANGE",
            f"{field_name}必须位于0到{maximum:g}之间",
            {"field": field_name, "maximum": maximum},
        )
    return numeric


def _normalize_required_text(value: str, field_name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValidationError("INVALID_MOCK_TEXT", f"{field_name}必须是文本")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValidationError(
            "INVALID_MOCK_TEXT",
            f"{field_name}不能为空且不得超过{maximum}个字符",
            {"field": field_name},
        )
    return normalized


def _normalize_identity_key(value: str, field_name: str, maximum: int) -> str:
    normalized = _normalize_required_text(value, field_name, maximum)
    canonical = unicodedata.normalize("NFKC", normalized).casefold()
    if len(canonical) > maximum:
        raise ValidationError(
            "INVALID_MOCK_TEXT",
            f"{field_name}规范化后不得超过{maximum}个字符",
            {"field": field_name},
        )
    return canonical


def _normalize_optional_text(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("INVALID_MOCK_TEXT", "可选说明必须是文本")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValidationError(
            "INVALID_MOCK_TEXT",
            f"可选说明不得超过{maximum}个字符",
        )
    return normalized or None


def _rounded_mean(values: Sequence[float]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def _rounded_standard_deviation(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(statistics.stdev(values), 2) if len(values) >= 2 else 0.0


def _session_total(
    session: Mapping[str, Any] | None,
    field_name: str,
) -> float | None:
    return float(session[field_name]) if session is not None else None


def _subject_output_key(subject_code: str) -> str:
    return {
        "101": "politics_score",
        "204": "english_score",
        "302": "math_score",
        "408": "computer_science_score",
    }[subject_code]
