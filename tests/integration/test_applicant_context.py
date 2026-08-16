from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import ApplicantContextDimension
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import ApplicantContextEventInput


class ApplicantContextEventTest(unittest.TestCase):
    def test_context_is_append_only_audited_and_latest_event_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))

            first_id = application.applicant_context.add_context(
                ApplicantContextEventInput(
                    dimension=ApplicantContextDimension.STUDY_PROGRESS,
                    subject_key="302.linear_algebra",
                    value={"status": "not_started", "book_purchased": True},
                    note="仅购书，尚未开始",
                ),
                str(uuid.uuid4()),
            )
            second_id = application.applicant_context.add_context(
                ApplicantContextEventInput(
                    dimension=ApplicantContextDimension.STUDY_PROGRESS,
                    subject_key="302.linear_algebra",
                    value={"status": "in_progress", "chapter": "1"},
                ),
                str(uuid.uuid4()),
            )

            current = application.applicant_context.list_contexts()
            history = application.applicant_context.list_contexts(include_history=True)
            self.assertEqual([row["event_id"] for row in current], [second_id])
            self.assertEqual([row["event_id"] for row in history], [first_id, second_id])
            self.assertEqual(current[0]["value"]["status"], "in_progress")

            with self.assertRaises(ValidationError):
                application.applicant_context.add_context(
                    ApplicantContextEventInput(
                        dimension=ApplicantContextDimension.STUDY_PROGRESS,
                        subject_key="101",
                        value={"status": "not_measured"},
                    ),
                    str(uuid.uuid4()),
                )

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                audit_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM audit_events
                    WHERE event_type = 'applicant_context_event_added'
                    """
                ).fetchone()[0]
                self.assertEqual(audit_count, 2)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE applicant_context_events SET note = 'x' WHERE id = ?",
                        (first_id,),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "DELETE FROM applicant_context_events WHERE id = ?",
                        (first_id,),
                    )

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["context_missing_audit"], 0)


if __name__ == "__main__":
    unittest.main()
