from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from chose_school.business.application import ApplicationServices
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
    EvidenceDocumentType,
    EvidenceGrade,
    FairnessReviewConclusion,
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
    Strict22408Status,
)
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import (
    ApplicantAchievementInput,
    ApplicantContextEventInput,
    ApplicantEvidenceInput,
    CatalogFilter,
    FactClaimInput,
    FactDerivationInput,
    FairnessReviewInput,
    MachineTestInput,
    MockExamLedgerInput,
    MockExamInput,
    MockSubjectResultInput,
    OfficialProjectObservationInput,
    PolicyEventFilter,
    PolicyEventInput,
    PreferenceEventInput,
    SecondaryProjectObservationInput,
    SubjectVerificationInput,
)


CommandHandler = Callable[[argparse.Namespace, ApplicationServices, str], Any]


def dispatch_command(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    handler = COMMAND_HANDLERS.get(arguments.command)
    if handler is None:
        raise ValidationError(
            "CLI_UNSUPPORTED_COMMAND",
            f"unsupported command: {arguments.command}",
            {"command": arguments.command},
        )
    return handler(arguments, application, trace_id)


def _initialize_database(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    result = application.database.initialize_database()
    result["profile_id"] = application.assessment.initialize_default_profile(trace_id)
    return result


def _import_kimi(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    result = application.catalog_import.import_archive(
        Path(arguments.archive),
        batch_id=str(uuid.uuid4()),
        trace_id=trace_id,
    )
    return asdict(result)


def _get_summary(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    return application.catalog.get_summary()


def _list_projects(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    strict_status = Strict22408Status(arguments.status) if arguments.status else None
    catalog_filter = CatalogFilter(
        admission_year=arguments.year,
        strict_status=strict_status,
        school_keyword=arguments.school,
        limit=arguments.limit,
        raw_imported=arguments.raw_imported,
    )
    return list(application.catalog.list_catalog(catalog_filter))


def _list_issues(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    return list(
        application.catalog.list_issues(
            severity=arguments.severity,
            status=arguments.status,
            limit=arguments.limit,
        )
    )


def _resolve_issue(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    application.maintenance.resolve_issue(arguments.issue_id, arguments.note, trace_id)
    return {"issue_id": arguments.issue_id, "status": "resolved", "trace_id": trace_id}


def _add_official_observation(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    observation = OfficialProjectObservationInput(
        school=arguments.school,
        college=arguments.college,
        program_code=arguments.program_code,
        program_name=arguments.program_name,
        admission_year=arguments.admission_year,
        politics_code=arguments.politics,
        english_code=arguments.english,
        math_code=arguments.math,
        professional_code=arguments.professional,
        source_title=arguments.source_title,
        source_url=arguments.source_url,
        source_institution=arguments.source_institution,
        source_document_type=EvidenceDocumentType(arguments.source_document_type),
        source_content_sha256=arguments.source_content_sha256,
        applicable_year=arguments.applicable_year,
        published_date=_parse_optional_date(arguments.published_date),
        retrieved_date=_parse_required_date(arguments.retrieved_date),
        direction=arguments.direction,
        campus=arguments.campus,
        training_location=arguments.training_location,
        study_mode=arguments.study_mode,
        training_type_raw=arguments.training_type,
        admission_type=arguments.admission_type,
        degree_type=arguments.degree_type,
        training_arrangement=arguments.training_arrangement,
        note=arguments.note,
    )
    result = application.official_observations.add_observation(
        observation,
        trace_id,
    )
    return {
        "observation_id": result.observation_id,
        "verification_id": result.verification_id,
        "strict_22408_status": result.strict_status.value,
        "created": result.created,
        "trace_id": trace_id,
    }


def _add_secondary_observation(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    observation = SecondaryProjectObservationInput(
        school=arguments.school,
        college=arguments.college,
        program_code=arguments.program_code,
        program_name=arguments.program_name,
        admission_year=arguments.admission_year,
        source_title=arguments.source_title,
        source_url=arguments.source_url,
        source_institution=arguments.source_institution,
        source_content_sha256=arguments.source_content_sha256,
        applicable_year=arguments.applicable_year,
        published_date=_parse_required_date(arguments.published_date),
        retrieved_date=_parse_required_date(arguments.retrieved_date),
        source_excerpt=arguments.source_excerpt,
        project_identity_basis=arguments.project_identity_basis,
        politics_code=arguments.politics,
        english_code=arguments.english,
        math_code=arguments.math,
        professional_code=arguments.professional,
        direction=arguments.direction,
        campus=arguments.campus,
        training_location=arguments.training_location,
        study_mode=arguments.study_mode,
        training_type_raw=arguments.training_type,
        admission_type=arguments.admission_type,
        degree_type=arguments.degree_type,
        training_arrangement=arguments.training_arrangement,
        note=arguments.note,
    )
    result = application.secondary_observations.add_observation(
        observation,
        trace_id,
    )
    return {
        "observation_id": result.observation_id,
        "created": result.created,
        "status": result.status.value,
        "establishes_official_catalog": False,
        "can_confirm_strict_22408": False,
        "trace_id": trace_id,
    }


def _add_fact(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    derivation_arguments = (
        arguments.derivation_operator,
        arguments.derivation_left_fact_key,
        arguments.derivation_left_value,
        arguments.derivation_right_fact_key,
        arguments.derivation_right_value,
    )
    derivation = (
        FactDerivationInput(
            operator=arguments.derivation_operator,
            left_fact_key=arguments.derivation_left_fact_key,
            left_integer_value=arguments.derivation_left_value,
            right_fact_key=arguments.derivation_right_fact_key,
            right_integer_value=arguments.derivation_right_value,
        )
        if any(value is not None for value in derivation_arguments)
        else None
    )
    claim = FactClaimInput(
        observation_id=arguments.observation_id,
        fact_key=arguments.fact_key,
        raw_value=arguments.value,
        evidence_grade=EvidenceGrade(arguments.evidence_grade),
        source_title=arguments.source_title,
        source_url=arguments.source_url,
        source_institution=arguments.source_institution,
        source_document_type=EvidenceDocumentType(arguments.source_document_type),
        source_content_sha256=arguments.source_content_sha256,
        applicable_year=arguments.applicable_year,
        published_date=_parse_optional_date(arguments.published_date),
        retrieved_date=_parse_required_date(arguments.retrieved_date),
        population_scope=arguments.population_scope,
        statistic_scope=arguments.statistic_scope,
        sample_size=arguments.sample_size,
        calculation_method_key=arguments.calculation_method_key,
        calculation_input_sha256=arguments.calculation_input_sha256,
        derivation=derivation,
        note=arguments.note,
    )
    return {"claim_id": application.facts.add_claim(claim, trace_id), "trace_id": trace_id}


def _add_policy_event(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    event = PolicyEventInput(
        school=arguments.school,
        observation_id=arguments.observation_id,
        effective_year=arguments.effective_year,
        event_type=PolicyEventType(arguments.event_type),
        scope_text=arguments.scope_text,
        title=arguments.title,
        description=arguments.description,
        announced_on=_parse_required_date(arguments.announced_on),
        source_title=arguments.source_title,
        source_url=arguments.source_url,
        source_institution=arguments.source_institution,
        source_document_type=EvidenceDocumentType(arguments.source_document_type),
        source_content_sha256=arguments.source_content_sha256,
        applicable_year=arguments.applicable_year,
        published_date=_parse_optional_date(arguments.published_date),
        retrieved_date=_parse_required_date(arguments.retrieved_date),
        supersedes_event_id=arguments.supersedes_event_id,
        note=arguments.note,
    )
    result = application.policy_events.add_event(event, trace_id)
    return {
        "event_id": result.event_id,
        "created": result.created,
        "school_id": result.school_id,
        "project_id": result.project_id,
        "effective_year": result.effective_year,
        "event_type": result.event_type.value,
        "event_status": result.event_status.value,
        "establishes_official_catalog": False,
        "can_confirm_strict_22408": False,
        "trace_id": trace_id,
    }


def _list_policy_events(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    event_filter = PolicyEventFilter(
        effective_year=arguments.year,
        school_keyword=arguments.school,
        observation_id=arguments.observation_id,
        event_type=PolicyEventType(arguments.event_type)
        if arguments.event_type
        else None,
        event_status=PolicyEventStatus(arguments.status) if arguments.status else None,
        current_only=arguments.current_only,
        limit=arguments.limit,
    )
    return list(application.policy_events.list_events(event_filter))


def _resolve_fact(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    resolution_id = application.facts.resolve_claim(arguments.claim_id, arguments.reason, trace_id)
    return {"resolution_id": resolution_id, "selected_claim_id": arguments.claim_id, "trace_id": trace_id}


def _unresolve_fact(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    resolution_id = application.facts.unresolve_claim(
        arguments.claim_id,
        arguments.reason,
        trace_id,
    )
    return {
        "resolution_id": resolution_id,
        "identity_claim_id": arguments.claim_id,
        "resolution_action": "unresolved",
        "selected_claim_id": None,
        "trace_id": trace_id,
    }


def _list_facts(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    return list(application.facts.list_claims(arguments.observation_id))


def _list_fact_conflicts(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    return list(application.facts.list_conflicts(arguments.limit))


def _verify_exam(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    verification = _build_subject_verification(arguments)
    verification_id, status = application.verification.verify(verification, trace_id)
    return {
        "verification_id": verification_id,
        "observation_id": arguments.observation_id,
        "strict_22408_status": status.value,
        "trace_id": trace_id,
    }


def _build_subject_verification(arguments: argparse.Namespace) -> SubjectVerificationInput:
    return SubjectVerificationInput(
        observation_id=arguments.observation_id,
        politics_code=arguments.politics,
        english_code=arguments.english,
        math_code=arguments.math,
        professional_code=arguments.professional,
        source_title=arguments.source_title,
        source_url=arguments.source_url,
        source_institution=arguments.source_institution,
        source_document_type=EvidenceDocumentType(arguments.source_document_type),
        source_content_sha256=arguments.source_content_sha256,
        applicable_year=arguments.applicable_year,
        published_date=_parse_optional_date(arguments.published_date),
        retrieved_date=_parse_required_date(arguments.retrieved_date),
        note=arguments.note,
    )


def _add_mock(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    mock_exam = MockExamInput(
        taken_on=_parse_required_date(arguments.date),
        paper_name=arguments.paper,
        politics_score=arguments.politics,
        english_score=arguments.english,
        math_score=arguments.math,
        computer_science_score=arguments.cs408,
        strict_timed=arguments.strict_timed,
        attempt_number=arguments.attempt,
        notes=arguments.note,
    )
    return {
        "session_id": application.assessment.add_mock_exam(mock_exam, trace_id),
        "ledger_version": 1,
        "eligibility_status": "legacy_unverified",
        "is_assessment_eligible": False,
        "trace_id": trace_id,
    }


def _add_mock_ledger(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    invalid_reason_code = (
        MockInvalidReasonCode(arguments.invalid_reason_code)
        if arguments.invalid_reason_code
        else None
    )
    mock_exam = MockExamLedgerInput(
        started_on=_parse_required_date(arguments.start_date),
        completed_on=_parse_required_date(arguments.end_date),
        paper_name=arguments.paper,
        paper_key=arguments.paper_key,
        paper_source=arguments.paper_source,
        paper_content_sha256=arguments.paper_content_sha256,
        paper_family=MockPaperFamily(arguments.paper_family),
        difficulty=MockDifficulty(arguments.difficulty),
        scoring_rule_key=arguments.scoring_rule_key,
        first_exposure=arguments.first_exposure,
        complete_paper_set=arguments.complete_paper_set,
        strict_schedule=arguments.strict_schedule,
        authentic_time_slots=arguments.authentic_time_slots,
        strict_timed=arguments.strict_timed,
        consulted_materials=arguments.consulted_materials,
        received_assistance=arguments.received_assistance,
        paused_timer=arguments.paused_timer,
        reviewed_answers_early=arguments.reviewed_answers_early,
        subject_results=_parse_mock_subject_results(arguments.subject_results_json),
        attempt_number=arguments.attempt,
        invalid_reason_code=invalid_reason_code,
        invalid_reason_note=arguments.invalid_reason_note,
        notes=arguments.note,
    )
    result = application.assessment.add_mock_exam_ledger(mock_exam, trace_id)
    return {**asdict(result), "trace_id": trace_id}


def _list_mock_sessions(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return list(
        application.assessment.list_mock_exams(
            include_legacy=arguments.include_legacy,
            eligible_only=arguments.eligible_only,
            session_id=arguments.session_id,
            limit=arguments.limit,
        )
    )


def _exclude_mock_session(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    exclusion_id = application.assessment.exclude_mock_exam(
        session_id=arguments.session_id,
        reason=arguments.reason,
        trace_id=trace_id,
    )
    return {
        "exclusion_id": exclusion_id,
        "session_id": arguments.session_id,
        "status": "exclusion_appended",
        "trace_id": trace_id,
    }


def _add_preference(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    preference = PreferenceEventInput(
        dimension=PreferenceDimension(arguments.dimension),
        subject_key=arguments.subject,
        acceptance_level=PreferenceAcceptanceLevel(arguments.acceptance),
        value=_parse_json_object(arguments.value_json),
        note=arguments.note,
    )
    event_id = application.preferences.add_preference(preference, trace_id)
    return {"event_id": event_id, "trace_id": trace_id}


def _list_preferences(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return list(
        application.preferences.list_preferences(
            dimension=arguments.dimension,
            subject_key=arguments.subject,
            include_history=arguments.history,
        )
    )


def _get_preference_readiness(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return asdict(application.preferences.summarize_readiness())


def _add_context(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    event = ApplicantContextEventInput(
        dimension=ApplicantContextDimension(arguments.dimension),
        subject_key=arguments.subject,
        value=_parse_json_object(arguments.value_json),
        note=arguments.note,
    )
    event_id = application.applicant_context.add_context(event, trace_id)
    return {"event_id": event_id, "trace_id": trace_id}


def _list_contexts(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return list(
        application.applicant_context.list_contexts(
            dimension=arguments.dimension,
            subject_key=arguments.subject,
            include_history=arguments.history,
        )
    )


def _add_achievement(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    evidence = tuple(
        _parse_applicant_evidence(item)
        for item in _parse_json_array(arguments.evidence_json)
    )
    achievement = ApplicantAchievementInput(
        achievement_key=arguments.key,
        category=AchievementCategory(arguments.category),
        title=arguments.title,
        issuer=arguments.issuer,
        achievement_year=arguments.year,
        period_label=arguments.period,
        awarded_on=_parse_optional_date(arguments.awarded_on),
        scope_level=AchievementScopeLevel(arguments.scope_level),
        stage=AchievementStage(arguments.stage),
        result=arguments.result,
        participation_type=AchievementParticipationType(arguments.participation_type),
        team_name=arguments.team_name,
        details=_parse_json_object(arguments.details_json),
        verification_status=AchievementVerificationStatus(
            arguments.verification_status
        ),
        evidence=evidence,
        note=arguments.note,
    )
    result = application.applicant_achievements.add_achievement(
        achievement,
        trace_id,
    )
    return {**asdict(result), "trace_id": trace_id}


def _list_achievements(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return list(
        application.applicant_achievements.list_achievements(
            category=arguments.category,
            achievement_year=arguments.year,
            achievement_key=arguments.key,
            include_history=arguments.history,
        )
    )


def _add_fairness_review(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    review = FairnessReviewInput(
        observation_id=arguments.observation_id,
        conclusion=FairnessReviewConclusion(arguments.conclusion),
        summary=arguments.summary,
        evidence=tuple(_parse_json_array(arguments.evidence_json)),
    )
    review_id = application.fairness_reviews.add_review(review, trace_id)
    return {"review_id": review_id, "trace_id": trace_id}


def _list_fairness_reviews(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return list(
        application.fairness_reviews.list_reviews(
            observation_id=arguments.observation_id,
            include_history=arguments.history,
        )
    )


def _get_assessment(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    return asdict(application.assessment.summarize())


def _add_machine_test(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    machine_test = MachineTestInput(
        taken_on=_parse_required_date(arguments.date),
        duration_minutes=arguments.duration,
        language=arguments.language,
        environment=arguments.environment,
        problem_source=arguments.source,
        difficulty=MachineTestDifficulty(arguments.difficulty),
        problem_count=arguments.total,
        independently_solved_count=arguments.solved,
        first_solve_minutes=arguments.first_solve_minutes,
        first_exposure=arguments.first_exposure,
        consulted_materials=arguments.consulted_materials,
        strict_timed=arguments.strict_timed,
        received_assistance=arguments.received_assistance,
        paused_timer=arguments.paused_timer,
        scoring_method=MachineScoringMethod(arguments.scoring_method),
        raw_score=arguments.raw_score,
        maximum_score=arguments.maximum_score,
        debugging_minutes=arguments.debugging_minutes,
        attempt_number=arguments.attempt,
        invalid_reason=arguments.invalid_reason,
        primary_blocker=arguments.blocker,
        notes=arguments.note,
    )
    result = application.machine_tests.add_machine_test(machine_test, trace_id)
    return {
        "session_id": result.session_id,
        "is_valid": result.is_valid,
        "trace_id": trace_id,
    }


def _list_machine_tests(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return list(
        application.machine_tests.list_sessions(
            duration_minutes=arguments.duration,
            language=arguments.language,
            problem_count=arguments.problem_count,
            valid_only=arguments.valid_only,
        )
    )


def _get_machine_assessment(
    arguments: argparse.Namespace,
    application: ApplicationServices,
    trace_id: str,
) -> Any:
    return asdict(application.machine_tests.summarize())


def _export_catalog(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    count = application.catalog_export.export_catalog(
        Path(arguments.output),
        force=arguments.force,
        excel_safe=arguments.excel_safe,
        raw_imported=arguments.raw_imported,
    )
    return {"output": str(Path(arguments.output).resolve()), "rows": count}


def _run_doctor(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    return application.catalog.doctor()


def _create_backup(arguments: argparse.Namespace, application: ApplicationServices, trace_id: str) -> Any:
    destination = application.maintenance.create_backup(Path(arguments.output), arguments.force)
    return {"backup": str(destination.resolve()), "status": "created"}


def _parse_required_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(
            "INVALID_DATE",
            f"日期必须使用 YYYY-MM-DD：{value}",
            {"value": value},
        ) from error


def _parse_optional_date(value: str | None) -> date | None:
    return _parse_required_date(value) if value else None


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValidationError(
            "INVALID_JSON_OBJECT",
            "value-json必须是有效JSON对象",
            {"column": error.colno},
        ) from error
    if not isinstance(parsed, dict):
        raise ValidationError(
            "INVALID_JSON_OBJECT",
            "value-json顶层必须是JSON对象",
        )
    return parsed


def _parse_json_array(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValidationError(
            "INVALID_JSON_ARRAY",
            "evidence-json必须是有效JSON数组",
            {"column": error.colno},
        ) from error
    if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
        raise ValidationError(
            "INVALID_JSON_ARRAY",
            "evidence-json顶层必须是对象数组",
        )
    return parsed


def _parse_applicant_evidence(raw: dict[str, Any]) -> ApplicantEvidenceInput:
    required_fields = {
        "source_title",
        "source_url",
        "source_access_scope",
        "source_document_type",
        "source_mime_type",
        "source_content_sha256",
        "source_file_size_bytes",
        "source_retrieved_on",
        "source_reviewed_on",
        "review_method",
        "evidence_grade",
        "evidence_status",
        "claim_text",
        "relationship",
    }
    allowed_fields = required_fields | {"note"}
    unknown_fields = sorted(set(raw) - allowed_fields)
    missing_fields = sorted(required_fields - set(raw))
    if unknown_fields or missing_fields:
        raise ValidationError(
            "INVALID_ACHIEVEMENT_EVIDENCE_FIELDS",
            "成果证据字段不完整或包含未知字段",
            {"missing": missing_fields, "unknown": unknown_fields},
        )
    text_fields = required_fields - {"source_file_size_bytes"}
    invalid_text_fields = sorted(
        field
        for field in text_fields
        if not isinstance(raw[field], str) or not raw[field].strip()
    )
    if invalid_text_fields:
        raise ValidationError(
            "INVALID_ACHIEVEMENT_EVIDENCE_TEXT",
            "成果证据必填文本字段不能为空",
            {"fields": invalid_text_fields},
        )
    try:
        return ApplicantEvidenceInput(
            source_title=raw["source_title"],
            source_url=raw["source_url"],
            source_access_scope=ApplicantEvidenceAccessScope(
                raw["source_access_scope"]
            ),
            source_document_type=ApplicantEvidenceDocumentType(
                raw["source_document_type"]
            ),
            source_mime_type=raw["source_mime_type"],
            source_content_sha256=raw["source_content_sha256"],
            source_file_size_bytes=raw["source_file_size_bytes"],
            source_retrieved_on=_parse_required_date(raw["source_retrieved_on"]),
            source_reviewed_on=_parse_required_date(raw["source_reviewed_on"]),
            review_method=ApplicantEvidenceReviewMethod(raw["review_method"]),
            evidence_grade=ApplicantEvidenceGrade(raw["evidence_grade"]),
            evidence_status=ApplicantEvidenceStatus(raw["evidence_status"]),
            claim_text=raw["claim_text"],
            relationship=AchievementEvidenceRelationship(raw["relationship"]),
            note=raw.get("note"),
        )
    except ValueError as error:
        raise ValidationError(
            "INVALID_ACHIEVEMENT_EVIDENCE_ENUM",
            "成果证据包含不支持的分类值",
        ) from error


def _parse_mock_subject_results(value: str) -> dict[str, MockSubjectResultInput]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValidationError(
            "INVALID_MOCK_SUBJECT_RESULTS_JSON",
            "subject-results-json必须是有效JSON对象",
            {"column": error.colno},
        ) from error
    if not isinstance(parsed, dict):
        raise ValidationError(
            "INVALID_MOCK_SUBJECT_RESULTS_JSON",
            "subject-results-json顶层必须是JSON对象",
        )

    allowed_fields = {
        "attendance_status",
        "score_lower",
        "score_upper",
        "started_at",
        "ended_at",
        "note",
    }
    subject_results: dict[str, MockSubjectResultInput] = {}
    for subject_code, raw_result in parsed.items():
        subject_results[str(subject_code)] = _parse_mock_subject_result(
            str(subject_code),
            raw_result,
            allowed_fields,
        )
    return subject_results


def _parse_mock_subject_result(
    subject_code: str,
    raw_result: Any,
    allowed_fields: set[str],
) -> MockSubjectResultInput:
    if not isinstance(raw_result, dict):
        raise ValidationError(
            "INVALID_MOCK_SUBJECT_RESULT",
            f"{subject_code}的科目结果必须是JSON对象",
            {"subject_code": subject_code},
        )
    unknown_fields = sorted(set(raw_result) - allowed_fields)
    if unknown_fields:
        raise ValidationError(
            "UNKNOWN_MOCK_SUBJECT_RESULT_FIELD",
            f"{subject_code}包含未知科目结果字段",
            {"subject_code": subject_code, "fields": unknown_fields},
        )
    try:
        attendance_status = MockAttendanceStatus(raw_result.get("attendance_status"))
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "INVALID_MOCK_ATTENDANCE",
            f"{subject_code}的attendance_status无效",
            {
                "subject_code": subject_code,
                "allowed": [status.value for status in MockAttendanceStatus],
            },
        ) from error
    return MockSubjectResultInput(
        attendance_status=attendance_status,
        score_lower=raw_result.get("score_lower"),
        score_upper=raw_result.get("score_upper"),
        started_at=_parse_optional_datetime(
            raw_result.get("started_at"),
            f"{subject_code}.started_at",
        ),
        ended_at=_parse_optional_datetime(
            raw_result.get("ended_at"),
            f"{subject_code}.ended_at",
        ),
        note=raw_result.get("note"),
    )


def _parse_optional_datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            "INVALID_DATETIME",
            f"{field_name}必须是包含时区的ISO 8601时间字符串",
            {"field": field_name},
        )
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(
            "INVALID_DATETIME",
            f"{field_name}必须是有效ISO 8601时间字符串：{value}",
            {"field": field_name, "value": value},
        ) from error


COMMAND_HANDLERS: dict[str, CommandHandler] = {
    "init": _initialize_database,
    "import-kimi": _import_kimi,
    "summary": _get_summary,
    "projects": _list_projects,
    "issues": _list_issues,
    "issue-resolve": _resolve_issue,
    "official-observation-add": _add_official_observation,
    "secondary-observation-add": _add_secondary_observation,
    "policy-event-add": _add_policy_event,
    "policy-events": _list_policy_events,
    "fact-add": _add_fact,
    "fact-resolve": _resolve_fact,
    "fact-unresolve": _unresolve_fact,
    "facts": _list_facts,
    "fact-conflicts": _list_fact_conflicts,
    "verify-exam": _verify_exam,
    "preference-add": _add_preference,
    "preferences": _list_preferences,
    "preference-readiness": _get_preference_readiness,
    "context-add": _add_context,
    "contexts": _list_contexts,
    "achievement-add": _add_achievement,
    "achievements": _list_achievements,
    "fairness-review-add": _add_fairness_review,
    "fairness-reviews": _list_fairness_reviews,
    "mock-add": _add_mock,
    "mock-ledger-add": _add_mock_ledger,
    "mock-sessions": _list_mock_sessions,
    "mock-exclude": _exclude_mock_session,
    "assessment": _get_assessment,
    "machine-add": _add_machine_test,
    "machine-sessions": _list_machine_tests,
    "machine-assessment": _get_machine_assessment,
    "export": _export_catalog,
    "doctor": _run_doctor,
    "backup": _create_backup,
}
