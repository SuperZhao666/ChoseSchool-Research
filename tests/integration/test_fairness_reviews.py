from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import EvidenceDocumentType, FairnessReviewConclusion
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import FairnessReviewInput, OfficialProjectObservationInput


class FairnessReviewTest(unittest.TestCase):
    def test_review_is_project_year_scoped_append_only_and_evidence_backed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            observation = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            )

            with self.assertRaises(ValidationError):
                application.fairness_reviews.add_review(
                    FairnessReviewInput(
                        observation_id=observation.observation_id,
                        conclusion=FairnessReviewConclusion.FAVORABLE,
                        summary="不能无证据通过",
                    ),
                    str(uuid.uuid4()),
                )

            review_id = application.fairness_reviews.add_review(
                FairnessReviewInput(
                    observation_id=observation.observation_id,
                    conclusion=FairnessReviewConclusion.MIXED,
                    summary="规则透明，但没有本科来源录取率，不能称绝对友好。",
                    evidence=(
                        {
                            "source_title": "复试办法",
                            "source_url": "https://example.edu/retest",
                            "source_type": "official_rule",
                            "signal": "supportive",
                            "content_sha256": "a" * 64,
                            "retrieved_date": "2026-08-11",
                            "excerpt": "复试规则与成绩计算方式公开。",
                        },
                    ),
                ),
                str(uuid.uuid4()),
            )
            current = application.fairness_reviews.list_reviews(
                observation_id=observation.observation_id
            )
            self.assertEqual(current[0]["review_id"], review_id)
            self.assertEqual(current[0]["conclusion"], "mixed")
            self.assertEqual(len(current[0]["evidence"]), 1)

            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE candidate_fairness_reviews SET conclusion='favorable' WHERE id=?",
                        (review_id,),
                    )
            doctor = application.catalog.doctor()
            self.assertEqual(doctor["fairness_review_missing_audit"], 0)


def _official_observation() -> OfficialProjectObservationInput:
    return OfficialProjectObservationInput(
        school="测试大学",
        college="计算机学院",
        program_code="085404",
        program_name="计算机技术",
        admission_year=2027,
        politics_code="101",
        english_code="204",
        math_code="302",
        professional_code="408",
        source_title="2027招生目录",
        source_url="https://example.edu/catalog",
        source_institution="测试大学研究生院",
        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
        source_content_sha256="b" * 64,
        applicable_year=2027,
        retrieved_date=date(2026, 8, 11),
        published_date=date(2026, 8, 11),
    )


if __name__ == "__main__":
    unittest.main()
