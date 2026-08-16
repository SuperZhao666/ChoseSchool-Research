from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path

from tests.support import REAL_ARCHIVE, REPOSITORY_ROOT

from chose_school.bootstrap import build_application
from chose_school.infrastructure.config import load_settings


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "apply_reproducible_score_statistics_20260813.py"


class ReproducibleScoreStatisticsImportTest(unittest.TestCase):
    def test_script_is_pii_free_and_byte_stable_on_replay(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary_directory:
            database_path = Path(temporary_directory) / "statistics.sqlite3"
            settings = replace(
                load_settings(repository_root=REPOSITORY_ROOT),
                database_path=database_path,
                log_path=Path(temporary_directory) / "test.jsonl",
            )
            application = build_application(settings)
            application.database.initialize_database()
            application.catalog_import.import_archive(
                REAL_ARCHIVE,
                "statistics-import-fixture-batch",
                "12345678-1234-1234-1234-123456789abc",
            )
            self._seed_contract_rows(database_path)

            dry_run_before = self._run(database_path)
            self.assertEqual(dry_run_before["mode"], "read_only_preflight")
            self.assertFalse(dry_run_before["contains_person_level_data"])

            first = self._run(database_path, apply=True)
            self.assertEqual(first["family_count"], 8)
            self.assertEqual(first["claim_count"], 37)
            self.assertEqual(first["resolutions_added"], 37)
            self.assertFalse(first["contains_person_level_data"])

            first_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
            second = self._run(database_path, apply=True)
            second_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
            self.assertEqual(second["claim_count"], 37)
            self.assertEqual(second["resolutions_added"], 0)
            self.assertEqual(second["resolutions_reused"], 37)
            self.assertEqual(first_hash, second_hash)

            with closing(sqlite3.connect(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                issues = connection.execute(
                    """
                    SELECT issue_code, observation_id, statistic_family
                    FROM v_statistical_fact_quality_issues
                    ORDER BY issue_code, observation_id
                    """
                ).fetchall()
                self.assertEqual(
                    [tuple(row) for row in issues],
                    [],
                    [tuple(row) for row in issues],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM fact_claims
                        WHERE calculation_input_sha256 IS NOT NULL
                        """
                    ).fetchone()[0],
                    37,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM audit_events
                        WHERE event_type='fact_claim_added'
                          AND json_extract(payload_json, '$.calculation.input_sha256')
                              IS NOT NULL
                        """
                    ).fetchone()[0],
                    37,
                )

    def _run(self, database_path: Path, apply: bool = False) -> dict[str, object]:
        command = [
            sys.executable,
            str(SCRIPT),
            "--database",
            str(database_path),
            "--trace-id",
            "12345678-1234-1234-1234-123456789abc",
        ]
        if apply:
            command.append("--apply")
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            self.fail(
                f"statistics script failed: stdout={completed.stdout!r} "
                f"stderr={completed.stderr!r}"
            )
        return json.loads(completed.stdout)

    @staticmethod
    def _seed_contract_rows(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("DROP TRIGGER protect_evidence_sources_material_update")
            existing_observations = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM project_year_observations WHERE id IN (109,112,163,164,165)"
                )
            }
            if existing_observations != {109, 112, 163, 164, 165}:
                raise AssertionError("fixture archive observation ids changed")
            source_contracts = (
                (
                    1455,
                    "ncu",
                    "南昌大学2026年统招硕士研究生拟录取名单公示",
                    "南昌大学研究生院",
                    "https://yjsy.ncu.edu.cn/__local/1/40/DD/D4363BDFFF0E263221936E949A8_19E1FF08_ECD9D.pdf",
                    "48b23926da536aaa3811b0729a7e45dbb40fed08517f26cffba05efa04d1281b",
                    "admission_list",
                ),
                (
                    675,
                    "lnu-final",
                    "辽宁大学2026年硕士研究生一志愿拟录取名单",
                    "辽宁大学研究生院",
                    "https://grs.lnu.edu.cn/2026ssyzymd.pdf",
                    "a923c330057d4478aae158aae27cf190e07ae7232988e46d9567909364918957",
                    "admission_list",
                ),
                (
                    669,
                    "lnu-roster",
                    "辽宁大学信息学部2026年进入复试考生名单",
                    "辽宁大学信息学部",
                    "https://sist.lnu.edu.cn/__local/C/CA/29/42AFA6A97023C2DDB88C21E7EDC_B1577418_48A7.xlsx",
                    "701d6ae9b87bce1023a96b1b7db35be280371647bcfea18b956783a6af7752ba",
                    "retest_list",
                ),
            )
            for source_id, identity, title, institution, url, sha256, document_type in source_contracts:
                connection.execute(
                    """
                    INSERT INTO evidence_sources(
                        id, identity_key, title, institution, url, evidence_grade,
                        retrieved_date, created_at, updated_at, document_type,
                        content_sha256, applicable_year
                    ) VALUES (?, ?, ?, ?, ?, 'official', '2026-08-13',
                              '2026-08-13T00:00:00+00:00',
                              '2026-08-13T00:00:00+00:00', ?, ?, 2026)
                    """,
                    (
                        source_id,
                        hashlib.sha256(identity.encode()).hexdigest(),
                        title,
                        institution,
                        url,
                        document_type,
                        sha256,
                    ),
                )
            connection.executescript(
                """
                CREATE TRIGGER protect_evidence_sources_material_update
                BEFORE UPDATE OF
                    identity_key, title, institution, url, evidence_grade,
                    published_date, retrieved_date, source_note,
                    document_type, content_sha256, applicable_year
                ON evidence_sources
                BEGIN
                    SELECT RAISE(ABORT, 'evidence source material fields are append-only');
                END;
                """
            )

            count_definition_ids = {
                row[0]: row[1]
                for row in connection.execute(
                    """
                    SELECT fact_key, id FROM fact_definitions
                    WHERE fact_key IN (
                        'admission.final_list_fulltime_blank_remark_count',
                        'admission.final_list_first_choice_fulltime_non_directed_count',
                        'retest.roster_count'
                    )
                    """
                )
            }
            counts = (
                (109, "admission.final_list_fulltime_blank_remark_count", 25, 1455,
                 "006数学与计算机学院085405软件工程、全日制、最终拟录取名单备注为空的考生行；覆盖该学院本专业全部目录方向合计"),
                (112, "admission.final_list_fulltime_blank_remark_count", 37, 1455,
                 "017软件学院085405软件工程、全日制、最终拟录取名单备注为空的考生行；覆盖该学院本专业全部目录方向合计"),
                (163, "admission.final_list_first_choice_fulltime_non_directed_count", 22, 675,
                 "信息学部018-085405软件工程一志愿、全日制、非定向最终名单限定集合，名单未提供专项分类列，专项身份未拆"),
                (164, "admission.final_list_first_choice_fulltime_non_directed_count", 15, 675,
                 "信息学部018-085410人工智能一志愿、全日制、非定向最终名单限定集合，名单未提供专项分类列，专项身份未拆"),
                (165, "admission.final_list_first_choice_fulltime_non_directed_count", 15, 675,
                 "信息学部018-085412网络与信息安全一志愿、全日制、非定向最终名单限定集合，名单未提供专项分类列，专项身份未拆"),
                (163, "retest.roster_count", 27, 669,
                 "信息学部018-085405软件工程一志愿复试名单列示考生，名单备注为空，专项身份未拆"),
                (164, "retest.roster_count", 18, 669,
                 "信息学部018-085410人工智能一志愿复试名单列示考生，名单备注为空，专项身份未拆"),
                (165, "retest.roster_count", 18, 669,
                 "信息学部018-085412网络与信息安全一志愿复试名单列示考生，名单备注为空，专项身份未拆"),
            )
            for index, (observation_id, fact_key, value, source_id, population) in enumerate(counts, 1):
                cursor = connection.execute(
                    """
                    INSERT INTO fact_claims(
                        claim_fingerprint, observation_id, fact_definition_id,
                        population_scope, statistic_scope, value_integer,
                        source_id, evidence_grade, trace_id, created_at
                    ) VALUES (?, ?, ?, ?, 'count contract', ?, ?, 'official',
                              '12345678-1234-1234-1234-123456789abc',
                              '2026-08-13T00:00:00+00:00')
                    """,
                    (
                        hashlib.sha256(f"count-{index}".encode()).hexdigest(),
                        observation_id,
                        count_definition_ids[fact_key],
                        population,
                        value,
                        source_id,
                    ),
                )
                claim_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    INSERT INTO fact_resolutions(
                        observation_id, fact_definition_id, population_scope,
                        statistic_scope, resolution_action, selected_claim_id,
                        reason, trace_id, created_at
                    ) VALUES (?, ?, ?, 'count contract', 'accept', ?, 'seed',
                              '12345678-1234-1234-1234-123456789abc',
                              '2026-08-13T00:00:00+00:00')
                    """,
                    (
                        observation_id,
                        count_definition_ids[fact_key],
                        population,
                        claim_id,
                    ),
                )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
