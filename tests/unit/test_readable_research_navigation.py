"""A single self-contained current pool, separate from historical evidence.

TraceId: 8c689b86-5d60-4f2f-96bc-868f6aa1aa83
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote


class ReadableResearchNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.readme = (self.root / "README.md").read_text(encoding="utf-8")

    def school(self, name: str) -> str:
        sections = re.split(r"(?m)^### ", self.readme)
        matches = [part for part in sections[1:] if part.splitlines()[0] == name]
        self.assertEqual(len(matches), 1, f"Expected one consolidated card: {name}")
        return matches[0]

    def test_readme_is_the_pool_and_does_not_send_readers_to_topic_reports(self) -> None:
        self.assertEqual(len(re.findall(r"(?m)^# ", self.readme)), 1)
        for term in ("2027 择校池", "逐校比较", "怎样判断"):
            self.assertIn(term, self.readme)
        targets = re.findall(r"\[[^\]]*\]\(([^)]+)\)", self.readme)
        self.assertTrue(targets)
        for target in targets:
            self.assertTrue(target.startswith(("https://", "http://", "#")), target)
        for phrase in ("最新专题", "先读这份", "展开全部专题报告摘要", "全部报告索引", "```powershell"):
            self.assertNotIn(phrase, self.readme)

    def test_public_docs_no_longer_accumulate_dated_research_reports(self) -> None:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "docs/*.md", "docs/**/*.md"],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        if result.returncode:
            self.skipTest("Git inventory unavailable")
        allowed = {"docs/README.md", "docs/architecture.md", "docs/data-dictionary.md",
                   "docs/evidence-and-status.md", "docs/operations.md",
                   "docs/decisions/ADR-001-local-sqlite-and-append-only-evidence.md"}
        self.assertEqual(set(result.stdout.splitlines()), allowed)
        self.assertTrue((self.root / "research/archive/README.md").is_file())
        self.assertTrue((self.root / "research/archive/docs/research-report-index.md").is_file())

    def test_every_historically_qualified_school_remains_visible(self) -> None:
        path = self.root / "research/archive/docs/national-211-strict-22408-status-matrix-2026-08-24.md"
        names = re.findall(r"(?m)^\| \d+ \| ([^|]+) \| `strict_match` \|", path.read_text(encoding="utf-8"))
        self.assertEqual(len(names), 57)
        for name in names:
            self.assertIn(name.strip(), self.readme)
        self.assertIn("不代表 2027", self.readme)

    def test_core_projects_are_consolidated_by_school_with_sources_and_costs(self) -> None:
        core = {
            "北京交通大学": ("010", "085405"), "郑州大学": ("084", "085410"),
            "西南交通大学": ("048", "085410"), "辽宁大学": ("018", "085405"),
            "新疆大学": ("308", "085405"), "厦门大学": ("131", "085404"),
            "重庆大学": ("014", "030", "085404", "085400"),
            "山东大学": ("047", "085404"), "中国海洋大学": ("002", "085404"),
            "华东师范大学": ("135", "085404"),
            "合肥工业大学": ("005", "085404", "085410"),
            "苏州大学": ("018", "085405"), "南昌大学": ("006", "017", "085405"),
        }
        for name, identifiers in core.items():
            section = self.school(name)
            for identifier in identifiers:
                self.assertIn(identifier, section)
            self.assertIn("http", section)
            self.assertRegex(section, r"学费|万元")
            self.assertIn("2027", section)

    def test_current_population_limits_are_not_lost_during_condensation(self) -> None:
        for value in ("172", "174", "27", "17", "72", "26", "829", "9万元"):
            self.assertIn(value, self.school("华东师范大学"))
        for value in ("480", "常规班", "士兵", "2027"):
            self.assertIn(value, self.school("中国科学技术大学"))
        self.assertRegex(self.school("南昌大学"), r"2026目标.*(?:缺|未知)")
        hfut = self.school("合肥工业大学")
        for value in ("阶段计划41", "阶段计划46", "正式拟录取人数和中位数"):
            self.assertIn(value, hfut)
        self.assertIn("376.5", self.school("苏州大学"))
        self.assertRegex(self.school("郑州大学"), r"86人[^。]*368")

    def test_current_and_maintenance_documents_have_valid_local_links(self) -> None:
        for relative in ("README.md", "docs/README.md", "docs/data-dictionary.md"):
            document = self.root / relative
            content = document.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content))
            for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
                if raw.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                target = document.parent / unquote(raw.split("#", 1)[0])
                self.assertTrue(target.exists(), f"Broken link: {relative}: {raw}")

    def test_methods_keep_historical_evidence_separate_from_personal_predictions(self) -> None:
        for boundary in ("不是录取难度排名", "复试线", "拟录取", "推免", "不是你的个人录取概率",
                         "同校多个项目也不是独立实验", "尚未提供模考成绩", "网络安全", "兰州大学"):
            self.assertIn(boundary, self.readme)


if __name__ == "__main__":
    unittest.main()
