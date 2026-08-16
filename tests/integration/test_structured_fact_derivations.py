from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests.support import REAL_ARCHIVE, REPOSITORY_ROOT

from chose_school.bootstrap import build_application
from chose_school.infrastructure.config import load_settings
from chose_school.infrastructure.database import Database


class StructuredFactDerivationMigrationTest(unittest.TestCase):
    def test_migration_preserves_old_claims_and_enforces_the_single_formula(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "schema-024.sqlite3"
            migrations_through_24 = [
                path
                for path in Database._migration_paths()
                if int(path.name.split("_", 1)[0]) <= 24
            ]
            with patch.object(
                Database,
                "_migration_paths",
                return_value=migrations_through_24,
            ):
                database = Database(database_path)
                self.assertEqual(database.migrate(), list(range(1, 25)))
                settings = load_settings(repository_root=REPOSITORY_ROOT)
                application = build_application(
                    replace(
                        settings,
                        database_path=database_path,
                        log_path=Path(temporary) / "test.jsonl",
                    )
                )
                application.catalog_import.import_archive(
                    REAL_ARCHIVE,
                    "migration-025-fixture-trace",
                    "migration-025-fixture-batch",
                )

            with closing(sqlite3.connect(database_path)) as connection:
                observation_id = int(
                    connection.execute(
                        "SELECT id FROM project_year_observations ORDER BY id LIMIT 1"
                    ).fetchone()[0]
                )
                source_id = int(
                    connection.execute(
                        "SELECT id FROM evidence_sources ORDER BY id LIMIT 1"
                    ).fetchone()[0]
                )
                total_plan_definition_id = int(
                    connection.execute(
                        "SELECT id FROM fact_definitions WHERE fact_key = 'quota.total_plan'"
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO fact_claims(
                        claim_fingerprint, observation_id, fact_definition_id,
                        population_scope, statistic_scope, value_integer,
                        source_id, evidence_grade, note, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "legacy-fact-before-025",
                        observation_id,
                        total_plan_definition_id,
                        "历史项目口径",
                        "历史总计划",
                        25,
                        source_id,
                        "secondary",
                        "迁移前事实夹具",
                        "migration-025-legacy-trace",
                        "2026-08-13T00:00:00+00:00",
                    ),
                )
                legacy_claim_id = int(
                    connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                )
                connection.commit()

            database = Database(database_path)
            self.assertEqual(database.migrate(), [25, 26, 27, 28])
            self.assertEqual(database.migrate(), [])

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                derivation_columns = (
                    "derivation_operator",
                    "derivation_left_fact_key",
                    "derivation_left_value_integer",
                    "derivation_right_fact_key",
                    "derivation_right_value_integer",
                )
                old_row = connection.execute(
                    f"SELECT {', '.join(derivation_columns)} FROM fact_claims WHERE id = ?",
                    (legacy_claim_id,),
                ).fetchone()
                self.assertIsNotNone(old_row)
                self.assertTrue(all(old_row[column] is None for column in derivation_columns))
                view_columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(v_fact_claims)")
                }
                self.assertTrue(set(derivation_columns).issubset(view_columns))

                derived_definition_id = int(
                    connection.execute(
                        """
                        SELECT id FROM fact_definitions
                        WHERE fact_key = 'quota.plan_minus_received_recommendation'
                        """
                    ).fetchone()[0]
                )
                self._insert_claim(
                    connection,
                    fingerprint="valid-derived-025",
                    observation_id=observation_id,
                    definition_id=derived_definition_id,
                    source_id=source_id,
                    value=22,
                    derivation=(
                        "subtract",
                        "quota.total_plan",
                        25,
                        "quota.recommendation_received",
                        3,
                    ),
                )
                connection.commit()

                invalid_cases = (
                    (
                        "missing-derived-field-025",
                        22,
                        (
                            "subtract",
                            "quota.total_plan",
                            25,
                            "quota.recommendation_received",
                            None,
                        ),
                    ),
                    (
                        "wrong-derived-result-025",
                        21,
                        (
                            "subtract",
                            "quota.total_plan",
                            25,
                            "quota.recommendation_received",
                            3,
                        ),
                    ),
                    (
                        "wrong-derived-operator-025",
                        22,
                        (
                            "add",
                            "quota.total_plan",
                            25,
                            "quota.recommendation_received",
                            3,
                        ),
                    ),
                    (
                        "wrong-derived-key-025",
                        22,
                        (
                            "subtract",
                            "quota.exam_catalog_plan",
                            25,
                            "quota.recommendation_received",
                            3,
                        ),
                    ),
                )
                for fingerprint, value, derivation in invalid_cases:
                    with self.subTest(fingerprint=fingerprint):
                        with self.assertRaises(sqlite3.IntegrityError):
                            self._insert_claim(
                                connection,
                                fingerprint=fingerprint,
                                observation_id=observation_id,
                                definition_id=derived_definition_id,
                                source_id=source_id,
                                value=value,
                                derivation=derivation,
                            )

                with self.assertRaises(sqlite3.IntegrityError):
                    self._insert_claim(
                        connection,
                        fingerprint="metadata-on-non-derived-025",
                        observation_id=observation_id,
                        definition_id=total_plan_definition_id,
                        source_id=source_id,
                        value=25,
                        derivation=(
                            "subtract",
                            "quota.total_plan",
                            25,
                            "quota.recommendation_received",
                            3,
                        ),
                    )

                definition = connection.execute(
                    """
                    SELECT description, preferred_source_type
                    FROM fact_definitions
                    WHERE fact_key = 'quota.recommendation_actual'
                    """
                ).fetchone()
                self.assertIn("最终推免拟录取公示名单", definition["description"])
                self.assertIn("不是最终报到", definition["description"])
                self.assertEqual(
                    definition["preferred_source_type"],
                    "最终推免拟录取公示名单逐行统计",
                )

    @staticmethod
    def _insert_claim(
        connection: sqlite3.Connection,
        *,
        fingerprint: str,
        observation_id: int,
        definition_id: int,
        source_id: int,
        value: int,
        derivation: tuple[str | None, str | None, int | None, str | None, int | None],
    ) -> None:
        connection.execute(
            """
            INSERT INTO fact_claims(
                claim_fingerprint, observation_id, fact_definition_id,
                population_scope, statistic_scope, value_integer,
                source_id, evidence_grade, note, trace_id, created_at,
                derivation_operator, derivation_left_fact_key,
                derivation_left_value_integer, derivation_right_fact_key,
                derivation_right_value_integer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint,
                observation_id,
                definition_id,
                "目标项目复试阶段计划（专项未拆分）",
                "同一文件中的透明算术余量",
                value,
                source_id,
                "official_mixed",
                "数据库约束测试",
                f"{fingerprint}-trace",
                "2026-08-13T00:00:00+00:00",
                *derivation,
            ),
        )


if __name__ == "__main__":
    unittest.main()
