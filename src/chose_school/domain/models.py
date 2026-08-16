from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from chose_school.domain.enums import (
    AchievementCategory,
    AchievementEvidenceRelationship,
    AchievementParticipationType,
    AchievementScopeLevel,
    AchievementStage,
    AchievementVerificationStatus,
    ApplicantContextDimension,
    ApplicantEvidenceAccessScope,
    ApplicantEvidenceDocumentType,
    ApplicantEvidenceGrade,
    ApplicantEvidenceReviewMethod,
    ApplicantEvidenceStatus,
    EvidenceGrade,
    EvidenceDocumentType,
    FactDataType,
    FairnessReviewConclusion,
    IssueSeverity,
    MachineMeasurementStatus,
    MachineScoringMethod,
    MachineTestDifficulty,
    MockAttendanceStatus,
    MockDifficulty,
    MockInvalidReasonCode,
    MockPaperFamily,
    PolicyEventStatus,
    PolicyEventType,
    PreferenceAcceptanceLevel,
    PreferenceDimension,
    SelectionGateCode,
    SelectionGateStatus,
    Strict22408Claim,
    Strict22408Status,
)


@dataclass(frozen=True)
class RawCatalogRow:
    archive_member: str
    row_number: int
    header: tuple[str, ...]
    cells: tuple[str, ...]
    values: Mapping[str, str]


@dataclass(frozen=True)
class CatalogSourceFile:
    archive_member: str
    content_sha256: str
    header: tuple[str, ...]
    rows: Sequence[RawCatalogRow]


@dataclass(frozen=True)
class CatalogArchive:
    source_files: Sequence[CatalogSourceFile]
    ignored_members: Sequence[str]


@dataclass(frozen=True)
class CatalogObservation:
    school: str
    college: str
    program_code: str | None
    program_name: str | None
    direction: str | None
    campus: str | None
    training_location: str | None
    study_mode: str | None
    training_type_raw: str | None
    admission_type: str | None
    degree_type: str | None
    training_arrangement: str | None
    admission_year: int | None
    strict_claim: Strict22408Claim
    strict_status: Strict22408Status
    strict_status_raw: str | None
    total_plan: int | None
    recommendation_actual: int | None
    special_plan: int | None
    effective_general_exam_quota: int | None
    retest_cutoff: float | None
    retest_count: int | None
    general_exam_admit_count: int | None
    admit_initial_min: float | None
    admit_initial_median: float | None
    admit_initial_mean: float | None
    initial_exam_weight: float | None
    retest_weight: float | None
    machine_test_weight: float | None
    machine_test_elimination_line: float | None
    tuition_per_year: float | None
    study_length_years: float | None
    first_choice_protection: bool | None
    evidence_grade: EvidenceGrade
    source_level_raw: str | None
    official_source: str | None
    retrieval_date: date | None
    notes: str | None
    subject_politics_code: str | None = None
    subject_english_code: str | None = None
    subject_math_code: str | None = None
    subject_professional_code: str | None = None
    raw_values: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    field_name: str | None = None
    raw_value: str | None = None


@dataclass(frozen=True)
class NormalizedRow:
    raw_row: RawCatalogRow
    observation: CatalogObservation | None
    issues: Sequence[ValidationIssue]


@dataclass(frozen=True)
class ImportResult:
    batch_id: str
    status: str
    source_hash: str
    source_files: int
    raw_rows: int
    observations: int
    issues: int
    ignored_members: int = 0
    duplicate_of: str | None = None


@dataclass(frozen=True)
class CatalogFilter:
    admission_year: int | None = None
    strict_status: Strict22408Status | None = None
    school_keyword: str | None = None
    limit: int = 100
    raw_imported: bool = False


@dataclass(frozen=True)
class MockExamInput:
    taken_on: date
    paper_name: str
    politics_score: float
    english_score: float
    math_score: float
    computer_science_score: float
    strict_timed: bool
    attempt_number: int = 1
    notes: str | None = None


@dataclass(frozen=True)
class MockSubjectResultInput:
    attendance_status: MockAttendanceStatus
    score_lower: float | None
    score_upper: float | None
    started_at: datetime | None
    ended_at: datetime | None
    note: str | None = None


@dataclass(frozen=True)
class MockExamLedgerInput:
    started_on: date
    completed_on: date
    paper_name: str
    paper_key: str
    paper_source: str
    paper_content_sha256: str | None
    paper_family: MockPaperFamily
    difficulty: MockDifficulty
    scoring_rule_key: str
    first_exposure: bool
    complete_paper_set: bool
    strict_schedule: bool
    authentic_time_slots: bool
    strict_timed: bool
    consulted_materials: bool
    received_assistance: bool
    paused_timer: bool
    reviewed_answers_early: bool
    subject_results: Mapping[str, MockSubjectResultInput]
    attempt_number: int = 1
    invalid_reason_code: MockInvalidReasonCode | None = None
    invalid_reason_note: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class MockExamLedgerAddResult:
    session_id: int
    ledger_version: int
    eligibility_status: str
    total_lower: float | None
    total_upper: float | None


@dataclass(frozen=True)
class AssessmentWindowStatistics:
    total_lower_mean: float | None
    total_upper_mean: float | None
    conservative_total_lower: float | None
    conservative_total_upper: float | None
    typical_total_lower: float | None
    typical_total_upper: float | None
    total_lower_sequence: tuple[float, ...]
    total_upper_sequence: tuple[float, ...]
    subject_lower_series: Mapping[str, tuple[float, ...]]
    subject_upper_series: Mapping[str, tuple[float, ...]]


@dataclass(frozen=True)
class AssessmentBandSummary:
    conservative_band: str | None
    occupied_bands: tuple[str, ...]
    role_band: str | None
    multi_band_guard_applied: bool


@dataclass(frozen=True)
class SelectionGateResult:
    code: SelectionGateCode
    status: SelectionGateStatus
    blocking_reason: str | None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SelectionReadinessFacts:
    profile_id: int | None
    current_preferences: tuple[Mapping[str, Any], ...]
    target_year_observation_count: int
    official_confirmed_target_year_count: int
    official_pending_target_year_count: int
    legacy_snapshot_count: int
    legacy_candidate_count: int
    active_candidate_count: int = 0
    active_research_hypothesis_count: int = 0
    active_official_observation_count: int = 0
    active_official_confirmed_count: int = 0
    fairness_review_count: int = 0
    adverse_fairness_review_count: int = 0


@dataclass(frozen=True)
class AssessmentSummary:
    session_count: int
    total_mean: float | None
    total_standard_deviation: float | None
    conservative_total: float | None
    is_decision_ready: bool
    subject_means: Mapping[str, float]
    rule_version: str = "mock-window-v2"
    as_of: str | None = None
    required_session_count: int = 5
    rolling_window_size: int = 5
    total_session_count: int = 0
    legacy_session_count: int = 0
    invalid_session_count: int = 0
    excluded_session_count: int = 0
    eligible_total_count: int = 0
    active_comparison_key: str | None = None
    comparison_groups: tuple[Mapping[str, Any], ...] = ()
    window_session_ids: tuple[int, ...] = ()
    window_sessions: tuple[Mapping[str, Any], ...] = ()
    is_score_window_ready: bool = False
    is_selection_ready: bool = False
    selection_blocking_reasons: tuple[str, ...] = ()
    selection_gate_version: str = "selection-readiness-v3"
    selection_gates: tuple[SelectionGateResult, ...] = ()
    has_score_intervals: bool = False
    statistics: AssessmentWindowStatistics | None = None
    band: AssessmentBandSummary | None = None
    subject_risk_status: str = "not_measured"


@dataclass(frozen=True)
class SubjectVerificationInput:
    observation_id: int
    politics_code: str
    english_code: str
    math_code: str
    professional_code: str
    source_title: str
    source_url: str
    source_institution: str | None
    source_document_type: EvidenceDocumentType
    source_content_sha256: str
    applicable_year: int
    published_date: date | None
    retrieved_date: date
    note: str | None = None


@dataclass(frozen=True)
class OfficialProjectObservationInput:
    school: str
    college: str
    program_code: str
    program_name: str
    admission_year: int
    politics_code: str
    english_code: str
    math_code: str
    professional_code: str
    source_title: str
    source_url: str
    source_institution: str
    source_document_type: EvidenceDocumentType
    source_content_sha256: str
    applicable_year: int
    retrieved_date: date
    direction: str | None = None
    campus: str | None = None
    training_location: str | None = None
    study_mode: str | None = None
    training_type_raw: str | None = None
    admission_type: str | None = None
    degree_type: str | None = None
    training_arrangement: str | None = None
    published_date: date | None = None
    note: str | None = None


@dataclass(frozen=True)
class OfficialProjectObservationResult:
    observation_id: int
    verification_id: int
    strict_status: Strict22408Status
    created: bool


@dataclass(frozen=True)
class SecondaryProjectObservationInput:
    """A project-year interpretation copied from a named secondary source."""

    school: str
    college: str
    program_code: str
    program_name: str
    admission_year: int
    source_title: str
    source_url: str
    source_institution: str
    source_content_sha256: str
    applicable_year: int
    published_date: date
    retrieved_date: date
    source_excerpt: str
    project_identity_basis: str
    politics_code: str | None = None
    english_code: str | None = None
    math_code: str | None = None
    professional_code: str | None = None
    direction: str | None = None
    campus: str | None = None
    training_location: str | None = None
    study_mode: str | None = None
    training_type_raw: str | None = None
    admission_type: str | None = None
    degree_type: str | None = None
    training_arrangement: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class SecondaryProjectObservationResult:
    observation_id: int
    status: Strict22408Status
    created: bool


@dataclass(frozen=True)
class PolicyEventInput:
    school: str
    effective_year: int
    event_type: PolicyEventType
    scope_text: str
    title: str
    description: str
    announced_on: date
    source_title: str
    source_url: str
    source_institution: str
    source_document_type: EvidenceDocumentType
    source_content_sha256: str
    applicable_year: int
    retrieved_date: date
    observation_id: int | None = None
    published_date: date | None = None
    supersedes_event_id: int | None = None
    note: str | None = None


@dataclass(frozen=True)
class PolicyEventAddResult:
    event_id: int
    created: bool
    school_id: int
    project_id: int | None
    effective_year: int
    event_type: PolicyEventType
    event_status: PolicyEventStatus


@dataclass(frozen=True)
class PolicyEventFilter:
    effective_year: int | None = None
    school_keyword: str | None = None
    observation_id: int | None = None
    event_type: PolicyEventType | None = None
    event_status: PolicyEventStatus | None = None
    current_only: bool = False
    limit: int = 100


@dataclass(frozen=True)
class PreferenceEventInput:
    dimension: PreferenceDimension
    subject_key: str
    acceptance_level: PreferenceAcceptanceLevel
    value: Mapping[str, Any] = field(default_factory=dict)
    note: str | None = None


@dataclass(frozen=True)
class ApplicantContextEventInput:
    dimension: ApplicantContextDimension
    subject_key: str
    value: Mapping[str, Any]
    note: str | None = None


@dataclass(frozen=True)
class ApplicantEvidenceInput:
    """Immutable snapshot of one document used to judge an achievement claim."""

    source_title: str
    source_url: str
    source_access_scope: ApplicantEvidenceAccessScope
    source_document_type: ApplicantEvidenceDocumentType
    source_mime_type: str
    source_content_sha256: str
    source_file_size_bytes: int
    source_retrieved_on: date
    source_reviewed_on: date
    review_method: ApplicantEvidenceReviewMethod
    evidence_grade: ApplicantEvidenceGrade
    evidence_status: ApplicantEvidenceStatus
    claim_text: str
    relationship: AchievementEvidenceRelationship
    note: str | None = None


@dataclass(frozen=True)
class ApplicantAchievementInput:
    """One append-only achievement claim and all evidence supporting its version."""

    achievement_key: str
    category: AchievementCategory
    title: str
    issuer: str
    achievement_year: int
    period_label: str
    awarded_on: date | None
    scope_level: AchievementScopeLevel
    stage: AchievementStage
    result: str
    participation_type: AchievementParticipationType
    team_name: str | None
    details: Mapping[str, Any]
    verification_status: AchievementVerificationStatus
    evidence: tuple[ApplicantEvidenceInput, ...]
    note: str | None = None


@dataclass(frozen=True)
class ApplicantAchievementAddResult:
    event_id: int
    created: bool
    evidence_document_ids: tuple[int, ...]


@dataclass(frozen=True)
class FairnessReviewInput:
    observation_id: int
    conclusion: FairnessReviewConclusion
    summary: str
    evidence: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class PreferenceReadinessSummary:
    contract_version: str
    required_subject_count: int
    answered_subject_count: int
    current_preference_event_count: int
    is_preference_intake_complete: bool
    missing_subjects: tuple[str, ...] = ()
    unknown_subjects: tuple[str, ...] = ()
    contradictory_subjects: tuple[str, ...] = ()
    unsupported_subjects: tuple[str, ...] = ()
    ranking_preferences: tuple[str, ...] = ()


@dataclass(frozen=True)
class MachineTestInput:
    taken_on: date
    duration_minutes: int
    language: str
    environment: str
    problem_source: str
    difficulty: MachineTestDifficulty
    problem_count: int
    independently_solved_count: int
    first_solve_minutes: int | None
    first_exposure: bool
    consulted_materials: bool
    strict_timed: bool
    received_assistance: bool = False
    paused_timer: bool = False
    scoring_method: MachineScoringMethod = MachineScoringMethod.UNKNOWN
    raw_score: float | None = None
    maximum_score: float | None = None
    debugging_minutes: int | None = None
    attempt_number: int = 1
    invalid_reason: str | None = None
    primary_blocker: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class MachineDurationAssessment:
    duration_minutes: int
    status: MachineMeasurementStatus
    total_session_count: int
    valid_session_count: int
    comparison_groups: tuple["MachineComparisonGroup", ...]


@dataclass(frozen=True)
class MachineComparisonGroup:
    language: str
    problem_count: int
    difficulty_label: str
    scoring_method: str
    maximum_score: float | None
    valid_session_count: int
    latest_valid_session: Mapping[str, Any]


@dataclass(frozen=True)
class MachineTestAddResult:
    session_id: int
    is_valid: bool


@dataclass(frozen=True)
class MachineAssessmentSummary:
    total_session_count: int
    valid_session_count: int
    is_duration_coverage_complete: bool
    required_durations: tuple[int, ...]
    durations: tuple[MachineDurationAssessment, ...]


@dataclass(frozen=True)
class FactDerivationInput:
    """Structured operands for one derived fact claim.

    Every operand inherits the single evidence source carried by the enclosing
    ``FactClaimInput``.  Optional fields let the service report incomplete CLI
    input as a domain validation error instead of constructing a false formula.
    """

    operator: str | None = None
    left_fact_key: str | None = None
    left_integer_value: int | None = None
    right_fact_key: str | None = None
    right_integer_value: int | None = None


@dataclass(frozen=True)
class FactClaimInput:
    observation_id: int
    fact_key: str
    raw_value: str
    evidence_grade: EvidenceGrade
    source_title: str
    source_url: str | None
    source_institution: str | None
    source_document_type: EvidenceDocumentType
    source_content_sha256: str | None
    applicable_year: int
    published_date: date | None
    retrieved_date: date
    population_scope: str
    statistic_scope: str
    sample_size: int | None = None
    calculation_method_key: str | None = None
    calculation_input_sha256: str | None = None
    derivation: FactDerivationInput | None = None
    note: str | None = None
    source_note: str | None = None


@dataclass(frozen=True)
class TypedFactValue:
    data_type: FactDataType
    integer_value: int | None = None
    decimal_value: float | None = None
    text_value: str | None = None
    boolean_value: bool | None = None


@dataclass(frozen=True)
class Settings:
    repository_root: Path
    database_path: Path
    log_path: Path
    log_level: str
    busy_timeout_ms: int
    catalog_member_pattern: str
    importer_version: str
    max_archive_uncompressed_bytes: int
    max_member_uncompressed_bytes: int
    max_compression_ratio: float
    strict_politics_code: str
    strict_english_code: str
    strict_math_code: str
    strict_professional_code: str
    minimum_mock_sessions: int
    mock_rolling_window_size: int
    required_machine_durations: tuple[int, ...]
    profile_key: str
    undergraduate_school: str
    undergraduate_major: str
    target_exam_year: int
    target_degree_type: str
    target_tier: str


JsonMapping = Mapping[str, Any]
