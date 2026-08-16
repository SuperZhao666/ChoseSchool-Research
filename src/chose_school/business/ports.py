from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from chose_school.domain.enums import Strict22408Status
from chose_school.domain.models import (
    ApplicantAchievementAddResult,
    ApplicantAchievementInput,
    ApplicantContextEventInput,
    CatalogArchive,
    CatalogFilter,
    FairnessReviewInput,
    ImportResult,
    MachineTestInput,
    MockExamLedgerAddResult,
    MockExamLedgerInput,
    MockExamInput,
    NormalizedRow,
    OfficialProjectObservationInput,
    OfficialProjectObservationResult,
    PolicyEventAddResult,
    PolicyEventFilter,
    PolicyEventInput,
    PreferenceEventInput,
    SelectionReadinessFacts,
    SubjectVerificationInput,
    FactClaimInput,
    TypedFactValue,
)


class CatalogArchiveReader(Protocol):
    def source_sha256(self, archive_path: Path) -> str: ...

    def read(self, archive_path: Path) -> CatalogArchive: ...


@dataclass(frozen=True)
class SchemaStatus:
    is_current: bool
    current_version: int | None
    required_version: int
    pending_versions: tuple[int, ...]
    mismatch_reason: str | None = None


class SchemaManager(Protocol):
    @property
    def path(self) -> Path: ...

    def migrate(self) -> list[int]: ...

    def inspect_schema(self) -> SchemaStatus: ...


class CatalogImportStore(Protocol):
    def find_successful_batch(
        self, source_sha256: str, importer_version: str
    ) -> str | None: ...

    def start_batch(
        self,
        batch_id: str,
        trace_id: str,
        archive_path: Path,
        source_sha256: str,
        importer_version: str,
    ) -> None: ...

    def record_duplicate_batch(
        self,
        batch_id: str,
        trace_id: str,
        archive_path: Path,
        source_sha256: str,
        importer_version: str,
        duplicate_of: str,
    ) -> ImportResult: ...

    def persist_import(
        self,
        batch_id: str,
        source_sha256: str,
        archive: CatalogArchive,
        normalized_rows: Mapping[tuple[str, int], NormalizedRow],
    ) -> ImportResult: ...

    def mark_batch_failed(self, batch_id: str, error_message: str) -> None: ...


class CatalogQueryStore(Protocol):
    def summary(self) -> Mapping[str, Any]: ...

    def list_catalog(self, catalog_filter: CatalogFilter) -> Sequence[Mapping[str, Any]]: ...

    def list_issues(
        self,
        severity: str | None,
        status: str,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]: ...

    def doctor(self) -> Mapping[str, Any]: ...


class IssueResolutionStore(Protocol):
    def resolve_issue(self, issue_id: int, note: str, trace_id: str) -> None: ...


class FactStore(Protocol):
    def add_claim(
        self,
        claim: FactClaimInput,
        typed_value: TypedFactValue,
        trace_id: str,
    ) -> int: ...

    def resolve_claim(self, claim_id: int, reason: str, trace_id: str) -> int: ...

    def unresolve_claim(self, claim_id: int, reason: str, trace_id: str) -> int: ...

    def list_claims(self, observation_id: int) -> Sequence[Mapping[str, Any]]: ...

    def list_conflicts(self, limit: int) -> Sequence[Mapping[str, Any]]: ...


class SubjectVerificationStore(Protocol):
    def add_subject_verification(
        self,
        verification: SubjectVerificationInput,
        derived_status: Strict22408Status,
        trace_id: str,
    ) -> int: ...


class OfficialProjectObservationStore(Protocol):
    def add_official_observation(
        self,
        observation: OfficialProjectObservationInput,
        derived_status: Strict22408Status,
        trace_id: str,
    ) -> OfficialProjectObservationResult: ...


class PolicyEventStore(Protocol):
    def add_policy_event(
        self,
        event: PolicyEventInput,
        trace_id: str,
    ) -> PolicyEventAddResult: ...

    def list_policy_events(
        self,
        event_filter: PolicyEventFilter,
    ) -> Sequence[Mapping[str, Any]]: ...


class AssessmentStore(Protocol):
    def find_profile_id(self, profile_key: str) -> int | None: ...

    def ensure_default_profile(
        self,
        profile_key: str,
        undergraduate_school: str,
        undergraduate_major: str,
        target_year: int,
        politics_code: str,
        english_code: str,
        math_code: str,
        professional_code: str,
        target_degree_type: str,
        target_tier: str,
        trace_id: str,
    ) -> int: ...

    def add_mock_exam(
        self, profile_id: int, mock_exam: MockExamInput, trace_id: str
    ) -> int: ...

    def add_mock_exam_ledger(
        self,
        profile_id: int,
        mock_exam: MockExamLedgerInput,
        trace_id: str,
    ) -> MockExamLedgerAddResult: ...

    def list_mock_exam_sessions(
        self,
        profile_id: int,
        include_legacy: bool,
        eligible_only: bool,
        session_id: int | None,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]: ...

    def exclude_mock_exam(
        self,
        profile_id: int,
        session_id: int,
        reason: str,
        trace_id: str,
    ) -> int: ...

    def strict_mock_totals(self, profile_id: int) -> Sequence[Mapping[str, Any]]:
        """Return complete strict sessions ordered by taken_on and session id."""
        ...


class PreferenceStore(Protocol):
    def find_profile_id(self, profile_key: str) -> int | None: ...

    def add_preference_event(
        self,
        profile_id: int,
        preference: PreferenceEventInput,
        canonical_value_json: str,
        trace_id: str,
    ) -> int: ...

    def list_preferences(
        self,
        profile_id: int,
        dimension: str | None,
        subject_key: str | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]: ...


class ApplicantContextStore(Protocol):
    def find_profile_id(self, profile_key: str) -> int | None: ...

    def add_context_event(
        self,
        profile_id: int,
        event: ApplicantContextEventInput,
        canonical_value_json: str,
        trace_id: str,
    ) -> int: ...

    def list_context_events(
        self,
        profile_id: int,
        dimension: str | None,
        subject_key: str | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]: ...


class ApplicantAchievementStore(Protocol):
    def find_profile_id(self, profile_key: str) -> int | None: ...

    def add_achievement(
        self,
        profile_id: int,
        achievement: ApplicantAchievementInput,
        canonical_details_json: str,
        event_fingerprint: str,
        fingerprint_version: str,
        trace_id: str,
    ) -> ApplicantAchievementAddResult: ...

    def list_achievements(
        self,
        profile_id: int,
        category: str | None,
        achievement_year: int | None,
        achievement_key: str | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]: ...


class FairnessReviewStore(Protocol):
    def find_profile_id(self, profile_key: str) -> int | None: ...

    def observation_exists(self, observation_id: int) -> bool: ...

    def add_fairness_review(
        self,
        profile_id: int,
        review: FairnessReviewInput,
        review_version: str,
        canonical_evidence_json: str,
        trace_id: str,
    ) -> int: ...

    def list_fairness_reviews(
        self,
        profile_id: int,
        observation_id: int | None,
        include_history: bool,
    ) -> Sequence[Mapping[str, Any]]: ...


class MachineTestStore(Protocol):
    def find_profile_id(self, profile_key: str) -> int | None: ...

    def add_machine_test(
        self,
        profile_id: int,
        machine_test: MachineTestInput,
        trace_id: str,
    ) -> int: ...

    def list_machine_tests(
        self,
        profile_id: int,
        duration_minutes: int | None,
        language: str | None,
        problem_count: int | None,
        valid_only: bool,
    ) -> Sequence[Mapping[str, Any]]: ...


class SelectionReadinessStore(Protocol):
    def read_facts(
        self,
        profile_id: int | None,
        target_exam_year: int,
    ) -> SelectionReadinessFacts: ...
    FairnessReviewInput,
