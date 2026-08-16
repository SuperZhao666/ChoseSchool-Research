from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import REPOSITORY_ROOT


class ApplicantAchievementCliTest(unittest.TestCase):
    def test_add_replay_list_and_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "achievement.sqlite3"
            self._run_json("--database", str(database), "--json", "init")

            evidence = [
                {
                    "source_title": "校级学业奖学金证书",
                    "source_url": "https://drive.google.com/file/d/test-scholarship/view",
                    "source_access_scope": "private_user_drive",
                    "source_document_type": "scholarship_certificate",
                    "source_mime_type": "image/jpeg",
                    "source_content_sha256": "a" * 64,
                    "source_file_size_bytes": 2048,
                    "source_retrieved_on": "2026-08-11",
                    "source_reviewed_on": "2026-08-11",
                    "review_method": "full_document_visual_review",
                    "evidence_grade": "primary_document_user_copy",
                    "evidence_status": "document_visual_confirmed",
                    "claim_text": "证书正文支持学年和奖项，未作学校官网独立核验",
                    "relationship": "supports",
                }
            ]
            command = (
                "achievement-add",
                "--key",
                "scholarship.2024-2025.academic-third",
                "--category",
                "scholarship",
                "--title",
                "2024—2025 学年学业奖学金",
                "--issuer",
                "临沂大学",
                "--year",
                "2025",
                "--period",
                "2024—2025 学年；证书仅精确到 2025 年 12 月",
                "--scope-level",
                "school",
                "--stage",
                "academic_year",
                "--result",
                "三等奖学金",
                "--participation-type",
                "not_applicable",
                "--details-json",
                '{"competition_family":null}',
                "--verification-status",
                "document_confirmed",
                "--evidence-json",
                json.dumps(evidence, ensure_ascii=False),
            )
            first = self._run_json(
                "--database", str(database), "--json", *command
            )
            replay = self._run_json(
                "--database", str(database), "--json", *command
            )
            self.assertTrue(first["created"])
            self.assertFalse(replay["created"])
            self.assertEqual(first["event_id"], replay["event_id"])

            rows = self._run_json(
                "--database",
                str(database),
                "--json",
                "achievements",
                "--category",
                "scholarship",
                "--year",
                "2025",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["result"], "三等奖学金")
            self.assertEqual(rows[0]["verification_status"], "document_confirmed")
            self.assertEqual(rows[0]["fingerprint_version"], "v2")
            self.assertIsNone(rows[0]["evidence"][0]["source_url"])
            self.assertEqual(
                rows[0]["evidence"][0]["source_access_scope"],
                "private_user_drive",
            )

            doctor = self._run_json(
                "--database", str(database), "--json", "doctor"
            )
            self.assertEqual(doctor["status"], "ok")
            self.assertEqual(doctor["applicant_achievement_event_count"], 1)
            self.assertEqual(doctor["applicant_evidence_document_count"], 1)
            self.assertEqual(doctor["applicant_evidence_review_event_count"], 1)
            self.assertEqual(
                doctor["applicant_achievement_evidence_review_link_count"],
                1,
            )

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


if __name__ == "__main__":
    unittest.main()
