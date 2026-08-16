from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import REPOSITORY_ROOT


class SecondaryObservationCliTest(unittest.TestCase):
    def test_cli_returns_explicit_non_official_contract_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "secondary.sqlite3"
            self._run_json("--database", str(database), "--json", "init")
            first = self._run_json(
                "--database", str(database), "--json", *_arguments()
            )
            replay = self._run_json(
                "--database", str(database), "--json", *_arguments()
            )
            self.assertTrue(first["created"])
            self.assertFalse(replay["created"])
            self.assertEqual(first["observation_id"], replay["observation_id"])
            self.assertEqual(first["status"], "secondary_only")
            self.assertFalse(first["establishes_official_catalog"])
            self.assertFalse(first["can_confirm_strict_22408"])
            self.assertTrue(first["trace_id"])

    def _run_json(self, *arguments: str):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            ["python", "manage.py", *arguments],
            cwd=REPOSITORY_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


def _arguments() -> tuple[str, ...]:
    return (
        "secondary-observation-add",
        "--school", "中国科学技术大学",
        "--college", "计算机科学与技术学院",
        "--program-code", "085404",
        "--program-name", "计算机技术",
        "--admission-year", "2025",
        "--politics", "101",
        "--english", "204",
        "--math", "302",
        "--professional", "408",
        "--study-mode", "全日制",
        "--source-title", "灰灰考研院校数据汇总",
        "--source-url", "https://example.com/huihui/ustc-2025",
        "--source-institution", "灰灰考研",
        "--source-content-sha256", "a" * 64,
        "--applicable-year", "2025",
        "--published-date", "2025-04-01",
        "--retrieved-date", "2026-08-03",
        "--source-excerpt", "计算机技术：101、204、302、408。",
        "--project-identity-basis", "页面同时列出学校、学院、专业代码和专业名称。",
    )


if __name__ == "__main__":
    unittest.main()
