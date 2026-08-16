from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import (
    AchievementCategory,
    AchievementEvidenceRelationship,
    AchievementParticipationType,
    AchievementScopeLevel,
    AchievementStage,
    AchievementVerificationStatus,
    ApplicantEvidenceAccessScope,
    ApplicantEvidenceDocumentType,
    ApplicantEvidenceGrade,
    ApplicantEvidenceReviewMethod,
    ApplicantEvidenceStatus,
)
from chose_school.domain.errors import StateConflictError, ValidationError
from chose_school.domain.models import ApplicantAchievementInput, ApplicantEvidenceInput


class ApplicantAchievementLedgerTest(unittest.TestCase):
    def test_pat_two_documents_form_one_idempotent_audited_achievement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            achievement = _pat_achievement()

            first = application.applicant_achievements.add_achievement(
                achievement,
                str(uuid.uuid4()),
            )
            replay = application.applicant_achievements.add_achievement(
                achievement,
                str(uuid.uuid4()),
            )

            self.assertTrue(first.created)
            self.assertFalse(replay.created)
            self.assertEqual(replay.event_id, first.event_id)
            self.assertEqual(len(first.evidence_document_ids), 2)

            current = application.applicant_achievements.list_achievements()
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["achievement_key"], "pat.2024-summer.basic")
            self.assertEqual(current[0]["details"]["score"], {"maximum": 100, "obtained": 94})
            self.assertEqual(current[0]["details"]["rank"], {"population": 279, "position": 29})
            self.assertEqual(len(current[0]["evidence"]), 2)
            self.assertNotIn("source_title", current[0]["evidence"][0])
            self.assertNotIn("claim_text", current[0]["evidence"][0])

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                counts = {
                    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "applicant_achievement_events",
                        "applicant_evidence_documents",
                        "applicant_achievement_evidence_links",
                        "applicant_evidence_review_events",
                        "applicant_achievement_evidence_review_links",
                    )
                }
                self.assertEqual(counts["applicant_achievement_events"], 1)
                self.assertEqual(counts["applicant_evidence_documents"], 2)
                self.assertEqual(counts["applicant_achievement_evidence_links"], 2)
                self.assertEqual(counts["applicant_evidence_review_events"], 2)
                self.assertEqual(
                    counts["applicant_achievement_evidence_review_links"],
                    2,
                )
                audit_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM audit_events
                    WHERE event_type IN (
                        'applicant_achievement_event_added',
                        'applicant_evidence_document_added',
                        'applicant_achievement_evidence_link_added',
                        'applicant_evidence_review_added',
                        'applicant_achievement_evidence_review_link_added'
                    )
                    """
                ).fetchone()[0]
                self.assertEqual(audit_count, 9)

                for table in (
                    "applicant_achievement_events",
                    "applicant_evidence_documents",
                    "applicant_achievement_evidence_links",
                    "applicant_evidence_review_events",
                    "applicant_achievement_evidence_review_links",
                ):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"UPDATE {table} SET trace_id = 'x'")
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"DELETE FROM {table}")

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["applicant_achievement_event_count"], 1)
            self.assertEqual(doctor["applicant_evidence_document_count"], 2)
            self.assertTrue(
                all(
                    count == 0
                    for name, count in doctor.items()
                    if name.startswith("applicant_")
                    and name not in {
                        "applicant_achievement_event_count",
                        "applicant_evidence_document_count",
                        "applicant_evidence_review_event_count",
                        "applicant_achievement_evidence_review_link_count",
                    }
                )
            )

    def test_same_key_revision_is_current_and_hash_metadata_conflict_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            original = _pat_achievement()
            first = application.applicant_achievements.add_achievement(
                original,
                str(uuid.uuid4()),
            )
            corrected = ApplicantAchievementInput(
                **{
                    **original.__dict__,
                    "result": "乙级三等奖（复核版）",
                    "note": "以追加事件形成修订，不覆盖旧成果事件",
                }
            )
            second = application.applicant_achievements.add_achievement(
                corrected,
                str(uuid.uuid4()),
            )
            self.assertNotEqual(first.event_id, second.event_id)
            current = application.applicant_achievements.list_achievements()
            history = application.applicant_achievements.list_achievements(
                include_history=True
            )
            self.assertEqual([row["event_id"] for row in current], [second.event_id])
            self.assertEqual(
                [row["event_id"] for row in history],
                [first.event_id, second.event_id],
            )

            conflicting_evidence = ApplicantEvidenceInput(
                **{
                    **original.evidence[0].__dict__,
                    "source_title": "与同一哈希不一致的来源标题",
                }
            )
            conflicting = ApplicantAchievementInput(
                **{
                    **original.__dict__,
                    "achievement_key": "pat.2024-summer.conflict-probe",
                    "evidence": (conflicting_evidence,),
                }
            )
            with self.assertRaises(StateConflictError) as caught:
                application.applicant_achievements.add_achievement(
                    conflicting,
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                caught.exception.error_code,
                "APPLICANT_EVIDENCE_METADATA_CONFLICT",
            )
            self.assertEqual(
                len(application.applicant_achievements.list_achievements(include_history=True)),
                2,
            )

    def test_service_rejects_inflated_or_unsafe_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            base = _pat_achievement()

            cases = (
                (
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    {**base.__dict__, "details": {"certificate_number": "secret"}},
                ),
                (
                    "COMPOSITE_RANK_REQUIRED",
                    {**base.__dict__, "details": {"rank": 29}},
                ),
                (
                    "INVALID_SCHOLARSHIP_PARTICIPATION",
                    {
                        **base.__dict__,
                        "category": AchievementCategory.SCHOLARSHIP,
                        "stage": AchievementStage.ACADEMIC_YEAR,
                    },
                ),
                (
                    "TEAM_NAME_REQUIRED",
                    {
                        **base.__dict__,
                        "participation_type": AchievementParticipationType.TEAM,
                        "team_name": None,
                    },
                ),
            )
            for expected_code, values in cases:
                with self.subTest(expected_code=expected_code):
                    with self.assertRaises(ValidationError) as caught:
                        application.applicant_achievements.add_achievement(
                            ApplicantAchievementInput(**values),
                            str(uuid.uuid4()),
                        )
                    self.assertEqual(caught.exception.error_code, expected_code)

            weak_evidence = ApplicantEvidenceInput(
                **{
                    **base.evidence[0].__dict__,
                    "review_method": ApplicantEvidenceReviewMethod.METADATA_ONLY,
                    "evidence_status": ApplicantEvidenceStatus.METADATA_ONLY,
                }
            )
            with self.assertRaises(ValidationError) as caught:
                application.applicant_achievements.add_achievement(
                    ApplicantAchievementInput(
                        **{**base.__dict__, "evidence": (weak_evidence,)}
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(caught.exception.error_code, "VISUAL_SUPPORT_REQUIRED")

    def test_v2_note_revision_and_same_document_review_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            original = _pat_achievement()
            first = application.applicant_achievements.add_achievement(
                original,
                str(uuid.uuid4()),
            )
            note_revision = ApplicantAchievementInput(
                **{**original.__dict__, "note": "说明发生语义修订，必须追加新版本"}
            )
            second = application.applicant_achievements.add_achievement(
                note_revision,
                str(uuid.uuid4()),
            )
            self.assertTrue(second.created)
            self.assertNotEqual(first.event_id, second.event_id)

            reviewed_evidence = ApplicantEvidenceInput(
                **{
                    **original.evidence[0].__dict__,
                    "source_reviewed_on": date(2026, 8, 12),
                    "claim_text": "复核后更正了证据主张，但原始文件身份不变",
                    "evidence_status": ApplicantEvidenceStatus.CONFLICT,
                    "relationship": AchievementEvidenceRelationship.CONTRADICTS,
                }
            )
            review_revision = ApplicantAchievementInput(
                **{
                    **original.__dict__,
                    "verification_status": AchievementVerificationStatus.CONFLICT,
                    "evidence": (reviewed_evidence, original.evidence[1]),
                    "note": "同一文件追加复核版本并将成果保持为冲突",
                }
            )
            third = application.applicant_achievements.add_achievement(
                review_revision,
                str(uuid.uuid4()),
            )
            replay = application.applicant_achievements.add_achievement(
                review_revision,
                str(uuid.uuid4()),
            )
            self.assertTrue(third.created)
            self.assertFalse(replay.created)

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                event_count = connection.execute(
                    "SELECT COUNT(*) FROM applicant_achievement_events"
                ).fetchone()[0]
                document_count = connection.execute(
                    "SELECT COUNT(*) FROM applicant_evidence_documents"
                ).fetchone()[0]
                review_count = connection.execute(
                    "SELECT COUNT(*) FROM applicant_evidence_review_events"
                ).fetchone()[0]
                self.assertEqual(event_count, 3)
                self.assertEqual(document_count, 2)
                self.assertEqual(review_count, 3)
                versions = connection.execute(
                    "SELECT DISTINCT fingerprint_version FROM applicant_achievement_events"
                ).fetchall()
                self.assertEqual(versions, [("v2",)])

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["applicant_evidence_review_event_count"], 3)

    def test_rejects_official_grade_contradiction_and_sensitive_bypasses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            base = _pat_achievement()

            official = ApplicantEvidenceInput(
                **{
                    **base.evidence[0].__dict__,
                    "source_url": "https://example.edu.cn/verification.pdf",
                    "source_access_scope": ApplicantEvidenceAccessScope.PUBLIC_WEB,
                    "evidence_grade": ApplicantEvidenceGrade.OFFICIAL_ONLINE_VERIFICATION,
                }
            )
            contradicts = ApplicantEvidenceInput(
                **{
                    **base.evidence[0].__dict__,
                    "relationship": AchievementEvidenceRelationship.CONTRADICTS,
                }
            )
            conflict_status = ApplicantEvidenceInput(
                **{
                    **base.evidence[0].__dict__,
                    "evidence_status": ApplicantEvidenceStatus.CONFLICT,
                }
            )
            cases = (
                (
                    "OFFICIAL_ONLINE_VERIFICATION_NOT_CONFIGURED",
                    {**base.__dict__, "evidence": (official,)},
                ),
                (
                    "CONTRADICTED_ACHIEVEMENT_CANNOT_BE_CONFIRMED",
                    {**base.__dict__, "evidence": (contradicts, base.evidence[1])},
                ),
                (
                    "CONTRADICTED_ACHIEVEMENT_CANNOT_BE_CONFIRMED",
                    {**base.__dict__, "evidence": (conflict_status,)},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    {**base.__dict__, "details": {"certificateNumber": "secret"}},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    {**base.__dict__, "details": {"证书号码": "secret"}},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    {**base.__dict__, "details": {"cert_no": "secret"}},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    {**base.__dict__, "details": {"award_certificate_number": "secret"}},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_DETAIL_FORBIDDEN",
                    {**base.__dict__, "details": {"student_no": "secret"}},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "证书编号: ABCD-123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "cert no: ABCD-123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "student no: 2024123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "certificate serial: ABCD123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "证书序列号: ABCD123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "CERT_NO=ABCD123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "student_id=2024123456"},
                ),
                (
                    "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
                    {**base.__dict__, "note": "certificate-number=ABCD123456"},
                ),
            )
            for expected_code, values in cases:
                with self.subTest(expected_code=expected_code):
                    with self.assertRaises(ValidationError) as caught:
                        application.applicant_achievements.add_achievement(
                            ApplicantAchievementInput(**values),
                            str(uuid.uuid4()),
                        )
                    self.assertEqual(caught.exception.error_code, expected_code)

            sensitive_evidence = ApplicantEvidenceInput(
                **{
                    **base.evidence[0].__dict__,
                    "claim_text": "学号=2024123456",
                }
            )
            with self.assertRaises(ValidationError) as caught:
                application.applicant_achievements.add_achievement(
                    ApplicantAchievementInput(
                        **{**base.__dict__, "evidence": (sensitive_evidence,)}
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                caught.exception.error_code,
                "SENSITIVE_ACHIEVEMENT_TEXT_FORBIDDEN",
            )

    def test_private_url_is_redacted_and_doctor_detects_unsupported_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            result = application.applicant_achievements.add_achievement(
                _pat_achievement(),
                str(uuid.uuid4()),
            )
            listed = application.applicant_achievements.list_achievements()
            self.assertEqual(len(listed), 1)
            self.assertIsNone(listed[0]["evidence"][0]["source_url"])
            self.assertEqual(
                listed[0]["evidence"][0]["source_access_scope"],
                "private_user_drive",
            )

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "DROP TRIGGER applicant_evidence_review_events_no_update"
                )
                connection.execute(
                    """
                    UPDATE applicant_evidence_review_events
                    SET evidence_grade = 'official_online_verification'
                    WHERE id = (
                        SELECT review_link.evidence_review_event_id
                        FROM applicant_achievement_evidence_review_links review_link
                        JOIN applicant_achievement_evidence_links link
                          ON link.id = review_link.achievement_evidence_link_id
                        WHERE link.achievement_event_id = ?
                        LIMIT 1
                    )
                    """,
                    (result.event_id,),
                )
                connection.commit()

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "error")
            self.assertEqual(
                doctor["applicant_evidence_official_online_verification_unsupported"],
                1,
            )

    def test_historical_v1_replay_does_not_restore_an_obsolete_current_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            original = _pat_achievement()
            first = application.applicant_achievements.add_achievement(
                original,
                str(uuid.uuid4()),
            )
            with closing(sqlite3.connect(application.database.database_path)) as connection:
                connection.execute("DROP TRIGGER applicant_achievement_events_no_update")
                connection.execute(
                    """
                    UPDATE applicant_achievement_events
                    SET fingerprint_version = 'v1', event_fingerprint = ?
                    WHERE id = ?
                    """,
                    ("f" * 64, first.event_id),
                )
                connection.commit()

            revision = ApplicantAchievementInput(
                **{**original.__dict__, "note": "当前采用的新说明"}
            )
            current = application.applicant_achievements.add_achievement(
                revision,
                str(uuid.uuid4()),
            )
            replay = application.applicant_achievements.add_achievement(
                original,
                str(uuid.uuid4()),
            )

            self.assertFalse(replay.created)
            self.assertEqual(replay.event_id, first.event_id)
            self.assertEqual(
                application.applicant_achievements.list_achievements()[0]["event_id"],
                current.event_id,
            )
            self.assertEqual(
                len(application.applicant_achievements.list_achievements(include_history=True)),
                2,
            )

    def test_public_evidence_url_rejects_embedded_personal_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            base = _pat_achievement()
            unsafe_urls = (
                "https://example.edu.cn/check?studentId=2024123456",
                "https://example.edu.cn/studentId/2024123456/file.pdf",
                "https://example.edu.cn/certificateNumber/ABCD1234",
                "https://example.edu.cn/check#studentNo=2024123456",
            )
            for unsafe_url in unsafe_urls:
                with self.subTest(unsafe_url=unsafe_url):
                    unsafe = ApplicantEvidenceInput(
                        **{
                            **base.evidence[0].__dict__,
                            "source_url": unsafe_url,
                            "source_access_scope": ApplicantEvidenceAccessScope.PUBLIC_WEB,
                        }
                    )
                    with self.assertRaises(ValidationError) as caught:
                        application.applicant_achievements.add_achievement(
                            ApplicantAchievementInput(
                                **{**base.__dict__, "evidence": (unsafe,)}
                            ),
                            str(uuid.uuid4()),
                        )
                    self.assertEqual(
                        caught.exception.error_code,
                        "SENSITIVE_ACHIEVEMENT_URL_FORBIDDEN",
                    )


def _pat_achievement() -> ApplicantAchievementInput:
    return ApplicantAchievementInput(
        achievement_key="pat.2024-summer.basic",
        category=AchievementCategory.COMPETITION_AWARD,
        title="2024 夏季攀拓计算机能力测评—程序设计（乙级）",
        issuer="攀拓计算机能力测评考试中心",
        achievement_year=2024,
        period_label="2024 年夏季；测评日期 2024-06-02",
        awarded_on=date(2024, 6, 2),
        scope_level=AchievementScopeLevel.NOT_APPLICABLE,
        stage=AchievementStage.ASSESSMENT,
        result="乙级三等奖",
        participation_type=AchievementParticipationType.INDIVIDUAL,
        team_name=None,
        details={
            "competition_family": "PAT",
            "division": "Master",
            "score": {"obtained": 94, "maximum": 100},
            "rank": {"position": 29, "population": 279},
        },
        verification_status=AchievementVerificationStatus.DOCUMENT_CONFIRMED,
        evidence=(
            _evidence(1, ApplicantEvidenceDocumentType.AWARD_CERTIFICATE),
            _evidence(2, ApplicantEvidenceDocumentType.SCORE_CERTIFICATE),
        ),
        note="两份文档支持同一次测评，只形成一条成果记录",
    )


def _evidence(
    index: int,
    document_type: ApplicantEvidenceDocumentType,
) -> ApplicantEvidenceInput:
    return ApplicantEvidenceInput(
        source_title=f"PAT 证据文件 {index}",
        source_url=f"https://drive.google.com/file/d/test-{index}/view",
        source_access_scope=ApplicantEvidenceAccessScope.PRIVATE_USER_DRIVE,
        source_document_type=document_type,
        source_mime_type="application/pdf",
        source_content_sha256=str(index) * 64,
        source_file_size_bytes=1000 + index,
        source_retrieved_on=date(2026, 8, 11),
        source_reviewed_on=date(2026, 8, 11),
        review_method=ApplicantEvidenceReviewMethod.FULL_DOCUMENT_VISUAL_REVIEW,
        evidence_grade=ApplicantEvidenceGrade.PRIMARY_DOCUMENT_USER_COPY,
        evidence_status=ApplicantEvidenceStatus.DOCUMENT_VISUAL_CONFIRMED,
        claim_text="证书正文支持该成果，尚未由主办方在线独立核验",
        relationship=AchievementEvidenceRelationship.SUPPORTS,
    )


if __name__ == "__main__":
    unittest.main()
