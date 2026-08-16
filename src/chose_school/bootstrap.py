from __future__ import annotations

from chose_school.business.application import ApplicationServices
from chose_school.business.applicant_achievement_service import ApplicantAchievementService
from chose_school.business.applicant_context_service import ApplicantContextService
from chose_school.business.assessment_service import AssessmentService
from chose_school.business.catalog_import_service import CatalogImportService
from chose_school.business.catalog_service import CatalogService
from chose_school.business.candidate_model_service import CandidateModelService
from chose_school.business.database_service import DatabaseAdministrationService
from chose_school.business.export_service import CatalogExportService
from chose_school.business.fact_service import FactService
from chose_school.business.fairness_review_service import FairnessReviewService
from chose_school.business.maintenance_service import MaintenanceService
from chose_school.business.machine_test_service import MachineTestService
from chose_school.business.official_observation_service import OfficialObservationService
from chose_school.business.policy_event_service import PolicyEventService
from chose_school.business.preference_service import PreferenceService
from chose_school.business.secondary_observation_service import SecondaryObservationService
from chose_school.business.verification_service import SubjectVerificationService
from chose_school.data_access.sqlite_assessment import SqliteAssessmentRepository
from chose_school.data_access.sqlite_applicant_context import (
    SqliteApplicantContextRepository,
)
from chose_school.data_access.sqlite_applicant_achievements import (
    SqliteApplicantAchievementRepository,
)
from chose_school.data_access.sqlite_catalog import SqliteCatalogRepository
from chose_school.data_access.sqlite_candidate_model import SqliteCandidateModelRepository
from chose_school.data_access.sqlite_facts import SqliteFactRepository
from chose_school.data_access.sqlite_fairness_reviews import (
    SqliteFairnessReviewRepository,
)
from chose_school.data_access.sqlite_machine_tests import SqliteMachineTestRepository
from chose_school.data_access.sqlite_official_observations import (
    SqliteOfficialProjectObservationRepository,
)
from chose_school.data_access.sqlite_preferences import SqlitePreferenceRepository
from chose_school.data_access.sqlite_policy_events import SqlitePolicyEventRepository
from chose_school.data_access.sqlite_secondary_observations import (
    SqliteSecondaryProjectObservationRepository,
)
from chose_school.data_access.sqlite_selection_readiness import (
    SqliteSelectionReadinessRepository,
)
from chose_school.data_access.sqlite_verification import (
    SqliteSubjectVerificationRepository,
)
from chose_school.domain.models import Settings
from chose_school.infrastructure.catalog_archive import KimiCatalogArchiveReader
from chose_school.infrastructure.database import Database
from chose_school.infrastructure.database_backup import SqliteDatabaseBackup


def build_application(settings: Settings) -> ApplicationServices:
    database = Database(settings.database_path, settings.busy_timeout_ms)
    catalog_repository = SqliteCatalogRepository(database)
    archive_reader = KimiCatalogArchiveReader(
        member_pattern=settings.catalog_member_pattern,
        max_archive_uncompressed_bytes=settings.max_archive_uncompressed_bytes,
        max_member_uncompressed_bytes=settings.max_member_uncompressed_bytes,
        max_compression_ratio=settings.max_compression_ratio,
    )
    catalog_import = CatalogImportService(
        archive_reader,
        catalog_repository,
        settings.importer_version,
    )
    catalog = CatalogService(catalog_repository)
    catalog_export = CatalogExportService(catalog)
    verification = SubjectVerificationService(
        SqliteSubjectVerificationRepository(database),
        settings,
    )
    assessment = AssessmentService(
        SqliteAssessmentRepository(database),
        SqliteSelectionReadinessRepository(database),
        settings,
    )
    maintenance = MaintenanceService(
        catalog_repository,
        SqliteDatabaseBackup(database),
    )
    facts = FactService(SqliteFactRepository(database))
    official_observations = OfficialObservationService(
        SqliteOfficialProjectObservationRepository(database),
        settings,
    )
    secondary_observations = SecondaryObservationService(
        SqliteSecondaryProjectObservationRepository(database),
        settings,
    )
    policy_events = PolicyEventService(SqlitePolicyEventRepository(database))
    preferences = PreferenceService(SqlitePreferenceRepository(database), settings)
    applicant_context = ApplicantContextService(
        SqliteApplicantContextRepository(database),
        settings,
    )
    applicant_achievements = ApplicantAchievementService(
        SqliteApplicantAchievementRepository(database),
        settings,
    )
    fairness_reviews = FairnessReviewService(
        SqliteFairnessReviewRepository(database),
        settings,
    )
    machine_tests = MachineTestService(SqliteMachineTestRepository(database), settings)
    candidate_model = CandidateModelService(
        SqliteCandidateModelRepository(database), settings
    )
    database_administration = DatabaseAdministrationService(database)
    return ApplicationServices(
        database=database_administration,
        catalog_import=catalog_import,
        catalog=catalog,
        catalog_export=catalog_export,
        verification=verification,
        assessment=assessment,
        maintenance=maintenance,
        facts=facts,
        official_observations=official_observations,
        secondary_observations=secondary_observations,
        policy_events=policy_events,
        preferences=preferences,
        applicant_context=applicant_context,
        applicant_achievements=applicant_achievements,
        fairness_reviews=fairness_reviews,
        machine_tests=machine_tests,
        candidate_model=candidate_model,
    )
