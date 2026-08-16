from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.support import REAL_ARCHIVE, build_test_application

from chose_school.domain.enums import EvidenceDocumentType, EvidenceGrade
from chose_school.domain.models import FactClaimInput


class FactEvidenceSourceReplayIdempotencyTest(unittest.TestCase):
    def test_replayed_claim_does_not_touch_shared_source_or_database_bytes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            root = Path(temporary)
            application, settings = build_test_application(root)
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                "source-replay-fixture-trace",
                "source-replay-fixture-batch",
            )
            with sqlite3.connect(settings.database_path) as connection:
                observation_id = int(
                    connection.execute(
                        """
                        SELECT id
                        FROM project_year_observations
                        WHERE admission_year = 2026
                        ORDER BY id
                        LIMIT 1
                        """
                    ).fetchone()[0]
                )

            source_note = "官方目录原件；项目级筛选条件和数值只记录在事实主张中。"
            claim = FactClaimInput(
                observation_id=observation_id,
                fact_key="quota.total_plan",
                raw_value="1",
                evidence_grade=EvidenceGrade.OFFICIAL,
                source_title="幂等重放测试官方目录",
                source_url="https://example.edu/official-catalog.pdf",
                source_institution="测试大学研究生院",
                source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
                source_content_sha256="b" * 64,
                applicable_year=2026,
                published_date=date(2025, 10, 1),
                retrieved_date=date(2026, 8, 13),
                population_scope="测试项目全集",
                statistic_scope="正式目录列示总计划",
                note="085404测试项目目录行列示1人。",
                source_note=source_note,
            )

            first_claim_id = application.facts.add_claim(claim, "source-replay-first")
            self._checkpoint(settings.database_path)
            before = self._snapshot(settings.database_path)
            before_hash = self._file_hash(settings.database_path)

            second_claim_id = application.facts.add_claim(claim, "source-replay-second")
            self._checkpoint(settings.database_path)
            after = self._snapshot(settings.database_path)
            after_hash = self._file_hash(settings.database_path)

            self.assertEqual(second_claim_id, first_claim_id)
            self.assertEqual(after, before)
            self.assertEqual(after_hash, before_hash)
            self.assertEqual(after["source_note"], source_note)
            self.assertNotIn("085404", after["source_note"])
            self.assertEqual(after["source_created_at"], after["source_updated_at"])

    @staticmethod
    def _checkpoint(database_path: Path) -> None:
        connection = sqlite3.connect(database_path)
        try:
            self_result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        finally:
            connection.close()
        if self_result != (0, 0, 0):
            raise AssertionError(f"unexpected WAL checkpoint result: {self_result}")

    @staticmethod
    def _snapshot(database_path: Path) -> dict[str, object]:
        connection = sqlite3.connect(database_path)
        try:
            connection.row_factory = sqlite3.Row
            source = connection.execute(
                """
                SELECT source_note, created_at, updated_at
                FROM evidence_sources
                WHERE url = 'https://example.edu/official-catalog.pdf'
                """
            ).fetchone()
            counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in (
                    "evidence_sources",
                    "fact_claims",
                    "fact_resolutions",
                    "audit_events",
                )
            }
            sequences = tuple(
                connection.execute(
                    """
                    SELECT name, seq
                    FROM sqlite_sequence
                    WHERE name IN (
                        'evidence_sources', 'fact_claims',
                        'fact_resolutions', 'audit_events'
                    )
                    ORDER BY name
                    """
                ).fetchall()
            )
        finally:
            connection.close()
        return {
            "counts": counts,
            "sequences": tuple(tuple(row) for row in sequences),
            "source_note": str(source["source_note"]),
            "source_created_at": str(source["created_at"]),
            "source_updated_at": str(source["updated_at"]),
        }

    @staticmethod
    def _file_hash(database_path: Path) -> str:
        return hashlib.sha256(database_path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
