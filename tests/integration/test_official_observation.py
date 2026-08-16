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

from tests.support import REAL_ARCHIVE, build_test_application

from chose_school.domain.enums import EvidenceDocumentType, Strict22408Status
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import OfficialProjectObservationInput


class OfficialObservationTest(unittest.TestCase):
    def test_official_observation_is_atomic_append_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            database_path = application.database.database_path
            with closing(sqlite3.connect(database_path)) as connection:
                legacy = connection.execute(
                    """
                    SELECT o.id, o.raw_row_id, r.raw_json
                    FROM project_year_observations o
                    JOIN projects p ON p.id = o.project_id
                    JOIN schools s ON s.id = p.school_id
                    JOIN raw_catalog_rows r ON r.id = o.raw_row_id
                    WHERE s.display_name = '西北农林科技大学'
                      AND p.program_code = '085400'
                      AND o.admission_year = 2026
                    """
                ).fetchone()
                before_counts = connection.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM raw_catalog_rows),
                        (SELECT COUNT(*) FROM project_year_observations)
                    """
                ).fetchone()

            trace_id = str(uuid.uuid4())
            result = application.official_observations.add_observation(
                _nwafu_observation(),
                trace_id,
            )
            self.assertTrue(result.created)
            self.assertEqual(result.strict_status, Strict22408Status.OFFICIAL_CONFIRMED)

            repeated = application.official_observations.add_observation(
                _nwafu_observation(),
                str(uuid.uuid4()),
            )
            self.assertFalse(repeated.created)
            self.assertEqual(repeated.observation_id, result.observation_id)
            self.assertEqual(repeated.verification_id, result.verification_id)

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                new_observation = connection.execute(
                    "SELECT * FROM v_catalog WHERE observation_id = ?",
                    (result.observation_id,),
                ).fetchone()
                stored_counts = connection.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM raw_catalog_rows),
                        (SELECT COUNT(*) FROM project_year_observations)
                    """
                ).fetchone()
                legacy_after = connection.execute(
                    """
                    SELECT o.raw_row_id, r.raw_json
                    FROM project_year_observations o
                    JOIN raw_catalog_rows r ON r.id = o.raw_row_id
                    WHERE o.id = ?
                    """,
                    (legacy[0],),
                ).fetchone()
                numeric_values = connection.execute(
                    """
                    SELECT total_plan, recommendation_actual, special_plan,
                           effective_general_exam_quota, retest_cutoff,
                           retest_count, general_exam_admit_count,
                           admit_initial_min, admit_initial_median,
                           admit_initial_mean
                    FROM project_year_observations WHERE id = ?
                    """,
                    (result.observation_id,),
                ).fetchone()
                lineage = connection.execute(
                    """
                    SELECT b.trace_id, b.importer_version, sf.content_sha256,
                           r.id AS raw_row_id, r.raw_json, r.source_row_number
                    FROM project_year_observations o
                    JOIN raw_catalog_rows r ON r.id = o.raw_row_id
                    JOIN source_files sf ON sf.id = r.source_file_id
                    JOIN import_batches b ON b.id = sf.batch_id
                    WHERE o.id = ?
                    """,
                    (result.observation_id,),
                ).fetchone()
                source = connection.execute(
                    """
                    SELECT evidence_grade, document_type, content_sha256,
                           applicable_year, url
                    FROM evidence_sources es
                    JOIN observation_sources os ON os.source_id = es.id
                    WHERE os.observation_id = ?
                    """,
                    (result.observation_id,),
                ).fetchone()
                audit = connection.execute(
                    """
                    SELECT trace_id, entity_id, payload_json
                    FROM audit_events
                    WHERE event_type = 'official_project_observation_added'
                      AND entity_id = ?
                    """,
                    (str(result.observation_id),),
                ).fetchone()

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE raw_catalog_rows SET raw_json = '{}' WHERE id = ?",
                        (lineage["raw_row_id"],),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE project_year_observations SET notes = NULL WHERE id = ?",
                        (result.observation_id,),
                    )

            self.assertEqual(new_observation["school"], "西北农林科技大学")
            self.assertEqual(new_observation["college"], "信息工程学院")
            self.assertEqual(new_observation["program_code"], "085404")
            self.assertEqual(new_observation["program_name"], "计算机技术")
            self.assertEqual(new_observation["strict_22408_status"], "official_confirmed")
            self.assertEqual(stored_counts[0], before_counts[0] + 1)
            self.assertEqual(stored_counts[1], before_counts[1] + 1)
            self.assertEqual(tuple(legacy_after), (legacy[1], legacy[2]))
            self.assertTrue(all(value is None for value in numeric_values))
            self.assertEqual(lineage["trace_id"], trace_id)
            self.assertEqual(
                lineage["importer_version"],
                "official-project-observation-v1",
            )
            self.assertEqual(lineage["content_sha256"], "7" * 64)
            self.assertEqual(lineage["source_row_number"], 2)
            self.assertEqual(json.loads(lineage["raw_json"])["program_code"], "085404")
            self.assertEqual(source["evidence_grade"], "official")
            self.assertEqual(source["document_type"], "official_catalog")
            self.assertEqual(source["content_sha256"], "7" * 64)
            self.assertEqual(source["applicable_year"], 2026)
            self.assertEqual(source["url"], "https://example.edu/2026-catalog.xls")
            self.assertEqual(audit["trace_id"], trace_id)
            self.assertEqual(audit["entity_id"], str(result.observation_id))
            self.assertEqual(
                json.loads(audit["payload_json"])["verification_id"],
                result.verification_id,
            )
            self.assertEqual(application.catalog.doctor()["status"], "ok")

    def test_official_observation_rejects_non_catalog_and_year_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, _ = build_test_application(Path(temporary))
            with self.assertRaises(ValidationError) as document_error:
                application.official_observations.add_observation(
                    replace(
                        _nwafu_observation(),
                        source_document_type=EvidenceDocumentType.OFFICIAL_NOTICE,
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(document_error.exception.error_code, "CATALOG_REQUIRED")

            with self.assertRaises(ValidationError) as year_error:
                application.official_observations.add_observation(
                    replace(_nwafu_observation(), applicable_year=2027),
                    str(uuid.uuid4()),
                )
            self.assertEqual(year_error.exception.error_code, "EVIDENCE_YEAR_MISMATCH")
            self.assertEqual(application.catalog.get_summary()["counts"]["observations"], 0)


def _nwafu_observation() -> OfficialProjectObservationInput:
    return OfficialProjectObservationInput(
        school="西北农林科技大学",
        college="信息工程学院",
        program_code="085404",
        program_name="计算机技术",
        admission_year=2026,
        politics_code="101",
        english_code="204",
        math_code="302",
        professional_code="408",
        source_title="2026年硕士研究生招生专业目录",
        source_url="https://example.edu/2026-catalog.xls",
        source_institution="西北农林科技大学研究生院",
        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
        source_content_sha256="7" * 64,
        applicable_year=2026,
        published_date=date(2025, 10, 1),
        retrieved_date=date(2026, 8, 1),
        campus="杨凌校区",
        training_location="陕西杨凌",
        study_mode="全日制",
        training_type_raw="统考",
        admission_type="统考",
        degree_type="专业学位",
        note="测试用正式目录项目行",
    )


if __name__ == "__main__":
    unittest.main()
