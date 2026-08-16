from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import (
    EvidenceDocumentType,
    EvidenceGrade,
    Strict22408Status,
)
from chose_school.domain.errors import StateConflictError
from chose_school.domain.models import (
    FactClaimInput,
    SecondaryProjectObservationInput,
)


class SecondaryObservationIntegrationTest(unittest.TestCase):
    def test_append_is_idempotent_audited_and_strict_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            trace_id = str(uuid.uuid4())
            first = application.secondary_observations.add_observation(
                _observation(), trace_id
            )
            replay = application.secondary_observations.add_observation(
                _observation(), str(uuid.uuid4())
            )
            self.assertTrue(first.created)
            self.assertFalse(replay.created)
            self.assertEqual(replay.observation_id, first.observation_id)
            self.assertEqual(first.status, Strict22408Status.SECONDARY_ONLY)

            with self.assertRaises(StateConflictError) as conflict:
                application.secondary_observations.add_observation(
                    replace(_observation(), source_excerpt="相同来源的另一种解释"),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                conflict.exception.error_code,
                "SECONDARY_OBSERVATION_SOURCE_CONFLICT",
            )

            application.facts.add_claim(
                FactClaimInput(
                    observation_id=first.observation_id,
                    fact_key="retest.cutoff_total",
                    raw_value="370",
                    evidence_grade=EvidenceGrade.SECONDARY,
                    source_title=_observation().source_title,
                    source_url=_observation().source_url,
                    source_institution=_observation().source_institution,
                    source_document_type=EvidenceDocumentType.SECONDARY_SUMMARY,
                    source_content_sha256=_observation().source_content_sha256,
                    applicable_year=_observation().applicable_year,
                    published_date=_observation().published_date,
                    retrieved_date=_observation().retrieved_date,
                    population_scope="085404全日制普通统考",
                    statistic_scope="2025年进入复试初试总分线",
                    note="二级文章中的原子复试线主张",
                ),
                str(uuid.uuid4()),
            )

            with closing(sqlite3.connect(application.database.database_path)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    "SELECT * FROM project_year_observations WHERE id = ?",
                    (first.observation_id,),
                ).fetchone()
                source = connection.execute(
                    """
                    SELECT es.* FROM evidence_sources es
                    JOIN observation_sources os ON os.source_id = es.id
                    WHERE os.observation_id = ?
                    """,
                    (first.observation_id,),
                ).fetchone()
                raw = connection.execute(
                    """
                    SELECT r.raw_json, b.trace_id, b.importer_version
                    FROM project_year_observations o
                    JOIN raw_catalog_rows r ON r.id = o.raw_row_id
                    JOIN source_files sf ON sf.id = r.source_file_id
                    JOIN import_batches b ON b.id = sf.batch_id
                    WHERE o.id = ?
                    """,
                    (first.observation_id,),
                ).fetchone()
                audit = connection.execute(
                    """
                    SELECT trace_id FROM audit_events
                    WHERE event_type = 'secondary_project_observation_added'
                      AND entity_id = ?
                    """,
                    (str(first.observation_id),),
                ).fetchone()
                verification_count = connection.execute(
                    "SELECT COUNT(*) FROM subject_verifications"
                ).fetchone()[0]
                observation_count = connection.execute(
                    "SELECT COUNT(*) FROM project_year_observations"
                ).fetchone()[0]
                source_count = connection.execute(
                    "SELECT COUNT(*) FROM evidence_sources"
                ).fetchone()[0]
                claim_source_id = connection.execute(
                    "SELECT source_id FROM fact_claims"
                ).fetchone()[0]

            self.assertEqual(observation_count, 1)
            self.assertEqual(source_count, 1)
            self.assertEqual(claim_source_id, source["id"])
            self.assertEqual(verification_count, 0)
            self.assertEqual(row["strict_22408_evidence_status"], "secondary_only")
            self.assertEqual(row["evidence_grade"], "secondary")
            self.assertIsNone(row["official_source"])
            numeric_columns = (
                "total_plan recommendation_actual special_plan "
                "effective_general_exam_quota retest_cutoff retest_count "
                "general_exam_admit_count admit_initial_min admit_initial_median "
                "admit_initial_mean initial_exam_weight retest_weight "
                "machine_test_weight machine_test_elimination_line tuition_per_year "
                "study_length_years first_choice_protection"
            ).split()
            self.assertTrue(all(row[column] is None for column in numeric_columns))
            self.assertEqual(source["evidence_grade"], "secondary")
            self.assertEqual(source["document_type"], "secondary_summary")
            self.assertEqual(source["content_sha256"], "a" * 64)
            raw_payload = json.loads(raw["raw_json"])
            self.assertEqual(raw_payload["source_excerpt"], _observation().source_excerpt)
            self.assertEqual(
                raw_payload["project_identity_basis"],
                _observation().project_identity_basis,
            )
            self.assertEqual(raw["trace_id"], trace_id)
            self.assertEqual(raw["importer_version"], "secondary-project-observation-v1")
            self.assertEqual(audit["trace_id"], trace_id)
            self.assertEqual(application.catalog.doctor()["status"], "ok")


def _observation() -> SecondaryProjectObservationInput:
    return SecondaryProjectObservationInput(
        school="中国科学技术大学",
        college="计算机科学与技术学院",
        program_code="085404",
        program_name="计算机技术",
        admission_year=2025,
        source_title="灰灰考研院校数据汇总",
        source_url="https://example.com/huihui/ustc-2025",
        source_institution="灰灰考研",
        source_content_sha256="a" * 64,
        applicable_year=2025,
        published_date=date(2025, 4, 1),
        retrieved_date=date(2026, 8, 3),
        source_excerpt="计算机技术：101、204、302、408。",
        project_identity_basis="页面同时列出学校、学院、专业代码和专业名称。",
        politics_code="101",
        english_code="204",
        math_code="302",
        professional_code="408",
        study_mode="全日制",
    )


if __name__ == "__main__":
    unittest.main()
