from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from chose_school.domain.candidate_model import (
    CandidateProfileFitReviewInput,
    CandidateTargetVersionInput,
    ProjectHistoryComparabilityReviewInput,
)


class CandidateModelStore(Protocol):
    def find_profile_context(self, profile_key: str) -> Mapping[str, Any] | None: ...

    def find_observation_context(
        self, observation_id: int
    ) -> Mapping[str, Any] | None: ...

    def find_candidate_target_context(
        self, candidate_target_version_id: int
    ) -> Mapping[str, Any] | None: ...

    def find_comparability_review_context(
        self, review_id: int
    ) -> Mapping[str, Any] | None: ...

    def find_profile_fit_review_context(
        self, review_id: int
    ) -> Mapping[str, Any] | None: ...

    def list_current_preference_event_ids(self, profile_id: int) -> Sequence[int]: ...

    def list_current_context_event_ids(self, profile_id: int) -> Sequence[int]: ...

    def find_evidence_source_contexts(
        self,
        source_ids: Sequence[int],
        target_observation_id: int | None,
        historical_observation_id: int,
    ) -> Sequence[Mapping[str, Any]]: ...

    def add_candidate_target_version(
        self,
        profile_id: int,
        target: CandidateTargetVersionInput,
        canonical_identity: Mapping[str, str | int],
        identity_canonical_json: str,
        identity_canonical_sha256: str,
        candidate_key: str,
        target_project_id: int | None,
        version_number: int,
        trace_id: str,
    ) -> int: ...

    def add_comparability_review(
        self,
        review: ProjectHistoryComparabilityReviewInput,
        dimension_contract_json: str,
        dimension_contract_sha256: str,
        evidence_bundle_json: str,
        evidence_bundle_sha256: str,
        review_sequence: int,
        trace_id: str,
    ) -> int: ...

    def add_profile_fit_review(
        self,
        profile_id: int,
        review: CandidateProfileFitReviewInput,
        input_snapshot_json: str,
        input_snapshot_sha256: str,
        dimension_results_json: str,
        dimension_results_sha256: str,
        evidence_gaps_json: str,
        evidence_gaps_sha256: str,
        review_sequence: int,
        trace_id: str,
    ) -> int: ...

    def list_candidate_targets(
        self, profile_id: int, include_history: bool
    ) -> Sequence[Mapping[str, Any]]: ...

    def list_comparability_reviews(
        self,
        candidate_target_version_id: int | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]: ...

    def list_profile_fit_reviews(
        self,
        candidate_target_version_id: int | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]: ...
