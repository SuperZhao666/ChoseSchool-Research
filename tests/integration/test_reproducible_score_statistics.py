from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tests.support import REPOSITORY_ROOT

from chose_school.bootstrap import build_application
from chose_school.domain.enums import EvidenceDocumentType, EvidenceGrade
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import FactClaimInput, OfficialProjectObservationInput
from chose_school.infrastructure.config import load_settings
from chose_school.infrastructure.database import Database


POPULATION = "目标项目普通统考拟录取者"
INPUT_HASH = "a" * 64


class ReproducibleScoreStatisticsTest(unittest.TestCase):
    def test_migration_preserves_legacy_row_and_v2_fingerprint_can_append_same_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "schema-025.sqlite3"
            all_migrations = Database._migration_paths()
            through_25 = [
                path
                for path in all_migrations
                if int(path.name.split("_", 1)[0]) <= 25
            ]
            with patch.object(Database, "_migration_paths", return_value=through_25):
                self.assertEqual(Database(database_path).migrate(), list(range(1, 26)))

            application = self._application(database_path, root / "test.jsonl")
            observation_id = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            ).observation_id

            with closing(sqlite3.connect(database_path)) as connection:
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
                legacy_fingerprint = hashlib.sha256(
                    json.dumps(
                        (
                            observation_id,
                            "score.initial.median",
                            POPULATION,
                            "初试总分中位数",
                            "decimal",
                            None,
                            350.0,
                            None,
                            None,
                            source_id,
                        ),
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    INSERT INTO fact_claims(
                        claim_fingerprint, observation_id, fact_definition_id,
                        population_scope, statistic_scope, value_decimal,
                        source_id, evidence_grade, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'official', ?, ?)
                    """,
                    (
                        legacy_fingerprint,
                        observation_id,
                        definition_id,
                        POPULATION,
                        "初试总分中位数",
                        350.0,
                        source_id,
                        "legacy-score-trace",
                        "2026-08-13T00:00:00+00:00",
                    ),
                )
                legacy_claim_id = int(
                    connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                )
                connection.commit()

            through_26 = [
                path
                for path in all_migrations
                if int(path.name.split("_", 1)[0]) <= 26
            ]
            with patch.object(Database, "_migration_paths", return_value=through_26):
                self.assertEqual(Database(database_path).migrate(), [26])
                self.assertEqual(Database(database_path).migrate(), [])

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                legacy = connection.execute(
                    """
                    SELECT sample_size, calculation_method_key,
                           calculation_input_sha256
                    FROM fact_claims WHERE id = ?
                    """,
                    (legacy_claim_id,),
                ).fetchone()
                self.assertIsNotNone(legacy)
                self.assertTrue(all(value is None for value in tuple(legacy)))
                view_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(v_fact_claims)")
                }
                self.assertTrue(
                    {
                        "sample_size",
                        "calculation_method_key",
                        "calculation_input_sha256",
                    }.issubset(view_columns)
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fact_definitions WHERE fact_key LIKE '%.q25' OR fact_key LIKE '%.q75'"
                    ).fetchone()[0],
                    6,
                )
                q25_definition_id = int(
                    connection.execute(
                        "SELECT id FROM fact_definitions WHERE fact_key = 'score.initial.q25'"
                    ).fetchone()[0]
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO fact_claims(
                            claim_fingerprint, observation_id, fact_definition_id,
                            population_scope, statistic_scope, value_decimal,
                            source_id, evidence_grade, trace_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, 330, ?, 'official', ?, ?)
                        """,
                        (
                            "missing-statistical-metadata-026",
                            observation_id,
                            q25_definition_id,
                            POPULATION,
                            "25%分位数",
                            source_id,
                            "missing-statistical-metadata-trace",
                            "2026-08-13T00:00:01+00:00",
                        ),
                    )
                total_definition_id = int(
                    connection.execute(
                        "SELECT id FROM fact_definitions WHERE fact_key = 'quota.total_plan'"
                    ).fetchone()[0]
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO fact_claims(
                            claim_fingerprint, observation_id, fact_definition_id,
                            population_scope, statistic_scope, value_integer,
                            source_id, evidence_grade, trace_id, created_at,
                            sample_size, calculation_method_key,
                            calculation_input_sha256
                        ) VALUES (?, ?, ?, ?, ?, 5, ?, 'official', ?, ?,
                                  5, 'sample_min_v1', ?)
                        """,
                        (
                            "metadata-on-non-statistical-fact-026",
                            observation_id,
                            total_definition_id,
                            POPULATION,
                            "总计划",
                            source_id,
                            "metadata-on-non-statistical-fact-trace",
                            "2026-08-13T00:00:02+00:00",
                            INPUT_HASH,
                        ),
                    )

            application = self._application(database_path, root / "test.jsonl")
            structured = self._score_claim(
                observation_id,
                "score.initial.median",
                "350",
                "初试总分中位数",
            )
            structured_id = application.facts.add_claim(
                structured,
                str(uuid.uuid4()),
            )
            self.assertNotEqual(structured_id, legacy_claim_id)
            self.assertEqual(
                application.facts.add_claim(structured, str(uuid.uuid4())),
                structured_id,
            )
            different_input_id = application.facts.add_claim(
                replace(structured, calculation_input_sha256="b" * 64),
                str(uuid.uuid4()),
            )
            self.assertNotEqual(different_input_id, structured_id)

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    "SELECT * FROM v_fact_claims WHERE claim_id = ?",
                    (structured_id,),
                ).fetchone()
                self.assertEqual(row["sample_size"], 5)
                self.assertEqual(
                    row["calculation_method_key"],
                    "percentile_inc_type7_v1",
                )
                self.assertEqual(row["calculation_input_sha256"], INPUT_HASH)
                audit = json.loads(
                    connection.execute(
                        """
                        SELECT payload_json FROM audit_events
                        WHERE event_type = 'fact_claim_added'
                          AND entity_type = 'fact_claim'
                          AND entity_id = ?
                        """,
                        (str(structured_id),),
                    ).fetchone()[0]
                )
                self.assertEqual(
                    audit["calculation"],
                    {
                        "input_sha256": INPUT_HASH,
                        "method_key": "percentile_inc_type7_v1",
                        "sample_size": 5,
                    },
                )

    def test_doctor_uses_population_family_and_input_identity_not_prose_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "statistics.sqlite3"
            through_26 = [
                path
                for path in Database._migration_paths()
                if int(path.name.split("_", 1)[0]) <= 26
            ]
            with patch.object(Database, "_migration_paths", return_value=through_26):
                Database(database_path).migrate()
            application = self._application(database_path, root / "test.jsonl")
            observation_id = application.official_observations.add_observation(
                _official_observation(),
                str(uuid.uuid4()),
            ).observation_id

            count_id = application.facts.add_claim(
                self._count_claim(observation_id),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                count_id,
                "官方最终名单逐行筛选得到该受控人群五行",
                str(uuid.uuid4()),
            )
            score_ids = []
            for fact_key, value, prose_scope in (
                ("score.initial.q25", "330", "PERCENTILE.INC 25%分位数"),
                ("score.initial.median", "350", "PERCENTILE.INC 50%分位数"),
                ("score.initial.q75", "370", "PERCENTILE.INC 75%分位数"),
            ):
                claim_id = application.facts.add_claim(
                    self._score_claim(
                        observation_id,
                        fact_key,
                        value,
                        prose_scope,
                    ),
                    str(uuid.uuid4()),
                )
                application.facts.resolve_claim(
                    claim_id,
                    "同一匿名输入集按冻结方法复算",
                    str(uuid.uuid4()),
                )
                score_ids.append(claim_id)

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")
            for metric in (
                "statistical_fact_metadata_invalid",
                "statistical_fact_count_missing",
                "statistical_fact_count_ambiguous",
                "statistical_fact_sample_size_count_mismatch",
                "statistical_fact_input_inconsistent",
                "statistical_fact_quantile_triplet_incomplete",
                "statistical_fact_quantile_order_invalid",
            ):
                self.assertEqual(doctor[metric], 0, metric)

            duplicate_count = application.facts.add_claim(
                replace(
                    self._count_claim(observation_id),
                    statistic_scope="另一份人数说明形成第二个当前身份",
                ),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                duplicate_count,
                "故障注入：同受控人群出现第二条当前人数",
                str(uuid.uuid4()),
            )
            ambiguous = application.catalog.doctor()
            self.assertEqual(ambiguous["status"], "error")
            self.assertEqual(ambiguous["statistical_fact_count_ambiguous"], 1)
            application.facts.unresolve_claim(
                duplicate_count,
                "撤回故障注入人数身份",
                str(uuid.uuid4()),
            )
            self.assertEqual(application.catalog.doctor()["status"], "ok")

            mismatched_count = application.facts.add_claim(
                replace(self._count_claim(observation_id), raw_value="4"),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                mismatched_count,
                "故障注入：人数少于结构化统计样本数",
                str(uuid.uuid4()),
            )
            mismatched = application.catalog.doctor()
            self.assertEqual(mismatched["status"], "error")
            self.assertEqual(
                mismatched["statistical_fact_sample_size_count_mismatch"],
                1,
            )
            application.facts.resolve_claim(
                count_id,
                "恢复正确的当前人数事实",
                str(uuid.uuid4()),
            )
            self.assertEqual(application.catalog.doctor()["status"], "ok")

            application.facts.unresolve_claim(
                score_ids[2],
                "故障注入：撤回q75形成不完整分位数组",
                str(uuid.uuid4()),
            )
            incomplete = application.catalog.doctor()
            self.assertEqual(incomplete["status"], "error")
            self.assertEqual(
                incomplete["statistical_fact_quantile_triplet_incomplete"],
                1,
            )
            application.facts.resolve_claim(
                score_ids[2],
                "恢复同一输入集q75",
                str(uuid.uuid4()),
            )
            self.assertEqual(application.catalog.doctor()["status"], "ok")

            inconsistent_mean = application.facts.add_claim(
                replace(
                    self._score_claim(
                        observation_id,
                        "score.initial.mean",
                        "352",
                        "初试总分算术平均数",
                    ),
                    calculation_method_key="arithmetic_mean_v1",
                    calculation_input_sha256="b" * 64,
                ),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                inconsistent_mean,
                "故障注入：均值使用另一输入集",
                str(uuid.uuid4()),
            )
            inconsistent = application.catalog.doctor()
            self.assertEqual(inconsistent["status"], "error")
            self.assertEqual(inconsistent["statistical_fact_input_inconsistent"], 1)
            application.facts.unresolve_claim(
                inconsistent_mean,
                "撤回不一致输入集故障注入",
                str(uuid.uuid4()),
            )
            self.assertEqual(application.catalog.doctor()["status"], "ok")

            invalid_q75 = application.facts.add_claim(
                self._score_claim(
                    observation_id,
                    "score.initial.q75",
                    "340",
                    "PERCENTILE.INC 75%分位数",
                ),
                str(uuid.uuid4()),
            )
            application.facts.resolve_claim(
                invalid_q75,
                "故障注入：q75低于q50",
                str(uuid.uuid4()),
            )
            corrupted = application.catalog.doctor()
            self.assertEqual(corrupted["status"], "error")
            self.assertEqual(corrupted["statistical_fact_quantile_order_invalid"], 1)

            with self.assertRaises(ValidationError) as missing_metadata:
                application.facts.add_claim(
                    replace(
                        self._score_claim(
                            observation_id,
                            "score.initial.q25",
                            "330",
                            "另一统计说明",
                        ),
                        sample_size=None,
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                missing_metadata.exception.error_code,
                "STATISTICAL_SAMPLE_SIZE_REQUIRED",
            )
            with self.assertRaises(ValidationError) as wrong_method:
                application.facts.add_claim(
                    replace(
                        self._score_claim(
                            observation_id,
                            "score.initial.q25",
                            "330",
                            "另一统计说明",
                        ),
                        calculation_method_key="arithmetic_mean_v1",
                    ),
                    str(uuid.uuid4()),
                )
            self.assertEqual(
                wrong_method.exception.error_code,
                "STATISTICAL_METHOD_MISMATCH",
            )

    @staticmethod
    def _application(database_path: Path, log_path: Path):
        settings = replace(
            load_settings(repository_root=REPOSITORY_ROOT),
            database_path=database_path,
            log_path=log_path,
        )
        return build_application(settings)

    @staticmethod
    def _score_claim(
        observation_id: int,
        fact_key: str,
        value: str,
        statistic_scope: str,
    ) -> FactClaimInput:
        return FactClaimInput(
            observation_id=observation_id,
            fact_key=fact_key,
            raw_value=value,
            evidence_grade=EvidenceGrade.OFFICIAL,
            source_title="2026年硕士研究生招生专业目录",
            source_url="https://example.edu/2026-catalog.xls",
            source_institution="西北农林科技大学研究生院",
            source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
            source_content_sha256="7" * 64,
            applicable_year=2026,
            published_date=date(2025, 10, 1),
            retrieved_date=date(2026, 8, 13),
            population_scope=POPULATION,
            statistic_scope=statistic_scope,
            sample_size=5,
            calculation_method_key="percentile_inc_type7_v1",
            calculation_input_sha256=INPUT_HASH,
        )

    @staticmethod
    def _count_claim(observation_id: int) -> FactClaimInput:
        return FactClaimInput(
            observation_id=observation_id,
            fact_key="admission.general_count",
            raw_value="5",
            evidence_grade=EvidenceGrade.OFFICIAL,
            source_title="2026年硕士研究生招生专业目录",
            source_url="https://example.edu/2026-catalog.xls",
            source_institution="西北农林科技大学研究生院",
            source_document_type=EvidenceDocumentType.OFFICIAL_CATALOG,
            source_content_sha256="7" * 64,
            applicable_year=2026,
            published_date=date(2025, 10, 1),
            retrieved_date=date(2026, 8, 13),
            population_scope=POPULATION,
            statistic_scope="最终名单逐行筛选人数",
        )


def _official_observation() -> OfficialProjectObservationInput:
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
        retrieved_date=date(2026, 8, 13),
        study_mode="全日制",
    )


if __name__ == "__main__":
    unittest.main()
