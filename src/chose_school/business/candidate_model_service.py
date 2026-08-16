from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from uuid import UUID

from chose_school.business.candidate_model_port import CandidateModelStore
from chose_school.domain.candidate_model import (
    CandidateProfileFitDimensionInput,
    CandidateProfileFitGapInput,
    CandidateProfileFitReviewInput,
    CandidateStrategyBucket,
    CandidateTargetAction,
    CandidateTargetBasis,
    CandidateTargetVersionInput,
    ComparabilityConclusion,
    ComparabilityEvidenceReference,
    ComparabilityEvidenceRole,
    IdentityDimensionConclusion,
    KnownPreferenceFitConclusion,
    ProfileFitDimensionStatus,
    ProfileFitGapImpact,
    ProfileFitGapStatus,
    ProjectHistoryComparabilityReviewInput,
    SpecialPlanHandling,
)
from chose_school.domain.errors import EntityNotFoundError, ValidationError
from chose_school.domain.models import Settings


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_FACT_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{1,159}$")
_GAP_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_IDENTITY_SCHEMA = "candidate-target-identity-v1"
_DIMENSION_SCHEMA = "project-history-dimensions-v1"
_UNSPECIFIED = "unspecified"
_IDENTITY_DIMENSIONS = (
    "school",
    "college",
    "program_code",
    "program_name",
    "direction",
    "campus",
    "training_location",
    "study_mode",
    "training_type",
    "admission_type",
    "degree_type",
    "training_arrangement",
)
_PROFILE_FIT_INPUT_SCHEMA = "candidate-profile-input-v1"
_PROFILE_FIT_DIMENSION_SCHEMA = "candidate-profile-fit-dimensions-v1"
_PROFILE_FIT_DIMENSIONS = (
    "institution",
    "program_code",
    "region",
    "training_location",
    "tuition",
    "joint_training",
    "retest_format",
    "school_tier_strategy",
    "admission_fairness",
    "preparation_timing",
)


class CandidateModelService:
    """Version candidate identities and historical-comparability judgements.

    It deliberately does not rank schools or infer admission probability.
    """

    def __init__(self, store: CandidateModelStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def add_candidate_target_version(
        self,
        target: CandidateTargetVersionInput,
        trace_id: str,
    ) -> int:
        _validate_trace_id(trace_id)
        _validate_year(target.target_year)
        reason = _bounded_text(target.reason, "reason", 2000)
        supersedes_id = _optional_positive_id(
            target.supersedes_version_id, "supersedes_version_id"
        )
        if not isinstance(target.target_basis, CandidateTargetBasis):
            raise ValidationError("INVALID_TARGET_BASIS", "候选目标依据不受支持")
        if not isinstance(target.action, CandidateTargetAction):
            raise ValidationError("INVALID_TARGET_ACTION", "候选目标动作不受支持")

        profile = self._store.find_profile_context(self._settings.profile_key)
        if profile is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        if int(profile["target_exam_year"]) != target.target_year:
            raise ValidationError(
                "TARGET_YEAR_PROFILE_MISMATCH",
                "候选目标年份必须与个人画像目标考试年份一致",
            )

        identity = _canonical_identity(
            str(profile["profile_key"]), target.target_year, target.identity
        )
        target_project_id: int | None = None
        observation_id = _optional_positive_id(
            target.target_observation_id, "target_observation_id"
        )
        if target.target_basis is CandidateTargetBasis.RESEARCH_HYPOTHESIS:
            if observation_id is not None:
                raise ValidationError(
                    "RESEARCH_TARGET_MUST_NOT_BIND_OBSERVATION",
                    "研究假设候选不得绑定任何本地项目或年度观测行",
                )
        else:
            if observation_id is None:
                raise ValidationError(
                    "OFFICIAL_TARGET_OBSERVATION_REQUIRED",
                    "正式候选必须绑定目标年度官方目录观测",
                )
            observation = self._store.find_observation_context(observation_id)
            if observation is None:
                raise EntityNotFoundError(
                    "OBSERVATION_NOT_FOUND", f"项目年度观测不存在：{observation_id}"
                )
            if (
                observation["admission_year"] is None
                or int(observation["admission_year"]) != target.target_year
            ):
                raise ValidationError(
                    "OFFICIAL_TARGET_YEAR_MISMATCH",
                    "正式候选观测必须与目标年份相同",
                )
            if int(observation["official_catalog_source_count"]) < 1:
                raise ValidationError(
                    "OFFICIAL_TARGET_CATALOG_EVIDENCE_REQUIRED",
                    "正式候选必须具有同年度官方目录内容哈希",
                )
            mismatches = [
                dimension
                for dimension in _IDENTITY_DIMENSIONS
                if identity[dimension] != observation[dimension]
            ]
            if mismatches:
                raise ValidationError(
                    "OFFICIAL_TARGET_CANONICAL_IDENTITY_MISMATCH",
                    "正式候选规范身份与绑定观测不一致",
                    {"dimensions": mismatches},
                )
            target_project_id = int(observation["project_id"])

        identity_json = canonical_json(identity)
        identity_sha256 = sha256_text(identity_json)
        candidate_key = f"candidate-v1:{identity_sha256}"
        version_number = 1
        if supersedes_id is not None:
            predecessor = self._store.find_candidate_target_context(supersedes_id)
            if predecessor is None:
                raise EntityNotFoundError(
                    "CANDIDATE_TARGET_VERSION_NOT_FOUND",
                    f"候选目标前序版本不存在：{supersedes_id}",
                )
            if predecessor["candidate_key"] != candidate_key:
                raise ValidationError(
                    "CANDIDATE_TARGET_CHAIN_IDENTITY_MISMATCH",
                    "候选目标后继版本必须延续同一跨库规范身份",
                )
            version_number = int(predecessor["version_number"]) + 1

        normalized = CandidateTargetVersionInput(
            target_year=target.target_year,
            identity=target.identity,
            target_basis=target.target_basis,
            action=target.action,
            reason=reason,
            target_observation_id=observation_id,
            supersedes_version_id=supersedes_id,
        )
        return self._store.add_candidate_target_version(
            int(profile["profile_id"]),
            normalized,
            identity,
            identity_json,
            identity_sha256,
            candidate_key,
            target_project_id,
            version_number,
            trace_id,
        )

    def add_comparability_review(
        self,
        review: ProjectHistoryComparabilityReviewInput,
        trace_id: str,
    ) -> int:
        _validate_trace_id(trace_id)
        _positive_id(review.candidate_target_version_id, "candidate_target_version_id")
        _positive_id(review.historical_observation_id, "historical_observation_id")
        supersedes_id = _optional_positive_id(
            review.supersedes_review_id, "supersedes_review_id"
        )
        summary = _bounded_text(review.summary, "summary", 4000)
        if not isinstance(review.conclusion, ComparabilityConclusion):
            raise ValidationError(
                "INVALID_COMPARABILITY_CONCLUSION", "跨年可比性结论不受支持"
            )

        target = self._store.find_candidate_target_context(
            review.candidate_target_version_id
        )
        if target is None:
            raise EntityNotFoundError(
                "CANDIDATE_TARGET_VERSION_NOT_FOUND",
                f"候选目标版本不存在：{review.candidate_target_version_id}",
            )
        historical = self._store.find_observation_context(
            review.historical_observation_id
        )
        if historical is None:
            raise EntityNotFoundError(
                "OBSERVATION_NOT_FOUND",
                f"历史项目年度观测不存在：{review.historical_observation_id}",
            )
        if historical["admission_year"] is None or int(
            historical["admission_year"]
        ) >= int(target["target_year"]):
            raise ValidationError(
                "HISTORICAL_YEAR_NOT_EARLIER",
                "历史观测必须早于候选目标版本年份",
            )

        dimensions = _dimension_contract(review, target, historical)
        dimension_json = canonical_json(dimensions)
        dimension_sha256 = sha256_text(dimension_json)
        evidence, sources = self._evidence_bundle(
            review.evidence,
            target,
            historical,
            review.historical_observation_id,
        )
        evidence_json = canonical_json(evidence)
        evidence_sha256 = sha256_text(evidence_json)
        _validate_comparable(review.conclusion, target, dimensions, evidence, sources)

        sequence = 1
        if supersedes_id is not None:
            predecessor = self._store.find_comparability_review_context(
                supersedes_id
            )
            if predecessor is None:
                raise EntityNotFoundError(
                    "COMPARABILITY_REVIEW_NOT_FOUND",
                    f"跨年可比性前序审查不存在：{supersedes_id}",
                )
            if (
                int(predecessor["candidate_target_version_id"])
                != review.candidate_target_version_id
                or int(predecessor["historical_observation_id"])
                != review.historical_observation_id
            ):
                raise ValidationError(
                    "COMPARABILITY_REVIEW_CHAIN_IDENTITY_MISMATCH",
                    "跨年审查后继必须绑定完全相同的候选版本和历史观测",
                )
            sequence = int(predecessor["review_sequence"]) + 1

        normalized = ProjectHistoryComparabilityReviewInput(
            candidate_target_version_id=review.candidate_target_version_id,
            historical_observation_id=review.historical_observation_id,
            conclusion=review.conclusion,
            dimensions=review.dimensions,
            evidence=review.evidence,
            summary=summary,
            supersedes_review_id=supersedes_id,
        )
        return self._store.add_comparability_review(
            normalized,
            dimension_json,
            dimension_sha256,
            evidence_json,
            evidence_sha256,
            sequence,
            trace_id,
        )

    def list_candidate_targets(
        self, include_history: bool = False
    ) -> Sequence[Mapping[str, Any]]:
        profile = self._store.find_profile_context(self._settings.profile_key)
        if profile is None:
            return ()
        return self._store.list_candidate_targets(
            int(profile["profile_id"]), include_history
        )

    def add_profile_fit_review(
        self,
        review: CandidateProfileFitReviewInput,
        trace_id: str,
    ) -> int:
        """Freeze a profile-fit interpretation without assigning an admit role."""

        _validate_trace_id(trace_id)
        _positive_id(
            review.candidate_target_version_id, "candidate_target_version_id"
        )
        supersedes_id = _optional_positive_id(
            review.supersedes_review_id, "supersedes_review_id"
        )
        summary = _bounded_text(review.summary, "summary", 4000)
        if not isinstance(review.strategy_bucket, CandidateStrategyBucket):
            raise ValidationError(
                "INVALID_CANDIDATE_STRATEGY_BUCKET",
                "候选研究策略桶不受支持",
            )
        if not isinstance(review.known_preference_fit, KnownPreferenceFitConclusion):
            raise ValidationError(
                "INVALID_KNOWN_PREFERENCE_FIT",
                "已知偏好适配结论不受支持",
            )

        profile = self._store.find_profile_context(self._settings.profile_key)
        if profile is None:
            raise EntityNotFoundError(
                "PROFILE_NOT_FOUND",
                "个人画像尚未初始化，请先运行 init",
                {"profile_key": self._settings.profile_key},
            )
        profile_id = int(profile["profile_id"])
        target = self._store.find_candidate_target_context(
            review.candidate_target_version_id
        )
        if target is None:
            raise EntityNotFoundError(
                "CANDIDATE_TARGET_VERSION_NOT_FOUND",
                f"候选目标版本不存在：{review.candidate_target_version_id}",
            )
        if int(target["profile_id"]) != profile_id:
            raise ValidationError(
                "CANDIDATE_PROFILE_MISMATCH",
                "候选画像适配审查必须绑定当前个人画像",
            )

        preference_event_ids = tuple(
            sorted(self._store.list_current_preference_event_ids(profile_id))
        )
        context_event_ids = tuple(
            sorted(self._store.list_current_context_event_ids(profile_id))
        )
        input_snapshot = {
            "schema": _PROFILE_FIT_INPUT_SCHEMA,
            "profile_id": profile_id,
            "candidate_target_version_id": review.candidate_target_version_id,
            "candidate_key": str(target["candidate_key"]),
            "preference_event_ids": list(preference_event_ids),
            "context_event_ids": list(context_event_ids),
        }
        input_snapshot_json = canonical_json(input_snapshot)

        dimensions = _profile_fit_dimension_contract(
            review.dimensions,
            frozenset(preference_event_ids),
            frozenset(context_event_ids),
        )
        gaps = _profile_fit_gap_contract(review.evidence_gaps)
        _validate_profile_fit_conclusion(
            review.known_preference_fit, dimensions["dimensions"], gaps
        )
        dimension_results_json = canonical_json(dimensions)
        evidence_gaps_json = canonical_json(gaps)

        sequence = 1
        if supersedes_id is not None:
            predecessor = self._store.find_profile_fit_review_context(supersedes_id)
            if predecessor is None:
                raise EntityNotFoundError(
                    "CANDIDATE_PROFILE_FIT_REVIEW_NOT_FOUND",
                    f"画像适配前序审查不存在：{supersedes_id}",
                )
            if (
                int(predecessor["profile_id"]) != profile_id
                or int(predecessor["candidate_target_version_id"])
                != review.candidate_target_version_id
            ):
                raise ValidationError(
                    "CANDIDATE_PROFILE_FIT_CHAIN_IDENTITY_MISMATCH",
                    "画像适配后继必须绑定完全相同的候选目标版本",
                )
            sequence = int(predecessor["review_sequence"]) + 1

        normalized = CandidateProfileFitReviewInput(
            candidate_target_version_id=review.candidate_target_version_id,
            strategy_bucket=review.strategy_bucket,
            known_preference_fit=review.known_preference_fit,
            dimensions=review.dimensions,
            evidence_gaps=review.evidence_gaps,
            summary=summary,
            supersedes_review_id=supersedes_id,
        )
        return self._store.add_profile_fit_review(
            profile_id,
            normalized,
            input_snapshot_json,
            sha256_text(input_snapshot_json),
            dimension_results_json,
            sha256_text(dimension_results_json),
            evidence_gaps_json,
            sha256_text(evidence_gaps_json),
            sequence,
            trace_id,
        )

    def list_comparability_reviews(
        self,
        candidate_target_version_id: int | None = None,
        include_history: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        if candidate_target_version_id is not None:
            _positive_id(candidate_target_version_id, "candidate_target_version_id")
        return self._store.list_comparability_reviews(
            candidate_target_version_id, include_history
        )

    def list_profile_fit_reviews(
        self,
        candidate_target_version_id: int | None = None,
        include_history: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        if candidate_target_version_id is not None:
            _positive_id(candidate_target_version_id, "candidate_target_version_id")
        return self._store.list_profile_fit_reviews(
            candidate_target_version_id, include_history
        )

    def _evidence_bundle(
        self,
        references: Sequence[ComparabilityEvidenceReference],
        target: Mapping[str, Any],
        historical: Mapping[str, Any],
        historical_observation_id: int,
    ) -> tuple[list[Mapping[str, Any]], Mapping[int, Mapping[str, Any]]]:
        seen: set[tuple[int, str]] = set()
        normalized: list[ComparabilityEvidenceReference] = []
        for reference in references:
            _positive_id(reference.source_id, "source_id")
            if not isinstance(reference.role, ComparabilityEvidenceRole):
                raise ValidationError(
                    "INVALID_COMPARABILITY_EVIDENCE_ROLE", "证据角色不受支持"
                )
            identity = (reference.source_id, reference.role.value)
            if identity in seen:
                raise ValidationError(
                    "DUPLICATE_COMPARABILITY_EVIDENCE", "同一来源角色不得重复"
                )
            seen.add(identity)
            normalized.append(reference)
        source_ids = sorted({reference.source_id for reference in normalized})
        rows = self._store.find_evidence_source_contexts(
            source_ids,
            target["target_observation_id"],
            historical_observation_id,
        )
        sources = {int(row["source_id"]): row for row in rows}
        missing = [source_id for source_id in source_ids if source_id not in sources]
        if missing:
            raise EntityNotFoundError(
                "EVIDENCE_SOURCE_NOT_FOUND", "跨年证据来源不存在", {"source_ids": missing}
            )

        bundle: list[Mapping[str, Any]] = []
        for reference in normalized:
            source = sources[reference.source_id]
            content_hash = source["content_sha256"]
            if not isinstance(content_hash, str) or not _SHA256_PATTERN.fullmatch(
                content_hash
            ):
                raise ValidationError(
                    "COMPARABILITY_EVIDENCE_HASH_REQUIRED",
                    "跨年证据必须具有小写内容 SHA-256",
                    {"source_id": reference.source_id},
                )
            expected_year = (
                int(target["target_year"])
                if reference.role is ComparabilityEvidenceRole.TARGET
                else int(historical["admission_year"])
            )
            if source["applicable_year"] is None or int(
                source["applicable_year"]
            ) != expected_year:
                raise ValidationError(
                    "COMPARABILITY_EVIDENCE_YEAR_MISMATCH",
                    "证据年份必须与目标年或历史年角色一致",
                )
            if reference.role is ComparabilityEvidenceRole.TARGET:
                if not bool(source["supports_target"]):
                    raise ValidationError(
                        "TARGET_EVIDENCE_LINK_REQUIRED", "目标年证据必须支持目标观测"
                    )
            elif not bool(source["supports_historical"]):
                raise ValidationError(
                    "HISTORICAL_EVIDENCE_LINK_REQUIRED", "历史证据必须支持历史观测"
                )
            document_type = source["document_type"]
            if not isinstance(document_type, str) or not document_type.strip():
                raise ValidationError(
                    "COMPARABILITY_DOCUMENT_TYPE_REQUIRED", "证据必须具有文档类型"
                )
            bundle.append(
                {
                    "role": reference.role.value,
                    "source_id": reference.source_id,
                    "content_sha256": content_hash,
                    "document_type": document_type,
                    "applicable_year": expected_year,
                    "source_url": source["url"],
                }
            )
        bundle.sort(key=lambda item: (str(item["role"]), int(item["source_id"])))
        return bundle, sources


def _canonical_identity(
    profile_key: str, target_year: int, identity: Any
) -> Mapping[str, str | int]:
    return {
        "schema": _IDENTITY_SCHEMA,
        "profile_key": _bounded_text(profile_key, "profile_key", 120),
        "target_year": target_year,
        "school": _bounded_text(identity.school, "school", 200),
        "college": _bounded_text(identity.college, "college", 200),
        "program_code": _bounded_text(identity.program_code, "program_code", 40),
        "program_name": _bounded_text(identity.program_name, "program_name", 200),
        "direction": _optional_identity(identity.direction, 300),
        "campus": _optional_identity(identity.campus, 200),
        "training_location": _optional_identity(identity.training_location, 200),
        "study_mode": _optional_identity(identity.study_mode, 80),
        "training_type": _optional_identity(identity.training_type, 120),
        "admission_type": _optional_identity(identity.admission_type, 120),
        "degree_type": _optional_identity(identity.degree_type, 120),
        "training_arrangement": _optional_identity(identity.training_arrangement, 300),
    }


def _dimension_contract(
    review: ProjectHistoryComparabilityReviewInput,
    target: Mapping[str, Any],
    historical: Mapping[str, Any],
) -> Mapping[str, Any]:
    dimensions = review.dimensions
    population_scope = _bounded_text(dimensions.population_scope, "population_scope", 120)
    statistic_scope = _bounded_text(dimensions.statistic_scope, "statistic_scope", 120)
    if not isinstance(dimensions.special_plan_handling, SpecialPlanHandling):
        raise ValidationError("INVALID_SPECIAL_PLAN_HANDLING", "专项计划口径不受支持")
    fact_keys = sorted({_fact_key(value) for value in dimensions.fact_keys})
    decisions: dict[str, Any] = {}
    for decision in dimensions.identity_decisions:
        dimension = _bounded_text(decision.dimension, "dimension", 80)
        if dimension not in _IDENTITY_DIMENSIONS or dimension in decisions:
            raise ValidationError(
                "INVALID_IDENTITY_DIMENSION_SET", "身份维度必须完整且不得重复"
            )
        if not isinstance(decision.conclusion, IdentityDimensionConclusion):
            raise ValidationError(
                "INVALID_IDENTITY_DIMENSION_CONCLUSION", "身份维度结论不受支持"
            )
        rationale = decision.rationale.strip() if isinstance(decision.rationale, str) else ""
        target_value = str(target[dimension])
        historical_value = str(historical[dimension])
        if decision.conclusion is IdentityDimensionConclusion.MATCH and target_value != historical_value:
            raise ValidationError(
                "IDENTITY_MATCH_VALUE_MISMATCH", f"{dimension} 的两侧值不同，不能标记 match"
            )
        if decision.conclusion is IdentityDimensionConclusion.EQUIVALENT and not rationale:
            raise ValidationError(
                "IDENTITY_EQUIVALENCE_RATIONALE_REQUIRED",
                f"{dimension} 标记 equivalent 时必须说明依据",
            )
        decisions[dimension] = {
            "target": target_value,
            "historical": historical_value,
            "conclusion": decision.conclusion.value,
            "rationale": rationale,
        }
    if set(decisions) != set(_IDENTITY_DIMENSIONS):
        raise ValidationError(
            "INCOMPLETE_IDENTITY_DIMENSIONS",
            "跨年审查必须逐项裁决全部规范身份维度",
            {"missing": sorted(set(_IDENTITY_DIMENSIONS) - set(decisions))},
        )
    return {
        "schema": _DIMENSION_SCHEMA,
        "population_scope": population_scope,
        "statistic_scope": statistic_scope,
        "special_plan_handling": dimensions.special_plan_handling.value,
        "fact_keys": fact_keys,
        "identity_dimensions": decisions,
    }


def _validate_comparable(
    conclusion: ComparabilityConclusion,
    target: Mapping[str, Any],
    dimensions: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    sources: Mapping[int, Mapping[str, Any]],
) -> None:
    if conclusion is not ComparabilityConclusion.COMPARABLE:
        return
    if (
        target["target_basis"] != CandidateTargetBasis.OFFICIAL_OBSERVATION.value
        or target["action"] != CandidateTargetAction.ACTIVE.value
    ):
        raise ValidationError(
            "COMPARABLE_REQUIRES_ACTIVE_OFFICIAL_TARGET",
            "comparable 必须绑定当前版本中的 active 正式目标观测",
        )
    if not dimensions["fact_keys"]:
        raise ValidationError("COMPARABLE_FACT_KEYS_REQUIRED", "comparable 必须声明事实键")
    if dimensions["special_plan_handling"] == SpecialPlanHandling.UNRESOLVED.value:
        raise ValidationError(
            "COMPARABLE_SPECIAL_SCOPE_UNRESOLVED", "专项计划口径未解决时不得 comparable"
        )
    if any(
        item["conclusion"] not in {"match", "equivalent"}
        for item in dimensions["identity_dimensions"].values()
    ):
        raise ValidationError(
            "COMPARABLE_IDENTITY_DIMENSION_GAP", "所有身份维度均须 match 或 equivalent"
        )
    if {item["role"] for item in evidence} != {"target", "historical"}:
        raise ValidationError(
            "COMPARABLE_BOTH_YEAR_EVIDENCE_REQUIRED", "必须同时具有目标年和历史年证据"
        )
    for item in evidence:
        source = sources[int(item["source_id"])]
        if (
            source["evidence_grade"] != "official"
            or not isinstance(source["url"], str)
            or not source["url"].startswith("https://")
        ):
            raise ValidationError(
                "COMPARABLE_OFFICIAL_EVIDENCE_REQUIRED", "两侧证据均须为可复核官方来源"
            )


def _profile_fit_dimension_contract(
    inputs: Sequence[CandidateProfileFitDimensionInput],
    current_preference_event_ids: frozenset[int],
    current_context_event_ids: frozenset[int],
) -> Mapping[str, Any]:
    dimensions: dict[str, Any] = {}
    for item in inputs:
        dimension = _bounded_text(item.dimension, "profile_fit_dimension", 80)
        if dimension not in _PROFILE_FIT_DIMENSIONS or dimension in dimensions:
            raise ValidationError(
                "INVALID_PROFILE_FIT_DIMENSION_SET",
                "画像适配维度必须完整、受控且不得重复",
            )
        if not isinstance(item.status, ProfileFitDimensionStatus):
            raise ValidationError(
                "INVALID_PROFILE_FIT_DIMENSION_STATUS",
                f"{dimension} 的画像适配状态不受支持",
            )
        rationale = _bounded_text(item.rationale, "rationale", 1000)
        preference_ids = _unique_positive_ids(
            item.preference_event_ids, "preference_event_ids"
        )
        context_ids = _unique_positive_ids(
            item.context_event_ids, "context_event_ids"
        )
        missing_preferences = sorted(
            set(preference_ids) - current_preference_event_ids
        )
        missing_context = sorted(set(context_ids) - current_context_event_ids)
        if missing_preferences or missing_context:
            raise ValidationError(
                "PROFILE_FIT_EVENT_REFERENCE_OUTSIDE_CURRENT_SNAPSHOT",
                "画像适配维度只能引用当前画像快照中的事件",
                {
                    "preference_event_ids": missing_preferences,
                    "context_event_ids": missing_context,
                },
            )
        if (
            item.status
            in {
                ProfileFitDimensionStatus.PASS,
                ProfileFitDimensionStatus.CONDITIONAL,
                ProfileFitDimensionStatus.HARD_CONFLICT,
            }
            and not preference_ids
            and not context_ids
        ):
            raise ValidationError(
                "PROFILE_FIT_DIMENSION_EVIDENCE_REQUIRED",
                f"{dimension} 的明确适配结论必须引用画像快照事件",
            )
        dimensions[dimension] = {
            "status": item.status.value,
            "preference_event_ids": list(preference_ids),
            "context_event_ids": list(context_ids),
            "rationale": rationale,
        }
    if set(dimensions) != set(_PROFILE_FIT_DIMENSIONS):
        raise ValidationError(
            "INCOMPLETE_PROFILE_FIT_DIMENSIONS",
            "画像适配审查必须逐项覆盖全部受控维度",
            {"missing": sorted(set(_PROFILE_FIT_DIMENSIONS) - set(dimensions))},
        )
    return {
        "schema": _PROFILE_FIT_DIMENSION_SCHEMA,
        "dimensions": dimensions,
    }


def _profile_fit_gap_contract(
    inputs: Sequence[CandidateProfileFitGapInput],
) -> list[Mapping[str, str]]:
    gaps: list[Mapping[str, str]] = []
    seen: set[str] = set()
    for item in inputs:
        code = item.code.strip() if isinstance(item.code, str) else ""
        if not _GAP_CODE_PATTERN.fullmatch(code) or code in seen:
            raise ValidationError(
                "INVALID_PROFILE_FIT_GAP_CODE",
                "画像适配证据缺口代码必须受控且不得重复",
                {"code": code},
            )
        if not isinstance(item.status, ProfileFitGapStatus):
            raise ValidationError(
                "INVALID_PROFILE_FIT_GAP_STATUS", "画像适配证据缺口状态不受支持"
            )
        if not isinstance(item.impact, ProfileFitGapImpact):
            raise ValidationError(
                "INVALID_PROFILE_FIT_GAP_IMPACT", "画像适配证据缺口影响不受支持"
            )
        seen.add(code)
        gaps.append(
            {
                "code": code,
                "status": item.status.value,
                "impact": item.impact.value,
                "rationale": _bounded_text(item.rationale, "rationale", 1000),
            }
        )
    gaps.sort(key=lambda item: item["code"])
    return gaps


def _validate_profile_fit_conclusion(
    conclusion: KnownPreferenceFitConclusion,
    dimensions: Mapping[str, Mapping[str, Any]],
    gaps: Sequence[Mapping[str, str]],
) -> None:
    statuses = {str(item["status"]) for item in dimensions.values()}
    hard_conflict = ProfileFitDimensionStatus.HARD_CONFLICT.value in statuses
    unresolved = bool(
        statuses
        & {
            ProfileFitDimensionStatus.CONDITIONAL.value,
            ProfileFitDimensionStatus.NOT_EVALUABLE.value,
        }
    ) or any(
        item["status"]
        in {ProfileFitGapStatus.MISSING.value, ProfileFitGapStatus.PARTIAL.value}
        for item in gaps
    )
    unresolved_hard_gap = any(
        item["impact"] == ProfileFitGapImpact.SELECTION_GATE.value
        and item["status"]
        in {ProfileFitGapStatus.MISSING.value, ProfileFitGapStatus.PARTIAL.value}
        for item in gaps
    )
    if conclusion is KnownPreferenceFitConclusion.CONFLICT and not hard_conflict:
        raise ValidationError(
            "PROFILE_FIT_CONFLICT_SIGNAL_REQUIRED",
            "conflict 结论必须具有至少一个硬偏好冲突",
        )
    if conclusion is not KnownPreferenceFitConclusion.CONFLICT and hard_conflict:
        raise ValidationError(
            "PROFILE_FIT_CONFLICT_CONCLUSION_REQUIRED",
            "存在硬偏好冲突时结论必须为 conflict",
        )
    if conclusion is KnownPreferenceFitConclusion.COMPATIBLE and (
        unresolved or unresolved_hard_gap
    ):
        raise ValidationError(
            "PROFILE_FIT_COMPATIBLE_REQUIRES_COMPLETE_EVIDENCE",
            "存在未解决条件时不得写 compatible",
        )
    if conclusion is KnownPreferenceFitConclusion.CONDITIONAL and not unresolved:
        raise ValidationError(
            "PROFILE_FIT_CONDITIONAL_GAP_REQUIRED",
            "conditional 结论必须明确记录未解决条件",
        )
    if (
        conclusion is KnownPreferenceFitConclusion.INSUFFICIENT
        and ProfileFitDimensionStatus.NOT_EVALUABLE.value not in statuses
    ):
        raise ValidationError(
            "PROFILE_FIT_INSUFFICIENT_INPUT_GAP_REQUIRED",
            "insufficient 结论必须具有无法评估的画像维度",
        )


def _unique_positive_ids(values: Sequence[int], field: str) -> tuple[int, ...]:
    normalized = tuple(sorted(_positive_id(value, field) for value in values))
    if len(normalized) != len(set(normalized)):
        raise ValidationError(
            "DUPLICATE_PROFILE_FIT_EVENT_REFERENCE",
            f"{field} 不得包含重复事件",
        )
    return normalized


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fact_key(value: Any) -> str:
    if not isinstance(value, str) or not _FACT_KEY_PATTERN.fullmatch(value.strip()):
        raise ValidationError("INVALID_COMPARABILITY_FACT_KEY", "比较事实键格式无效")
    return value.strip()


def _optional_identity(value: Any, maximum: int) -> str:
    if value is None:
        return _UNSPECIFIED
    return _bounded_text(value, "identity_dimension", maximum)


def _bounded_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValidationError(
            "INVALID_TEXT_FIELD", f"{field} 必须为 1 至 {maximum} 个字符"
        )
    return value.strip()


def _positive_id(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError("INVALID_ENTITY_ID", f"{field} 必须是正整数")
    return value


def _optional_positive_id(value: Any, field: str) -> int | None:
    return None if value is None else _positive_id(value, field)


def _validate_year(value: Any) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 2000 <= value <= 2100:
        raise ValidationError("INVALID_TARGET_YEAR", "目标年份必须是 2000 至 2100 的整数")


def _validate_trace_id(value: Any) -> None:
    if not isinstance(value, str):
        raise ValidationError("TRACE_ID_REQUIRED", "写入必须提供规范 TraceId")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise ValidationError("INVALID_TRACE_ID", "TraceId 必须是规范 UUID") from error
    if str(parsed) != value:
        raise ValidationError("INVALID_TRACE_ID", "TraceId 必须是小写规范 UUID")
