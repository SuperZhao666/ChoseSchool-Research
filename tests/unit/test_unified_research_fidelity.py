"""Guard against losing researched data when reorganizing the single README.

TraceId: 54eea253-6109-4d0d-9da1-ddfa1efb94de
These checks protect quantitative content and placement; they do not certify
source truth or turn historical/secondary observations into official facts.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


def numeric_signature(line: str) -> tuple[str, ...]:
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"https?://\S+", "", line)
    line = re.sub(r"[0-9a-fA-F]{32,}", "", line)
    return tuple(re.findall(r"(?<![a-zA-Z])(?:\d+\.\d+|\d+)(?![a-zA-Z])", line))


# TraceId: 4633df94-71b7-4339-ae57-1ad2dd0576cb
SCORE_SUBJECT_COLUMN = "当年初试科目与证据"


def original_cells(cells: list[str], header: list[str]) -> list[str]:
    """Exclude only the added subject column from the immutable numeric baseline."""
    return [cell for i, cell in enumerate(cells)
            if i >= len(header) or header[i].strip() != SCORE_SUBJECT_COLUMN]


def table_numeric_signatures(body: str) -> set[tuple[str, ...]]:
    lines = body.splitlines(); header = []; rows = set()
    for i, line in enumerate(lines):
        if not line.startswith('|'):
            header = []; continue
        cells = line.strip().strip('|').split('|')
        if i + 1 < len(lines) and re.fullmatch(r'\|[ :|\-]+\|', lines[i + 1]):
            header = cells
        rows.add(numeric_signature(' | '.join(original_cells(cells, header))))
    return rows


class UnifiedResearchFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.readme = (cls.root / "README.md").read_text(encoding="utf-8")
        cls.manifest = json.loads(
            (cls.root / "research/coverage/unified-readme-fidelity.json").read_text(encoding="utf-8")
        )

    def test_historical_sources_remain_immutable(self) -> None:
        for source in self.manifest["archive_sources"]:
            with self.subTest(source=source["path"]):
                actual = hashlib.sha256((self.root / source["path"]).read_bytes()).hexdigest()
                self.assertEqual(actual, source["sha256"])

    def test_retained_quantitative_rows_stay_in_their_school_or_evidence_group(self) -> None:
        sections = {}
        pattern = r'<a id="((?:school|evidence)-\d+|complete-evidence)"></a>'
        matches = list(re.finditer(pattern, self.readme))
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self.readme)
            body = self.readme[match.end():end]
            sections[match[1]] = table_numeric_signatures(body)
        for group in self.manifest["quantitative_groups"]:
            with self.subTest(topic=group["topic"], module=group["module"]):
                self.assertIn(group["destination"], sections)
                for row in group["numeric_rows"]:
                    self.assertIn(tuple(row), sections[group["destination"]])

    def test_added_subject_column_does_not_hide_changes_to_original_scores(self) -> None:
        header = ['年度', SCORE_SUBJECT_COLUMN, '最低分', '中位数']
        cells = ['2026', '101／204／302／408', '298', '356']
        self.assertEqual(original_cells(cells, header), ['2026', '298', '356'])
        mutated = ['2026', '101／204／302／408', '299', '356']
        self.assertNotEqual(original_cells(cells, header), original_cells(mutated, header))
        self.assertEqual(original_cells(cells, ['年度', '原专业课', '最低分', '中位数']), cells)

    def test_reading_file_contains_full_history_and_corrections(self) -> None:
        for text in ("2023—2026", "25%位置", "75%位置", "导师", "实践", "成果",
                     "303—304", "17.2", "原件追溯待恢复", "固定18", "27行",
                     "研究池", "不能", "354.14"):
            self.assertIn(text, self.readme)
        self.assertNotIn("2026学制3年、学费1万元／年，2027不能自动继承。", self.readme)
        self.assertNotIn("已经足以否定“名额越少，分数越低”的硬规则", self.readme)
        self.assertNotIn("本人现有本科算法竞赛证书", self.readme)

    def test_full_file_navigation_and_foldouts_are_balanced(self) -> None:
        self.assertEqual(self.readme.count("<details>"), self.readme.count("</details>"))
        ids = re.findall(r'<a id="([^"]+)"', self.readme)
        self.assertEqual(len(ids), len(set(ids)))
        for school in self.manifest["schools"]:
            self.assertEqual(len(re.findall(r"(?m)^### " + re.escape(school) + r"$", self.readme)), 1)
        self.assertIn("下载同一份完整README", self.readme)
        self.assertIn("500 KiB", self.readme)


if __name__ == "__main__":
    unittest.main()
