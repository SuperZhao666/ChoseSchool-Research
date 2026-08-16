from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import replace
from datetime import date
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, unquote, urlparse

from chose_school.business.ports import ApplicantAchievementStore
from chose_school.domain.enums import (
    AchievementCategory,
    AchievementEvidenceRelationship,
    AchievementParticipationType,
    AchievementVerificationStatus,
    ApplicantEvidenceAccessScope,
    ApplicantEvidenceGrade,
    ApplicantEvidenceReviewMethod,
    ApplicantEvidenceStatus,
)
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.models import (
    ApplicantAchievementAddResult,
    ApplicantAchievementInput,
    ApplicantEvidenceInput,
    Settings,
)


_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,159}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MIME_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png"})
_EVENT_FINGERPRINT_VERSION = "v2"
_VISUAL_METHODS = frozenset(
    {
        ApplicantEvidenceReviewMethod.FULL_DOCUMENT_VISUAL_REVIEW,
        ApplicantEvidenceReviewMethod.COMBINED_VISUAL_AND_TEXT,
    }
)
_SENSITIVE_DETAIL_KEYS = frozenset(
    {
        "certificatenumber",
        "certificateno",
        "certificateid",
        "idnumber",
        "identitynumber",
        "officialid",
        "studentid",
        "studentnumber",
        "registrationid",
        "registrationnumber",
        "身份证号",
        "身份证号码",
        "学号",
        "报名号",
        "准考证号",
        "证书号",
        "证书编号",
        "证书号码",
    }
)
_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?ix)(?:"
    r"(?:certificate|cert)[\s_-]*(?:number|no|id|identifier|serial)|"
    r"student[\s_-]*(?:id|number|no|identifier|serial)|"
    r"registration[\s_-]*(?:id|number|no|identifier|serial)|"
    r"identity[\s_-]*(?:id|number|no|identifier|serial)|official[\s_-]*id|"
    r"身份证(?:号|号码)|学号|报名号|准考证号|证书(?:号|编号|号码|序列号)"
    r")\s*[:：=#]?\s*[a-z0-9][a-z0-9_-]{3,}"
)
_SENSITIVE_DETAIL_KEY_PATTERN = re.compile(
    r"(?:certificate|cert)(?:number|no|id|identifier|serial)|"
    r"(?:student|registration|identity)(?:number|no|id|identifier|serial)|"
    r"(?:证书|学生|报名|准考证|身份证).*(?:号|编号|号码|序列号)"
)


class ApplicantAchievementService:
    """Append evidence-backed applicant achievements without inflating evidence grades."""

    def __init__(self, store: ApplicantAchievementStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def add_achievement(
        self,
        achievement: ApplicantAchievementInput,
        trace_id: str,
    ) -> ApplicantAchievementAddResult:
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValidationError(
                "TRACE_ID_REQUIRED",
                "追加个人成果必须提供 TraceId",
            )
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        normalized = _normalize_achievement(achievement)
        canonical_details_json = _canonical_json(normalized.details)
        fingerprint = _event_fingerprint(normalized, canonical_details_json)
        return self._store.add_achievement(
            profile_id,
            normalized,
            canonical_details_json,
            fingerprint,
            _EVENT_FINGERPRINT_VERSION,
            trace_id.strip(),
        )

    def list_achievements(
        self,
        category: str | None = None,
        achievement_year: int | None = None,
        achievement_key: str | None = None,
        include_history: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            return ()
        normalized_category = None
        if category is not None:
            try:
                normalized_category = AchievementCategory(category).value
            except ValueError as error:
                raise ValidationError(
                    "INVALID_ACHIEVEMENT_CATEGORY",
                    f"不支持的个人成果类别：{category}",
                ) from error
        normalized_year = None
        if achievement_year is not None:
            if isinstance(achievement_year, bool) or not 2000 <= achievement_year <= 2100:
                raise ValidationError(
                    "INVALID_ACHIEVEMENT_YEAR",
                    "个人成果年份必须在 2000 至 2100 之间",
                )
            normalized_year = achievement_year
        normalized_key = None
        if achievement_key is not None:
            normalized_key = achievement_key.strip().lower()
            if not _KEY_PATTERN.fullmatch(normalized_key):
                raise ValidationError(
                    "INVALID_ACHIEVEMENT_KEY",
                    "个人成果键必须是 3 至 160 位小写字母、数字或 ._:-",
                )
        return self._store.list_achievements(
            profile_id,
            normalized_category,
            normalized_year,
            normalized_key,
            include_history,
        )


def _normalize_achievement(
    achievement: ApplicantAchievementInput,
) -> ApplicantAchievementInput:
    achievement_key = _plain_text(achievement.achievement_key, "成果键", 160).lower()
    if not _KEY_PATTERN.fullmatch(achievement_key):
        raise ValidationError(
            "INVALID_ACHIEVEMENT_KEY",
            "个人成果键必须是 3 至 160 位小写字母、数字或 ._:-",
        )
    if isinstance(achievement.achievement_year, bool) or not (
        2000 <= achievement.achievement_year <= 2100
    ):
        raise ValidationError(
            "INVALID_ACHIEVEMENT_YEAR",
            "个人成果年份必须在 2000 至 2100 之间",
        )
    awarded_on = achievement.awarded_on
    if awarded_on is not None and not isinstance(awarded_on, date):
        raise ValidationError("INVALID_ACHIEVEMENT_DATE", "获奖日期必须是 ISO 日期")
    if awarded_on is not None and awarded_on.year != achievement.achievement_year:
        raise ValidationError(
            "ACHIEVEMENT_DATE_YEAR_MISMATCH",
            "精确获奖日期与成果年份不一致；仅有月份时请留空日期并保留期间原文",
        )

    title = _privacy_safe_text(achievement.title, "成果名称", 300)
    issuer = _privacy_safe_text(achievement.issuer, "颁发单位", 300)
    period_label = _privacy_safe_text(achievement.period_label, "成果期间", 120)
    result = _privacy_safe_text(achievement.result, "成果结果", 200)
    note = _optional_privacy_safe_text(achievement.note, "成果说明", 2000)

    participation = achievement.participation_type
    team_name = _optional_privacy_safe_text(achievement.team_name, "团队名称", 200)
    if participation is AchievementParticipationType.TEAM and team_name is None:
        raise ValidationError("TEAM_NAME_REQUIRED", "团队成果必须填写团队名称")
    if participation is not AchievementParticipationType.TEAM and team_name is not None:
        raise ValidationError(
            "TEAM_NAME_NOT_ALLOWED",
            "非团队成果不得填写团队名称",
        )
    if achievement.category is AchievementCategory.SCHOLARSHIP:
        if participation is not AchievementParticipationType.NOT_APPLICABLE:
            raise ValidationError(
                "INVALID_SCHOLARSHIP_PARTICIPATION",
                "奖学金不使用个人赛或团队赛口径，应为 not_applicable",
            )
        if achievement.stage.value != "academic_year":
            raise ValidationError(
                "INVALID_SCHOLARSHIP_STAGE",
                "奖学金阶段必须为 academic_year",
            )

    try:
        details = dict(achievement.details)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "INVALID_ACHIEVEMENT_DETAILS",
            "成果 details 必须是 JSON 对象",
        ) from error
    _reject_sensitive_details(details)
    _validate_composite_measurements(details)
    _canonical_json(details)

    evidence = tuple(_normalize_evidence(item) for item in achievement.evidence)
    if not evidence:
        raise ValidationError(
            "ACHIEVEMENT_EVIDENCE_REQUIRED",
            "个人成果至少需要一份可追溯证据",
        )
    hashes = [item.source_content_sha256 for item in evidence]
    if len(hashes) != len(set(hashes)):
        raise ValidationError(
            "DUPLICATE_ACHIEVEMENT_EVIDENCE",
            "同一成果不得重复关联内容相同的证据文件",
        )
    if not any(
        item.relationship is AchievementEvidenceRelationship.SUPPORTS
        for item in evidence
    ):
        raise ValidationError(
            "SUPPORTING_ACHIEVEMENT_EVIDENCE_REQUIRED",
            "个人成果至少需要一份 relationship=supports 的证据",
        )
    if achievement.verification_status is AchievementVerificationStatus.DOCUMENT_CONFIRMED:
        if any(
            item.relationship is AchievementEvidenceRelationship.CONTRADICTS
            or item.evidence_status is ApplicantEvidenceStatus.CONFLICT
            for item in evidence
        ):
            raise ValidationError(
                "CONTRADICTED_ACHIEVEMENT_CANNOT_BE_CONFIRMED",
                "存在反证关系或证据复核冲突时，成果不能标记 document_confirmed",
            )
        has_visual_support = any(
            item.relationship is AchievementEvidenceRelationship.SUPPORTS
            and item.evidence_status is ApplicantEvidenceStatus.DOCUMENT_VISUAL_CONFIRMED
            and item.review_method in _VISUAL_METHODS
            for item in evidence
        )
        if not has_visual_support:
            raise ValidationError(
                "VISUAL_SUPPORT_REQUIRED",
                "document_confirmed 必须有一份已逐页视觉核验的支持性证据",
            )

    return replace(
        achievement,
        achievement_key=achievement_key,
        title=title,
        issuer=issuer,
        period_label=period_label,
        result=result,
        team_name=team_name,
        details=details,
        evidence=evidence,
        note=note,
    )


def _normalize_evidence(evidence: ApplicantEvidenceInput) -> ApplicantEvidenceInput:
    source_url = _plain_text(evidence.source_url, "证据链接", 2000)
    parsed = urlparse(source_url)
    _reject_sensitive_source_url(parsed)
    if evidence.source_access_scope is ApplicantEvidenceAccessScope.LOCAL_USER_FILE:
        if parsed.scheme != "file":
            raise ValidationError(
                "INVALID_LOCAL_EVIDENCE_URL",
                "本地证据必须使用 file URL",
            )
    elif parsed.scheme != "https" or not parsed.netloc:
        raise ValidationError(
            "INVALID_EVIDENCE_URL",
            "云端或公开证据必须使用 HTTPS 链接",
        )
    mime_type = evidence.source_mime_type.strip().lower()
    if mime_type not in _MIME_TYPES:
        raise ValidationError(
            "INVALID_EVIDENCE_MIME_TYPE",
            "证据文件只支持 PDF、JPEG 或 PNG",
        )
    content_hash = evidence.source_content_sha256.strip().lower()
    if not _SHA256_PATTERN.fullmatch(content_hash):
        raise ValidationError(
            "INVALID_EVIDENCE_HASH",
            "证据文件哈希必须是 64 位小写 SHA-256",
        )
    if isinstance(evidence.source_file_size_bytes, bool) or evidence.source_file_size_bytes <= 0:
        raise ValidationError(
            "INVALID_EVIDENCE_FILE_SIZE",
            "证据文件大小必须是正整数",
        )
    if not isinstance(evidence.source_retrieved_on, date) or not isinstance(
        evidence.source_reviewed_on, date
    ):
        raise ValidationError("INVALID_EVIDENCE_DATE", "证据取得和复核日期必须是 ISO 日期")
    if evidence.source_reviewed_on < evidence.source_retrieved_on:
        raise ValidationError(
            "INVALID_EVIDENCE_REVIEW_DATE",
            "证据复核日期不得早于取得日期",
        )
    if evidence.evidence_grade is ApplicantEvidenceGrade.OFFICIAL_ONLINE_VERIFICATION:
        raise ValidationError(
            "OFFICIAL_ONLINE_VERIFICATION_NOT_CONFIGURED",
            "尚未建立发证方主体匹配与在线核验快照，不能写入官方在线验真等级",
        )
    if evidence.evidence_status is ApplicantEvidenceStatus.DOCUMENT_VISUAL_CONFIRMED:
        if evidence.review_method not in _VISUAL_METHODS:
            raise ValidationError(
                "INVALID_VISUAL_REVIEW_METHOD",
                "视觉确认状态必须使用完整视觉核验方法",
            )
        if evidence.evidence_grade not in {
            ApplicantEvidenceGrade.PRIMARY_DOCUMENT_USER_COPY,
        }:
            raise ValidationError(
                "INVALID_VISUAL_EVIDENCE_GRADE",
                "视觉确认材料必须是个人持有原件副本或在线官方核验材料",
            )
    return replace(
        evidence,
        source_title=_privacy_safe_text(evidence.source_title, "证据标题", 500),
        source_url=source_url,
        source_mime_type=mime_type,
        source_content_sha256=content_hash,
        claim_text=_privacy_safe_text(evidence.claim_text, "证据主张", 1000),
        note=_optional_privacy_safe_text(evidence.note, "证据说明", 2000),
    )


def _event_fingerprint(
    achievement: ApplicantAchievementInput,
    canonical_details_json: str,
) -> str:
    payload = {
        "achievement_key": achievement.achievement_key,
        "category": achievement.category.value,
        "title": achievement.title,
        "issuer": achievement.issuer,
        "achievement_year": achievement.achievement_year,
        "period_label": achievement.period_label,
        "awarded_on": achievement.awarded_on.isoformat() if achievement.awarded_on else None,
        "scope_level": achievement.scope_level.value,
        "stage": achievement.stage.value,
        "result": achievement.result,
        "participation_type": achievement.participation_type.value,
        "team_name": achievement.team_name,
        "details": json.loads(canonical_details_json),
        "verification_status": achievement.verification_status.value,
        "note": achievement.note,
        "evidence": sorted(
            [
                {
                "source_content_sha256": item.source_content_sha256,
                "source_reviewed_on": item.source_reviewed_on.isoformat(),
                "review_method": item.review_method.value,
                "evidence_grade": item.evidence_grade.value,
                "evidence_status": item.evidence_status.value,
                "claim_text": item.claim_text,
                "note": item.note,
                "relationship": item.relationship.value,
                }
                for item in achievement.evidence
            ],
            key=lambda item: (
                item["source_content_sha256"],
                item["relationship"],
                item["claim_text"],
            ),
        ),
        "fingerprint_version": _EVENT_FINGERPRINT_VERSION,
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reject_sensitive_details(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = _normalized_sensitive_key(raw_key)
            if _is_sensitive_detail_key(key):
                raise ValidationError(
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    "成果结构化详情不得保存证书号、学号、身份证号或报名标识",
                    {"field": ".".join((*path, str(raw_key)))},
                )
            _reject_sensitive_details(child, (*path, str(raw_key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_sensitive_details(child, (*path, str(index)))
    elif isinstance(value, str) and _SENSITIVE_TEXT_PATTERN.search(
        unicodedata.normalize("NFKC", value)
    ):
        raise ValidationError(
            "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
            "成果结构化详情不得保存证书号、学号、身份证号或报名标识",
            {"field": ".".join(path) or "details"},
        )


def _validate_composite_measurements(details: Mapping[str, Any]) -> None:
    if "score" in details:
        score = details["score"]
        if not isinstance(score, Mapping) or set(score) != {"obtained", "maximum"}:
            raise ValidationError(
                "COMPOSITE_SCORE_REQUIRED",
                "成绩必须同时保存 obtained 和 maximum，不得把复合数字降成单一精确值",
            )
        _require_finite_number(score["obtained"], "score.obtained")
        maximum = _require_finite_number(score["maximum"], "score.maximum")
        if maximum <= 0 or float(score["obtained"]) > maximum:
            raise ValidationError("INVALID_SCORE_PAIR", "成绩分子分母不合法")
    if "rank" in details:
        rank = details["rank"]
        if not isinstance(rank, Mapping) or set(rank) != {"position", "population"}:
            raise ValidationError(
                "COMPOSITE_RANK_REQUIRED",
                "排名必须同时保存 position 和 population，不得只摘录一个数字",
            )
        position = _require_positive_integer(rank["position"], "rank.position")
        population = _require_positive_integer(rank["population"], "rank.population")
        if position > population:
            raise ValidationError("INVALID_RANK_PAIR", "排名名次不得大于参评人数")


def _require_finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("INVALID_MEASUREMENT", f"{field_name} 必须是数字")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError("INVALID_MEASUREMENT", f"{field_name} 必须是有限数字")
    return number


def _require_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError("INVALID_MEASUREMENT", f"{field_name} 必须是正整数")
    return value


def _plain_text(value: Any, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValidationError("INVALID_ACHIEVEMENT_TEXT", f"{label}必须是文本")
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or len(normalized) > maximum:
        raise ValidationError(
            "INVALID_ACHIEVEMENT_TEXT",
            f"{label}不能为空且不得超过 {maximum} 个字符",
        )
    return normalized


def _privacy_safe_text(value: Any, label: str, maximum: int) -> str:
    normalized = _plain_text(value, label, maximum)
    if _SENSITIVE_TEXT_PATTERN.search(normalized):
        raise ValidationError(
            "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
            "个人成果文本不得保存证书号、学号、身份证号或报名标识",
            {"field": label},
        )
    return normalized


def _optional_text(value: Any, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = _plain_text(value, label, maximum)
    return normalized or None


def _optional_privacy_safe_text(value: Any, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _privacy_safe_text(value, label, maximum)


def _normalized_sensitive_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)


def _is_sensitive_detail_key(normalized_key: str) -> bool:
    return (
        normalized_key in _SENSITIVE_DETAIL_KEYS
        or _SENSITIVE_DETAIL_KEY_PATTERN.search(normalized_key) is not None
    )


def _reject_sensitive_source_url(parsed: Any) -> None:
    decoded_tail = unicodedata.normalize(
        "NFKC",
        unquote(" ".join((parsed.path, parsed.query, parsed.fragment))),
    )
    query_keys = {
        _normalized_sensitive_key(key)
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    }
    url_tokens = [
        _normalized_sensitive_key(token)
        for token in re.split(r"[/\\?&=#;:]+", decoded_tail)
        if token.strip()
    ]
    if any(_is_sensitive_detail_key(key) for key in (*query_keys, *url_tokens)) or (
        _SENSITIVE_TEXT_PATTERN.search(decoded_tail) is not None
    ):
        raise ValidationError(
            "SENSITIVE_ACHIEVEMENT_URL_FORBIDDEN",
            "成果证据链接不得包含证书号、学号、身份证号或报名标识",
        )


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "INVALID_ACHIEVEMENT_DETAILS",
            "成果 details 必须是可序列化的 JSON 对象",
        ) from error
