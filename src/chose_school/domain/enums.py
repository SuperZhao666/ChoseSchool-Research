from __future__ import annotations

from enum import StrEnum


class Strict22408Claim(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Strict22408Status(StrEnum):
    """Evidence state for the complete 101+204+302+408 contract."""

    UNVERIFIED = "unverified"
    SECONDARY_ONLY = "secondary_only"
    OFFICIAL_PENDING_CATALOG = "official_pending_catalog"
    OFFICIAL_CONFIRMED = "official_confirmed"
    OFFICIAL_NON_STRICT = "official_non_strict"
    CONFLICT = "conflict"


class EvidenceGrade(StrEnum):
    OFFICIAL = "official"
    OFFICIAL_MIXED = "official_mixed"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    UNKNOWN = "unknown"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class ImportStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICT = "conflict"


class SubjectCode(StrEnum):
    POLITICS = "101"
    ENGLISH_TWO = "204"
    MATH_TWO = "302"
    COMPUTER_SCIENCE_408 = "408"


class CandidateTier(StrEnum):
    """Legacy placeholder tier; not authoritative for personal selection."""

    SPRINT = "sprint"
    MATCH = "match"
    STEADY = "steady"
    WATCH = "watch"
    EXCLUDED = "excluded"


class SelectionGateStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    NOT_EVALUABLE = "not_evaluable"


class SelectionGateCode(StrEnum):
    SCORE_WINDOW = "score_window"
    SUBJECT_RISK = "subject_risk"
    PREFERENCE_INPUT_COVERAGE = "preference_input_coverage"
    CANDIDATE_STRUCTURE = "candidate_structure"
    CANDIDATE_2027_CATALOG = "candidate_2027_catalog"
    CANDIDATE_ORDINARY_QUOTA = "candidate_ordinary_quota"
    CANDIDATE_RETEST_CONTRACT = "candidate_retest_contract"
    CANDIDATE_FAIRNESS_REVIEW = "candidate_fairness_review"


class PreferenceDimension(StrEnum):
    """A personal boundary that can change a candidate project's role."""

    REGION = "region"
    TRAINING_LOCATION = "training_location"
    PROGRAM_CODE = "program_code"
    TUITION_CEILING = "tuition_ceiling"
    RETEST_FORMAT = "retest_format"
    JOINT_TRAINING = "joint_training"
    SCHOOL_TIER_REQUIREMENT = "school_tier_requirement"
    ADMISSION_FAIRNESS = "admission_fairness"
    INSTITUTION = "institution"


class PreferenceAcceptanceLevel(StrEnum):
    """Explicit user acceptance state; unknown must never pass a hard filter."""

    ACCEPT = "accept"
    RELUCTANT = "reluctant"
    REJECT = "reject"
    UNKNOWN = "unknown"


class ApplicantContextDimension(StrEnum):
    """Self-reported context; never a substitute for measured scores."""

    STUDY_PROGRESS = "study_progress"
    STUDY_ROUTINE = "study_routine"
    MEASUREMENT_STATUS = "measurement_status"
    PREPARATION_STRATEGY = "preparation_strategy"
    PERSONAL_CONSTRAINT = "personal_constraint"


class AchievementCategory(StrEnum):
    """Applicant achievement family; independent from school-side evidence grades."""

    COMPETITION_AWARD = "competition_award"
    SCHOLARSHIP = "scholarship"
    ABILITY_CERTIFICATE = "ability_certificate"


class AchievementScopeLevel(StrEnum):
    NATIONAL = "national"
    PROVINCIAL = "provincial"
    SCHOOL = "school"
    UNSPECIFIED = "unspecified"
    NOT_APPLICABLE = "not_applicable"


class AchievementStage(StrEnum):
    NATIONAL_FINAL = "national_final"
    PROVINCIAL_ROUND = "provincial_round"
    PRELIMINARY_ROUND = "preliminary_round"
    POPULARIZATION = "popularization"
    ACADEMIC_YEAR = "academic_year"
    ASSESSMENT = "assessment"


class AchievementParticipationType(StrEnum):
    INDIVIDUAL = "individual"
    TEAM = "team"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class AchievementVerificationStatus(StrEnum):
    """Claim state; document_confirmed is not official online verification."""

    DOCUMENT_CONFIRMED = "document_confirmed"
    METADATA_ONLY = "metadata_only"
    SELF_REPORTED = "self_reported"
    CONFLICT = "conflict"


class ApplicantEvidenceAccessScope(StrEnum):
    PRIVATE_USER_DRIVE = "private_user_drive"
    PUBLIC_WEB = "public_web"
    LOCAL_USER_FILE = "local_user_file"


class ApplicantEvidenceDocumentType(StrEnum):
    AWARD_CERTIFICATE = "award_certificate"
    SCHOLARSHIP_CERTIFICATE = "scholarship_certificate"
    SCORE_CERTIFICATE = "score_certificate"
    AWARD_PROOF = "award_proof"


class ApplicantEvidenceReviewMethod(StrEnum):
    FULL_DOCUMENT_VISUAL_REVIEW = "full_document_visual_review"
    COMBINED_VISUAL_AND_TEXT = "combined_visual_and_text"
    OCR_ONLY = "ocr_only"
    METADATA_ONLY = "metadata_only"
    NOT_REVIEWED = "not_reviewed"


class ApplicantEvidenceGrade(StrEnum):
    PRIMARY_DOCUMENT_USER_COPY = "primary_document_user_copy"
    OFFICIAL_ONLINE_VERIFICATION = "official_online_verification"
    SELF_REPORTED = "self_reported"
    UNKNOWN = "unknown"


class ApplicantEvidenceStatus(StrEnum):
    DOCUMENT_VISUAL_CONFIRMED = "document_visual_confirmed"
    METADATA_ONLY = "metadata_only"
    SELF_REPORTED = "self_reported"
    CONFLICT = "conflict"


class AchievementEvidenceRelationship(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class FairnessReviewConclusion(StrEnum):
    """Evidence-backed project-year review, not a school-wide label."""

    FAVORABLE = "favorable"
    MIXED = "mixed"
    ADVERSE = "adverse"
    INSUFFICIENT = "insufficient"


class MachineTestDifficulty(StrEnum):
    BASIC = "basic"
    MIXED = "mixed"
    CANDIDATE_SPECIFIC = "candidate_specific"
    UNKNOWN = "unknown"


class MachineScoringMethod(StrEnum):
    SOLVED_COUNT = "solved_count"
    POINTS = "points"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class MachineMeasurementStatus(StrEnum):
    NOT_MEASURED = "not_measured"
    INVALID_ONLY = "invalid_only"
    VALID_MEASURED = "valid_measured"


class MockAttendanceStatus(StrEnum):
    PRESENT_SCORED = "present_scored"
    PRESENT_BLANK = "present_blank"
    ABSENT = "absent"


class MockPaperFamily(StrEnum):
    OFFICIAL_PAST = "official_past"
    CALIBRATED_MOCK = "calibrated_mock"
    TRAINING = "training"
    UNKNOWN = "unknown"


class MockDifficulty(StrEnum):
    STANDARD = "standard"
    EASIER = "easier"
    HARDER = "harder"
    UNKNOWN = "unknown"


class MockInvalidReasonCode(StrEnum):
    NOT_FIRST_EXPOSURE = "not_first_exposure"
    CONSULTED_MATERIALS = "consulted_materials"
    RECEIVED_ASSISTANCE = "received_assistance"
    PAUSED_TIMER = "paused_timer"
    NOT_STRICT_TIMED = "not_strict_timed"
    NOT_COMPLETE_PAPER_SET = "not_complete_paper_set"
    NOT_STRICT_SCHEDULE = "not_strict_schedule"
    INAUTHENTIC_TIME_SLOTS = "inauthentic_time_slots"
    REVIEWED_ANSWERS_EARLY = "reviewed_answers_early"
    TECHNICAL_INTERRUPTION = "technical_interruption"
    HEALTH_INTERRUPTION = "health_interruption"
    ABSENT_SUBJECT = "absent_subject"
    OTHER_PROTOCOL_FAILURE = "other_protocol_failure"


class ScoreBand(StrEnum):
    BELOW_290 = "below_290"
    FROM_290_TO_304 = "290_304"
    FROM_305_TO_314 = "305_314"
    FROM_315_TO_324 = "315_324"
    FROM_325_TO_334 = "325_334"
    FROM_335_TO_344 = "335_344"
    FROM_345_TO_359 = "345_359"
    FROM_360_TO_379 = "360_379"
    AT_LEAST_380 = "at_least_380"


class FactDataType(StrEnum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    TEXT = "text"
    BOOLEAN = "boolean"


class EvidenceDocumentType(StrEnum):
    OFFICIAL_CATALOG = "official_catalog"
    OFFICIAL_NOTICE = "official_notice"
    RETEST_POLICY = "retest_policy"
    RETEST_LIST = "retest_list"
    ADMISSION_LIST = "admission_list"
    FEE_NOTICE = "fee_notice"
    OTHER_OFFICIAL = "other_official"
    SECONDARY_SUMMARY = "secondary_summary"
    EXPERIENCE_POST = "experience_post"


class PolicyEventType(StrEnum):
    """A narrowly defined official policy notice, not a catalog fact."""

    SUBJECT_ADJUSTMENT_NOTICE = "subject_adjustment_notice"


class PolicyEventStatus(StrEnum):
    """Policy lifecycle state; it never substitutes for Strict22408Status."""

    ANNOUNCED = "announced"
    PENDING_DIRECTORY = "pending_directory"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
