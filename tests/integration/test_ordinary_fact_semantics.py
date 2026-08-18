from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

from tests.support import build_test_application

from chose_school.domain.enums import EvidenceDocumentType, EvidenceGrade
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import FactClaimInput, OfficialProjectObservationInput


class OrdinaryFactSemanticsTest(unittest.TestCase):
    def test_migration_registers_proxy_facts_and_safe_views(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            with closing(sqlite3.connect(settings.database_path)) as connection:
                definitions = {
                    row[0]
                    for row in connection.execute(
                        "SELECT fact_key FROM fact_definitions WHERE fact_key LIKE 'admission.suggested_list_%'"
                    )
                }
                self.assertEqual(
                    definitions,
                    {
                        "admission.suggested_list_total_count",
                        "admission.suggested_list_blank_remark_count",
                        "admission.suggested_list_special_count",
                    },
                )
                views = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'v_current_%fact_evidence'"
                    )
                }
                self.assertIn("v_current_accepted_fact_evidence", views)
                self.assertIn("v_current_unresolved_fact_evidence", views)
            self.assertEqual(application.catalog.doctor()["status"], "ok")

    def test_service_and_database_reject_nonofficial_ordinary_machine_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application, settings = build_test_application(Path(temporary))
            observation_id = application.official_observations.add_observation(
                _official_observation(), str(uuid.uuid4())
            ).observation_id
            claim = FactClaimInput(
                observation_id=observation_id,
                fact_key="score.initial.median",
                raw_value="350",
                evidence_grade=EvidenceGrade.OFFICIAL_MIXED,
                source_title="测试官方混合来源",
                source_url="https://example.edu.cn/test.pdf",
                source_institution="测试大学",
                source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                source_content_sha256="a" * 64,
                applicable_year=2026,
                published_date=None,
                retrieved_date=date(2026, 8, 18),
                population_scope="mixed_population",
                statistic_scope="median",
            )
            with self.assertRaises(ValidationError) as raised:
                application.facts.add_claim(claim, str(uuid.uuid4()))
            self.assertEqual(
                raised.exception.error_code,
                "ORDINARY_MACHINE_FACT_REQUIRES_OFFICIAL_EVIDENCE",
            )

            with closing(sqlite3.connect(settings.database_path)) as connection:
                connection.row_factory = sqlite3.Row
                source_id = int(
                    connection.execute(
                        "SELECT id FROM evidence_sources WHERE url = ?",
                        (_official_observation().source_url,),
                    ).fetchone()[0]
                )
                definition_id = int(
                    connection.execute(
                        "SELECT id FROM fact_definitions WHERE fact_key = 'score.initial.median'"
                    ).fetchone()[0]
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO fact_claims(
                            claim_fingerprint, observation_id, fact_definition_id,
                            population_scope, statistic_scope, value_decimal,
                            source_id, evidence_grade, trace_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "b" * 64,
                            observation_id,
                            definition_id,
                            "mixed_population",
                            "median",
                            350.0,
                            source_id,
                            "official_mixed",
                            str(uuid.uuid4()),
                            "2026-08-18T00:00:00+00:00",
                        ),
                    )


def _official_observation() -> OfficialProjectObservationInput:
    return OfficialProjectObservationInput(
        school="测试大学",
        college="软件学院",
        program_code="085405",
        program_name="软件工程",
        admission_year=2026,
        politics_code="101",
        english_code="204",
        math_code="302",
        professional_code="408",
        source_title="测试大学2026正式招生目录",
        source_url="https://example.edu.cn/test.pdf",
        source_institution="测试大学",
        source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
        source_content_sha256="c" * 64,
        applicable_year=2026,
        retrieved_date=date(2026, 8, 18),
        published_date=date(2025, 9, 1),
    )


if __name__ == "__main__":
    unittest.main()
