from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Mapping, Sequence

from chose_school.business.ports import FairnessReviewStore
from chose_school.domain.enums import FairnessReviewConclusion
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.models import FairnessReviewInput, Settings


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_SOURCE_TYPES = frozenset(
    {"official_rule", "official_result", "public_experience", "other_public"}
)
_SIGNALS = frozenset({"supportive", "adverse", "context_only"})
_REVIEW_VERSION = "candidate-fairness-v1"


class FairnessReviewService:
    """Append project-year fairness judgements with immutable evidence snapshots."""

    def __init__(self, store: FairnessReviewStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def add_review(self, review: FairnessReviewInput, trace_id: str) -> int:
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValidationError("TRACE_ID_REQUIRED", "追加公平性审查必须提供TraceId")
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        if not self._store.observation_exists(review.observation_id):
            raise EntityNotFoundError(
                "OBSERVATION_NOT_FOUND",
                f"项目年度观测不存在：{review.observation_id}",
            )
        normalized = _normalize_review(review)
        evidence_json = json.dumps(
            normalized.evidence,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return self._store.add_fairness_review(
            profile_id,
            normalized,
            _REVIEW_VERSION,
            evidence_json,
            trace_id,
        )

    def list_reviews(
        self,
        observation_id: int | None = None,
        include_history: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        profile_id = self._store.find_profile_id(self._settings.profile_key)
        if profile_id is None:
            return ()
        return self._store.list_fairness_reviews(
            profile_id,
            observation_id,
            include_history,
        )


def _normalize_review(review: FairnessReviewInput) -> FairnessReviewInput:
    if isinstance(review.observation_id, bool) or review.observation_id <= 0:
        raise ValidationError("INVALID_OBSERVATION_ID", "observation-id必须是正整数")
    summary = review.summary.strip()
    if not summary or len(summary) > 2000:
        raise ValidationError("INVALID_FAIRNESS_SUMMARY", "公平性结论不得为空且最多2000字符")
    evidence = tuple(_normalize_evidence(item) for item in review.evidence)
    if review.conclusion is not FairnessReviewConclusion.INSUFFICIENT and not evidence:
        raise ValidationError(
            "FAIRNESS_EVIDENCE_REQUIRED",
            "非insufficient结论必须至少包含一条可复核证据快照",
        )
    return FairnessReviewInput(
        observation_id=review.observation_id,
        conclusion=review.conclusion,
        summary=summary,
        evidence=evidence,
    )


def _normalize_evidence(item: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        normalized = dict(item)
    except (TypeError, ValueError) as error:
        raise ValidationError("INVALID_FAIRNESS_EVIDENCE", "公平性证据必须是JSON对象") from error
    required_text = (
        "source_title",
        "source_url",
        "content_sha256",
        "retrieved_date",
        "excerpt",
    )
    for key in required_text:
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(
                "INVALID_FAIRNESS_EVIDENCE",
                f"公平性证据缺少非空字段：{key}",
            )
        normalized[key] = value.strip()
    if not _SHA256_PATTERN.fullmatch(str(normalized["content_sha256"])):
        raise ValidationError(
            "INVALID_FAIRNESS_EVIDENCE_HASH",
            "公平性证据content_sha256必须是64位十六进制",
        )
    normalized["content_sha256"] = str(normalized["content_sha256"]).lower()
    try:
        date.fromisoformat(str(normalized["retrieved_date"]))
    except ValueError as error:
        raise ValidationError(
            "INVALID_FAIRNESS_EVIDENCE_DATE",
            "公平性证据retrieved_date必须是ISO日期",
        ) from error
    if normalized.get("source_type") not in _SOURCE_TYPES:
        raise ValidationError(
            "INVALID_FAIRNESS_SOURCE_TYPE",
            "公平性证据source_type不受支持",
            {"allowed": sorted(_SOURCE_TYPES)},
        )
    if normalized.get("signal") not in _SIGNALS:
        raise ValidationError(
            "INVALID_FAIRNESS_SIGNAL",
            "公平性证据signal不受支持",
            {"allowed": sorted(_SIGNALS)},
        )
    return normalized
