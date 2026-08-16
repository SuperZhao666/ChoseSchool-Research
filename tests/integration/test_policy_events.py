from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing, redirect_stderr
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

from tests.support import build_test_application

from chose_school.access.cli_parser import parse_arguments
from chose_school.domain.enums import (
    EvidenceDocumentType,
    PolicyEventStatus,
    PolicyEventType,
)
from chose_school.domain.errors import (
    EntityNotFoundError,
    StateConflictError,
    ValidationError,
)
from chose_school.domain.models import (
    OfficialProjectObservationInput,
    PolicyEventFilter,
    PolicyEventInput,
)


class PolicyEventTest(unittest.TestCase):
    def test_policy_events_are_append_only_idempotent_audited_and_strict_neutral(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            observation = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            )
            before = _strict_state_counts(
                application.database.database_path,
                observation.observation_id,
            )
            event = _policy_event(observation.observation_id)
            first_trace = str(uuid.uuid4())
            first = application.policy_events.add_event(event, first_trace)
            replay = application.policy_events.add_event(
                replace(
                    event,
                    school=f"  {event.school}  ",
                    source_content_sha256=event.source_content_sha256.upper(),
                ),
                str(uuid.uuid4()),
            )

            self.assertTrue(first.created)
            self.assertFalse(replay.created)
            self.assertEqual(replay.event_id, first.event_id)
            self.assertEqual(first.event_status, PolicyEventStatus.PENDING_DIRECTORY)

            revised = application.policy_events.add_event(
                replace(
                    event,
                    description="公告修订版仍明确最终以2027正式目录为准",
                    source_title="2027年初试科目调整公告（修订版）",
                    source_url="https://example.edu/notice/2027-change-v2",
                    source_content_sha256="c" * 64,
                    supersedes_event_id=first.event_id,
                ),
                str(uuid.uuid4()),
            )
            self.assertTrue(revised.created)
            self.assertNotEqual(revised.event_id, first.event_id)

            history = application.policy_events.list_events(
                PolicyEventFilter(observation_id=observation.observation_id)
            )
            current = application.policy_events.list_events(
                PolicyEventFilter(
                    observation_id=observation.observation_id,
                    current_only=True,
                )
            )
            self.assertEqual([row["event_id"] for row in history], [1, 2])
            self.assertEqual([row["event_id"] for row in current], [2])
            self.assertTrue(all(row["can_confirm_strict_22408"] == 0 for row in history))
            self.assertTrue(
                all(row["establishes_official_catalog"] == 0 for row in history)
            )

            after = _strict_state_counts(
                application.database.database_path,
                observation.observation_id,
            )
            self.assertEqual(after, before)

            with closing(sqlite3.connect(application.database.database_path)) as connection:
                policy_count = connection.execute(
                    "SELECT COUNT(*) FROM policy_events"
                ).fetchone()[0]
                source_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM evidence_sources
                    WHERE document_type = 'official_notice'
                    """
                ).fetchone()[0]
                audit_rows = connection.execute(
                    """
                    SELECT trace_id, entity_id, payload_json
                    FROM audit_events
                    WHERE event_type = 'policy_event_added'
                    ORDER BY id
                    """
                ).fetchall()
                self.assertEqual(policy_count, 2)
                self.assertEqual(source_count, 2)
                self.assertEqual(len(audit_rows), 2)
                self.assertEqual(audit_rows[0][0], first_trace)
                self.assertFalse(
                    json.loads(audit_rows[0][2])["can_confirm_strict_22408"]
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE policy_events SET description = 'changed' WHERE id = 1"
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("DELETE FROM policy_events WHERE id = 1")

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["policy_event_missing_audit"], 0)
            self.assertEqual(doctor["policy_event_duplicate_audit"], 0)

    def test_policy_event_replay_checks_source_metadata_and_same_source_can_correct(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            observation = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            )
            event = _policy_event(observation.observation_id)
            first = application.policy_events.add_event(event, str(uuid.uuid4()))

            with self.assertRaises(StateConflictError) as metadata_conflict:
                application.policy_events.add_event(
                    replace(
                        event,
                        source_title="同一内容哈希下的冲突来源标题",
                        source_url="https://mirror.example.edu/conflicting-location",
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                metadata_conflict.exception.error_code,
                "SOURCE_IDENTITY_METADATA_CONFLICT",
            )

            correction = application.policy_events.add_event(
                replace(
                    event,
                    description="纠正先前的内部解析，但官方页面原始字节没有变化",
                    supersedes_event_id=first.event_id,
                ),
                str(uuid.uuid4()),
            )
            self.assertTrue(correction.created)

            with closing(
                sqlite3.connect(application.database.database_path)
            ) as connection:
                source_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM evidence_sources
                    WHERE document_type = 'official_notice'
                    """
                ).fetchone()[0]
                snapshot_count = connection.execute(
                    "SELECT COUNT(*) FROM policy_event_source_snapshots"
                ).fetchone()[0]
            self.assertEqual(source_count, 1)
            self.assertEqual(snapshot_count, 2)

            with self.assertRaises(StateConflictError) as duplicate_successor:
                application.policy_events.add_event(
                    replace(
                        event,
                        description="对同一前任创建第二条分叉修订",
                        source_title="第二条修订公告",
                        source_url="https://example.edu/notice/second-successor",
                        source_content_sha256="9" * 64,
                        supersedes_event_id=first.event_id,
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                duplicate_successor.exception.error_code,
                "POLICY_EVENT_ALREADY_SUPERSEDED",
            )

    def test_policy_event_source_snapshot_is_immutable_and_drift_is_detected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            observation = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            )
            event = _policy_event(observation.observation_id)
            added = application.policy_events.add_event(event, str(uuid.uuid4()))

            with closing(
                sqlite3.connect(application.database.database_path)
            ) as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        UPDATE evidence_sources
                        SET title = '不应成功的覆盖'
                        WHERE document_type = 'official_notice'
                        """
                    )
                connection.execute("DROP TRIGGER protect_evidence_sources_material_update")
                connection.execute(
                    """
                    UPDATE evidence_sources
                    SET title = '被后改的标题',
                        institution = '不相关机构',
                        url = 'https://tampered.invalid/source'
                    WHERE document_type = 'official_notice'
                    """
                )
                connection.commit()
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        UPDATE policy_event_source_snapshots
                        SET source_title = '不可覆盖'
                        WHERE policy_event_id = ?
                        """,
                        (added.event_id,),
                    )

            history = application.policy_events.list_events(PolicyEventFilter())
            self.assertEqual(history[0]["source_title"], event.source_title)
            self.assertEqual(history[0]["source_institution"], event.source_institution)
            self.assertEqual(history[0]["source_url"], event.source_url)
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "error")
            self.assertEqual(doctor["policy_event_source_snapshot_drift"], 1)
            self.assertEqual(doctor["evidence_source_correction_protection_missing"], 1)

    def test_policy_event_query_rejects_unknown_observation_and_fake_cli_status(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            with self.assertRaises(EntityNotFoundError) as missing_observation:
                application.policy_events.list_events(
                    PolicyEventFilter(observation_id=999_999)
                )
            self.assertEqual(
                missing_observation.exception.error_code,
                "OBSERVATION_NOT_FOUND",
            )

        parsed = parse_arguments(
            ["policy-events", "--status", PolicyEventStatus.PENDING_DIRECTORY.value]
        )
        self.assertEqual(parsed.status, PolicyEventStatus.PENDING_DIRECTORY.value)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_arguments(["policy-events", "--status", "superseded"])

    def test_policy_event_validation_and_exact_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            first_observation = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            )
            second_observation = application.official_observations.add_observation(
                replace(
                    _official_observation(),
                    school="另一所大学",
                    source_institution="另一所大学研究生院",
                    source_url="https://other.example.edu/catalog/2026",
                    source_content_sha256="d" * 64,
                ),
                str(uuid.uuid4()),
            )
            valid = _policy_event(first_observation.observation_id)
            cases = (
                ("TRACE_ID_REQUIRED", valid, "   "),
                (
                    "INVALID_SOURCE_SHA256",
                    replace(valid, source_content_sha256="bad"),
                    str(uuid.uuid4()),
                ),
                (
                    "EVIDENCE_YEAR_MISMATCH",
                    replace(valid, applicable_year=2026),
                    str(uuid.uuid4()),
                ),
                (
                    "INVALID_SOURCE_URL",
                    replace(valid, source_url="ftp://example.edu/notice"),
                    str(uuid.uuid4()),
                ),
                (
                    "SOURCE_INSTITUTION_MISMATCH",
                    replace(valid, source_institution="不相关学校研究生院"),
                    str(uuid.uuid4()),
                ),
                (
                    "POLICY_NOTICE_REQUIRED",
                    replace(
                        valid,
                        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                    ),
                    str(uuid.uuid4()),
                ),
                (
                    "POLICY_PROJECT_SCHOOL_MISMATCH",
                    replace(valid, observation_id=second_observation.observation_id),
                    str(uuid.uuid4()),
                ),
            )
            for expected_code, event, trace_id in cases:
                with self.subTest(expected_code=expected_code):
                    with self.assertRaises(ValidationError) as error:
                        application.policy_events.add_event(event, trace_id)
                    self.assertEqual(error.exception.error_code, expected_code)

            missing_school_name = "数据库中不存在的大学"
            with self.assertRaises(EntityNotFoundError) as missing_school:
                application.policy_events.add_event(
                    replace(
                        valid,
                        school=missing_school_name,
                        observation_id=None,
                        source_institution=f"{missing_school_name}研究生院",
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(missing_school.exception.error_code, "SCHOOL_NOT_FOUND")

            project_event = application.policy_events.add_event(
                valid,
                str(uuid.uuid4()),
            )
            school_event = application.policy_events.add_event(
                replace(
                    valid,
                    observation_id=None,
                    scope_text="示例大学全校相关专业",
                    description="学校级公告，不猜测绑定具体项目",
                    source_title="学校级2027科目调整公告",
                    source_url="https://example.edu/notice/2027-school-change",
                    source_content_sha256="e" * 64,
                ),
                str(uuid.uuid4()),
            )
            by_school = application.policy_events.list_events(
                PolicyEventFilter(school_keyword="示例大学")
            )
            by_observation = application.policy_events.list_events(
                PolicyEventFilter(observation_id=first_observation.observation_id)
            )
            self.assertEqual(
                {row["event_id"] for row in by_school},
                {project_event.event_id, school_event.event_id},
            )
            self.assertEqual(
                [row["event_id"] for row in by_observation],
                [project_event.event_id],
            )

    def test_doctor_detects_policy_event_without_matching_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            observation = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            )
            database_path = application.database.database_path
            now = datetime.now(timezone.utc).isoformat()
            with closing(sqlite3.connect(database_path)) as connection:
                school_id, project_id = connection.execute(
                    """
                    SELECT project.school_id, observation.project_id
                    FROM project_year_observations observation
                    JOIN projects project ON project.id = observation.project_id
                    WHERE observation.id = ?
                    """,
                    (observation.observation_id,),
                ).fetchone()
                source_hash = "f" * 64
                source_identity = hashlib.sha256(
                    json.dumps(
                        (source_hash, "official_notice", 2027),
                        ensure_ascii=False,
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
                source_id = connection.execute(
                    """
                    INSERT INTO evidence_sources(
                        identity_key, title, institution, url, evidence_grade,
                        published_date, retrieved_date, source_note,
                        created_at, updated_at, document_type,
                        content_sha256, applicable_year
                    ) VALUES (?, ?, ?, ?, 'official', ?, ?, NULL, ?, ?,
                              'official_notice', ?, 2027)
                    """,
                    (
                        source_identity,
                        "测试政策公告",
                        "示例大学研究生院",
                        "https://example.edu/notice/untracked",
                        "2026-06-01",
                        "2026-08-03",
                        now,
                        now,
                        source_hash,
                    ),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO policy_events(
                        school_id, project_id, effective_year, event_type,
                        event_status, title, description, source_id,
                        announced_on, created_at, updated_at, trace_id,
                        event_fingerprint, scope_text, source_content_sha256
                    ) VALUES (?, ?, 2027, 'subject_adjustment_notice',
                              'pending_directory', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        school_id,
                        project_id,
                        "测试政策公告",
                        "只用于doctor故障注入",
                        source_id,
                        "2026-06-01",
                        now,
                        now,
                        str(uuid.uuid4()),
                        "1" * 64,
                        "示例大学085404",
                        source_hash,
                    ),
                )
                connection.commit()

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "error")
            self.assertEqual(doctor["policy_event_missing_audit"], 1)
            self.assertEqual(doctor["policy_event_missing_source_snapshot"], 1)


def _official_observation() -> OfficialProjectObservationInput:
    return OfficialProjectObservationInput(
        school="示例大学",
        college="计算机学院",
        program_code="085404",
        program_name="计算机技术",
        admission_year=2026,
        politics_code="101",
        english_code="204",
        math_code="302",
        professional_code="408",
        source_title="2026年硕士研究生招生专业目录",
        source_url="https://example.edu/catalog/2026",
        source_institution="示例大学研究生院",
        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
        source_content_sha256="a" * 64,
        applicable_year=2026,
        published_date=date(2025, 10, 1),
        retrieved_date=date(2026, 8, 3),
        study_mode="全日制",
        degree_type="专业学位",
    )


def _policy_event(observation_id: int) -> PolicyEventInput:
    return PolicyEventInput(
        school="示例大学",
        observation_id=observation_id,
        effective_year=2027,
        event_type=PolicyEventType.SUBJECT_ADJUSTMENT_NOTICE,
        scope_text="计算机学院085404计算机技术",
        title="关于调整2027年硕士研究生招生考试初试科目的公告",
        description="第四科调整为408，完整四码及招生项目以2027正式目录为准",
        announced_on=date(2026, 6, 1),
        source_title="关于调整2027年硕士研究生招生考试初试科目的公告",
        source_url="https://example.edu/notice/2027-change",
        source_institution="示例大学研究生院",
        source_document_type=EvidenceDocumentType.OFFICIAL_NOTICE,
        source_content_sha256="b" * 64,
        applicable_year=2027,
        published_date=date(2026, 6, 1),
        retrieved_date=date(2026, 8, 3),
        note="政策公告不能确认严格22408",
    )


def _strict_state_counts(database_path: Path, observation_id: int) -> tuple[int, int, str]:
    with closing(sqlite3.connect(database_path)) as connection:
        observation_count = connection.execute(
            "SELECT COUNT(*) FROM project_year_observations"
        ).fetchone()[0]
        verification_count = connection.execute(
            "SELECT COUNT(*) FROM subject_verifications"
        ).fetchone()[0]
        strict_status = connection.execute(
            "SELECT strict_22408_status FROM v_catalog WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()[0]
    return observation_count, verification_count, strict_status


if __name__ == "__main__":
    unittest.main()
