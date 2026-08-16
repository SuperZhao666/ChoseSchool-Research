from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class ApplicationServices:
    database: DatabaseAdministrationService
    catalog_import: CatalogImportService
    catalog: CatalogService
    catalog_export: CatalogExportService
    verification: SubjectVerificationService
    assessment: AssessmentService
    maintenance: MaintenanceService
    facts: FactService
    official_observations: OfficialObservationService
    secondary_observations: SecondaryObservationService
    policy_events: PolicyEventService
    preferences: PreferenceService
    applicant_context: ApplicantContextService
    applicant_achievements: ApplicantAchievementService
    fairness_reviews: FairnessReviewService
    machine_tests: MachineTestService
    candidate_model: CandidateModelService
