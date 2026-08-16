from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CandidateTargetBasis(StrEnum):
    RESEARCH_HYPOTHESIS = "research_hypothesis"
    OFFICIAL_OBSERVATION = "official_observation"


class CandidateTargetAction(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class ComparabilityConclusion(StrEnum):
    COMPARABLE = "comparable"
    LIMITED = "limited"
    REJECTED = "rejected"
    INSUFFICIENT = "insufficient"


class ComparabilityEvidenceRole(StrEnum):
    TARGET = "target"
    HISTORICAL = "historical"


class SpecialPlanHandling(StrEnum):
    EXCLUDED = "excluded"
    INCLUDED = "included"
    SEPARATE = "separate"
    UNRESOLVED = "unresolved"


class IdentityDimensionConclusion(StrEnum):
    MATCH = "match"
    EQUIVALENT = "equivalent"
    DIFFERENT = "different"
    UNKNOWN = "unknown"


class CandidateStrategyBucket(StrEnum):
    """User-assigned research order, never an institutional fact or admit role."""

    PRIORITY_985_RESEARCH = "985_priority_research"
    HEDGE_211_RESEARCH = "211_hedge_research"
    NON_211_COMPARATOR_RESEARCH = "non_211_comparator_research"


class KnownPreferenceFitConclusion(StrEnum):
    COMPATIBLE = "compatible"
    CONDITIONAL = "conditional"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"


class ProfileFitDimensionStatus(StrEnum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    HARD_CONFLICT = "hard_conflict"
    NOT_EVALUABLE = "not_evaluable"
    NOT_APPLICABLE = "not_applicable"


class ProfileFitGapStatus(StrEnum):
    MISSING = "missing"
    PARTIAL = "partial"
    RESOLVED = "resolved"
    NOT_APPLICABLE = "not_applicable"


class ProfileFitGapImpact(StrEnum):
    SELECTION_GATE = "selection_gate"
    RESEARCH_CONDITION = "research_condition"
    ADVISORY = "advisory"


@dataclass(frozen=True)
class CandidateIdentityInput:
    school: str
    college: str
    program_code: str
    program_name: str
    direction: str | None = None
    campus: str | None = None
    training_location: str | None = None
    study_mode: str | None = None
    training_type: str | None = None
    admission_type: str | None = None
    degree_type: str | None = None
    training_arrangement: str | None = None


@dataclass(frozen=True)
class CandidateTargetVersionInput:
    target_year: int
    identity: CandidateIdentityInput
    target_basis: CandidateTargetBasis
    action: CandidateTargetAction
    reason: str
    target_observation_id: int | None = None
    supersedes_version_id: int | None = None


@dataclass(frozen=True)
class IdentityDimensionDecision:
    dimension: str
    conclusion: IdentityDimensionConclusion
    rationale: str


@dataclass(frozen=True)
class ComparabilityDimensionInput:
    population_scope: str
    statistic_scope: str
    special_plan_handling: SpecialPlanHandling
    fact_keys: tuple[str, ...]
    identity_decisions: tuple[IdentityDimensionDecision, ...]


@dataclass(frozen=True)
class ComparabilityEvidenceReference:
    source_id: int
    role: ComparabilityEvidenceRole


@dataclass(frozen=True)
class ProjectHistoryComparabilityReviewInput:
    candidate_target_version_id: int
    historical_observation_id: int
    conclusion: ComparabilityConclusion
    dimensions: ComparabilityDimensionInput
    evidence: tuple[ComparabilityEvidenceReference, ...]
    summary: str
    supersedes_review_id: int | None = None


@dataclass(frozen=True)
class CandidateProfileFitDimensionInput:
    dimension: str
    status: ProfileFitDimensionStatus
    rationale: str
    preference_event_ids: tuple[int, ...] = ()
    context_event_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class CandidateProfileFitGapInput:
    code: str
    status: ProfileFitGapStatus
    impact: ProfileFitGapImpact
    rationale: str


@dataclass(frozen=True)
class CandidateProfileFitReviewInput:
    candidate_target_version_id: int
    strategy_bucket: CandidateStrategyBucket
    known_preference_fit: KnownPreferenceFitConclusion
    dimensions: tuple[CandidateProfileFitDimensionInput, ...]
    evidence_gaps: tuple[CandidateProfileFitGapInput, ...]
    summary: str
    supersedes_review_id: int | None = None
