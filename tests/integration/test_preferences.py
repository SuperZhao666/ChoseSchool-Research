from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import (
    PreferenceAcceptanceLevel,
    PreferenceDimension,
)
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import PreferenceEventInput


class PreferenceEventTest(unittest.TestCase):
    def test_preferences_are_append_only_and_latest_event_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))

            first_trace_id = str(uuid.uuid4())
            first_event_id = application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.REGION,
                    subject_key=" 新疆 ",
                    acceptance_level=PreferenceAcceptanceLevel.RELUCTANT,
                    note="距离远，先保留为条件路线",
                ),
                first_trace_id,
            )
            second_trace_id = str(uuid.uuid4())
            second_event_id = application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.REGION,
                    subject_key="新疆",
                    acceptance_level=PreferenceAcceptanceLevel.REJECT,
                    note="最终确认不接受",
                ),
                second_trace_id,
            )

            current = application.preferences.list_preferences()
            history = application.preferences.list_preferences(include_history=True)
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["event_id"], second_event_id)
            self.assertEqual(current[0]["acceptance_level"], "reject")
            self.assertEqual(current[0]["value"], {})
            self.assertEqual(
                [row["event_id"] for row in history],
                [first_event_id, second_event_id],
            )
            self.assertEqual(
                application.catalog.doctor()["preference_missing_audit"],
                0,
            )

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                audit = connection.execute(
                    """
                    SELECT trace_id, entity_id
                    FROM audit_events
                    WHERE event_type = 'preference_event_added'
                    ORDER BY id
                    """
                ).fetchall()
                self.assertEqual(
                    audit,
                    [
                        (first_trace_id, str(first_event_id)),
                        (second_trace_id, str(second_event_id)),
                    ],
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        UPDATE applicant_preference_events
                        SET acceptance_level = 'accept'
                        WHERE id = ?
                        """,
                        (first_event_id,),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "DELETE FROM applicant_preference_events WHERE id = ?",
                        (first_event_id,),
                    )

    def test_preference_validation_rejects_ambiguous_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))

            with self.assertRaises(ValidationError):
                application.preferences.add_preference(
                    PreferenceEventInput(
                        dimension=PreferenceDimension.PROGRAM_CODE,
                        subject_key="0854",
                        acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    ),
                    str(uuid.uuid4()),
                )

            with self.assertRaises(ValidationError):
                application.preferences.add_preference(
                    PreferenceEventInput(
                        dimension=PreferenceDimension.REGION,
                        subject_key="山东",
                        acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    ),
                    " ",
                )

            with self.assertRaises(ValidationError):
                application.preferences.add_preference(
                    PreferenceEventInput(
                        dimension=PreferenceDimension.TUITION_CEILING,
                        subject_key="default",
                        acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                        value={"amount": 90000, "basis": "all", "currency": "CNY"},
                    ),
                    str(uuid.uuid4()),
                )

            event_id = application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.TUITION_CEILING,
                    subject_key="default",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    value={"currency": "CNY", "basis": "total", "amount": 90000},
                ),
                str(uuid.uuid4()),
            )
            current = application.preferences.list_preferences(
                dimension="tuition_ceiling",
                subject_key="default",
            )
            self.assertEqual(current[0]["event_id"], event_id)
            self.assertEqual(
                current[0]["value"],
                {"amount": 90000, "basis": "total", "currency": "CNY"},
            )

            no_cap_id = application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.TUITION_CEILING,
                    subject_key="default",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    value={"mode": "no_hard_cap"},
                ),
                str(uuid.uuid4()),
            )
            current = application.preferences.list_preferences(
                dimension="tuition_ceiling",
                subject_key="default",
            )
            self.assertEqual(current[0]["event_id"], no_cap_id)
            self.assertEqual(current[0]["value"], {"mode": "no_hard_cap"})

    def test_preference_readiness_requires_v2_explicit_atomic_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))

            application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                    subject_key="985_priority_211_hedge",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                ),
                str(uuid.uuid4()),
            )
            initial = application.preferences.summarize_readiness()
            self.assertEqual(initial.required_subject_count, 23)
            self.assertEqual(initial.answered_subject_count, 0)
            self.assertEqual(initial.current_preference_event_count, 1)
            self.assertFalse(initial.is_preference_intake_complete)
            self.assertEqual(len(initial.missing_subjects), 23)
            self.assertEqual(
                initial.ranking_preferences,
                ("school_tier_requirement:985_priority_211_hedge",),
            )

            required_events = [
                PreferenceEventInput(
                    dimension=PreferenceDimension.REGION,
                    subject_key="actual_training_scope",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    value={"mode": "mainland"},
                ),
                PreferenceEventInput(
                    dimension=PreferenceDimension.TUITION_CEILING,
                    subject_key="default",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                    value={
                        "mode": "no_hard_cap",
                    },
                ),
                PreferenceEventInput(
                    dimension=PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                    subject_key="211_floor",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                ),
                PreferenceEventInput(
                    dimension=PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                    subject_key="non_211_acceptable",
                    acceptance_level=PreferenceAcceptanceLevel.REJECT,
                ),
            ]
            required_events.extend(
                PreferenceEventInput(
                    dimension=PreferenceDimension.JOINT_TRAINING,
                    subject_key=subject_key,
                    acceptance_level=PreferenceAcceptanceLevel.REJECT,
                )
                for subject_key in (
                    "offsite",
                    "enterprise",
                    "international",
                    "unknown_assignment",
                )
            )
            required_events.append(
                PreferenceEventInput(
                    dimension=PreferenceDimension.PROGRAM_CODE,
                    subject_key="any_other_eligible_code",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                )
            )
            required_events.extend(
                PreferenceEventInput(
                    dimension=PreferenceDimension.PROGRAM_CODE,
                    subject_key=subject_key,
                    acceptance_level=(
                        PreferenceAcceptanceLevel.ACCEPT
                        if subject_key in ("085404", "085405")
                        else PreferenceAcceptanceLevel.REJECT
                    ),
                )
                for subject_key in (
                    "085404",
                    "085405",
                    "085410",
                    "085411",
                    "085412",
                    "085400",
                    "145200",
                )
            )
            required_events.extend(
                PreferenceEventInput(
                    dimension=PreferenceDimension.ADMISSION_FAIRNESS,
                    subject_key=subject_key,
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                )
                for subject_key in (
                    "ordinary_undergraduate_nondiscrimination",
                    "evidence_backed_fair_reputation",
                )
            )
            required_events.extend(
                PreferenceEventInput(
                    dimension=PreferenceDimension.RETEST_FORMAT,
                    subject_key=subject_key,
                    acceptance_level=PreferenceAcceptanceLevel.RELUCTANT,
                )
                for subject_key in (
                    "machine_test",
                    "written_test",
                    "theory_closed_book",
                    "pure_interview",
                    "high_weight_interview",
                )
            )
            for preference in required_events:
                application.preferences.add_preference(
                    preference,
                    str(uuid.uuid4()),
                )

            complete = application.preferences.summarize_readiness()
            self.assertEqual(complete.required_subject_count, 23)
            self.assertEqual(complete.answered_subject_count, 23)
            self.assertEqual(complete.current_preference_event_count, 24)
            self.assertTrue(complete.is_preference_intake_complete)
            self.assertEqual(complete.missing_subjects, ())
            self.assertEqual(complete.unknown_subjects, ())
            self.assertEqual(complete.contradictory_subjects, ())
            self.assertEqual(complete.unsupported_subjects, ())

            application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.SCHOOL_TIER_REQUIREMENT,
                    subject_key="non_211_acceptable",
                    acceptance_level=PreferenceAcceptanceLevel.ACCEPT,
                ),
                str(uuid.uuid4()),
            )
            contradictory = application.preferences.summarize_readiness()
            self.assertFalse(contradictory.is_preference_intake_complete)
            self.assertEqual(
                contradictory.contradictory_subjects,
                (
                    "school_tier_requirement:211_floor"
                    "|non_211_acceptable:MUST_BE_COMPLEMENTARY",
                ),
            )

            application.preferences.add_preference(
                PreferenceEventInput(
                    dimension=PreferenceDimension.RETEST_FORMAT,
                    subject_key="machine_test",
                    acceptance_level=PreferenceAcceptanceLevel.UNKNOWN,
                ),
                str(uuid.uuid4()),
            )
            unknown = application.preferences.summarize_readiness()
            self.assertEqual(unknown.answered_subject_count, 22)
            self.assertIn(
                "retest_format:machine_test",
                unknown.unknown_subjects,
            )
            self.assertFalse(unknown.is_preference_intake_complete)


if __name__ == "__main__":
    unittest.main()
