from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.acceptance.test_cli_journey import _strict_observation_arguments
from tests.support import REPOSITORY_ROOT


class StatisticalFactCliTest(unittest.TestCase):
    def test_cli_persists_and_lists_reproducible_calculation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "statistical-cli.sqlite3"
            self._run_ok("--database", str(database), "--json", "init")
            observation = self._run_ok(
                "--database",
                str(database),
                "--json",
                *_strict_observation_arguments(),
            )
            observation_id = int(observation["observation_id"])
            arguments = self._fact_arguments(observation_id)
            first = self._run_ok(
                "--database",
                str(database),
                "--json",
                *arguments,
            )
            replay = self._run_ok(
                "--database",
                str(database),
                "--json",
                *arguments,
            )
            self.assertEqual(first["claim_id"], replay["claim_id"])

            facts = self._run_ok(
                "--database",
                str(database),
                "--json",
                "facts",
                "--observation-id",
                str(observation_id),
            )
            row = next(item for item in facts if item["fact_key"] == "score.initial.q25")
            self.assertEqual(row["sample_size"], 5)
            self.assertEqual(row["calculation_method_key"], "percentile_inc_type7_v1")
            self.assertEqual(row["calculation_input_sha256"], "a" * 64)

            missing = list(arguments)
            index = missing.index("--sample-size")
            del missing[index : index + 2]
            rejected = self._run(
                "--database",
                str(database),
                "--json",
                *missing,
            )
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(
                json.loads(rejected.stderr)["error_code"],
                "STATISTICAL_SAMPLE_SIZE_REQUIRED",
            )

    @staticmethod
    def _fact_arguments(observation_id: int) -> tuple[str, ...]:
        return (
            "fact-add",
            "--observation-id",
            str(observation_id),
            "--fact-key",
            "score.initial.q25",
            "--value",
            "330",
            "--evidence-grade",
            "official",
            "--source-title",
            "2026年硕士研究生招生专业目录",
            "--source-url",
            "https://example.edu/2026-catalog.xls",
            "--source-institution",
            "西北农林科技大学研究生院",
            "--source-document-type",
            "official_catalog",
            "--source-content-sha256",
            "7" * 64,
            "--applicable-year",
            "2026",
            "--retrieved-date",
            "2026-08-13",
            "--population-scope",
            "目标项目普通统考拟录取者",
            "--statistic-scope",
            "PERCENTILE.INC 25%分位数",
            "--sample-size",
            "5",
            "--calculation-method-key",
            "percentile_inc_type7_v1",
            "--calculation-input-sha256",
            "a" * 64,
        )

    def _run_ok(self, *arguments: str):
        result = self._run(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            ["python", "manage.py", *arguments],
            cwd=REPOSITORY_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env=environment,
        )


if __name__ == "__main__":
    unittest.main()
