from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from tests.support import build_test_application


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "apply_cqu_three_year_history_20260814.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("cqu_history_import", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load CQU history import script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CquThreeYearHistoryImportTest(unittest.TestCase):
    def test_import_is_non_strict_reproducible_private_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            application, settings = build_test_application(Path(temporary))
            application.assessment.initialize_default_profile(str(uuid.uuid4()))
            script = _load_script()

            first = script._append(settings.database_path, str(uuid.uuid4()))
            first_hash = hashlib.sha256(settings.database_path.read_bytes()).hexdigest()
            second = script._append(settings.database_path, str(uuid.uuid4()))
            second_hash = hashlib.sha256(settings.database_path.read_bytes()).hexdigest()

            self.assertEqual(first["observations_created"], 2)
            self.assertEqual(first["claim_count"], 8)
            self.assertEqual(first["resolutions_added"], 8)
            self.assertEqual(second["observations_created"], 0)
            self.assertEqual(second["resolutions_added"], 0)
            self.assertEqual(first_hash, second_hash)

            with sqlite3.connect(settings.database_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    """
                    SELECT admission_year, strict_22408_status,
                           subject_professional_code, observation_id
                    FROM v_catalog
                    WHERE school='重庆大学'
                      AND college='计算机学院'
                      AND program_code='085404'
                      AND admission_year IN (2024, 2025)
                    ORDER BY admission_year
                    """
                ).fetchall()
                self.assertEqual(
                    [
                        (
                            row["admission_year"],
                            row["strict_22408_status"],
                            row["subject_professional_code"],
                        )
                        for row in rows
                    ],
                    [
                        (2024, "official_non_strict", "917"),
                        (2025, "official_non_strict", "961"),
                    ],
                )
                observation_2025 = int(rows[1]["observation_id"])
                statistic_rows = connection.execute(
                    """
                    SELECT fact_key, sample_size, calculation_method_key,
                           calculation_input_sha256, value_decimal
                    FROM v_current_structured_score_statistics
                    WHERE observation_id=?
                    ORDER BY fact_key
                    """,
                    (observation_2025,),
                ).fetchall()
                self.assertEqual(len(statistic_rows), 5)
                self.assertEqual({row["sample_size"] for row in statistic_rows}, {91})
                self.assertEqual(
                    {row["calculation_input_sha256"] for row in statistic_rows},
                    {script.SCORE_INPUT_SHA256},
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM v_statistical_fact_quality_issues "
                        "WHERE observation_id=?",
                        (observation_2025,),
                    ).fetchone()[0],
                    0,
                )
                serialized = " ".join(
                    str(value)
                    for row in connection.execute(
                        """
                        SELECT source_title, source_url, population_scope,
                               statistic_scope, claim_note
                        FROM v_current_resolved_fact_evidence
                        WHERE observation_id=?
                        """,
                        (observation_2025,),
                    )
                    for value in row
                    if value is not None
                )
                self.assertNotIn("10611", serialized)
                self.assertNotIn("证件号码", serialized)

            doctor = application.catalog.doctor()
            self.assertEqual(doctor["status"], "ok")


if __name__ == "__main__":
    unittest.main()
