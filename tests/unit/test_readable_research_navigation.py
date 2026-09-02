"""Guards for the single human-readable research entrypoint.

TraceId: 7e282555-47f3-432d-a123-7ff8d5477154
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote


class ReadableResearchNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[2]
        self.readme_path = self.repository_root / "README.md"
        self.overview_path = (
            self.repository_root / "docs" / "start-here-current-conclusions.md"
        )
        self.docs_readme_path = self.repository_root / "docs" / "README.md"
        self.index_path = self.repository_root / "docs" / "research-report-index.md"

    @staticmethod
    def _local_markdown_targets(document_path: Path) -> set[Path]:
        content = document_path.read_text(encoding="utf-8")
        targets: set[Path] = set()
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", content):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_part = unquote(raw_target.split("#", 1)[0])
            targets.add((document_path.parent / path_part).resolve())
        return targets

    def test_readme_leads_to_one_overview_and_collapses_the_evidence_wall(self) -> None:
        readme = self.readme_path.read_text(encoding="utf-8")
        overview = self.overview_path.read_text(encoding="utf-8")
        index = self.index_path.read_text(encoding="utf-8")

        self.assertIn("docs/start-here-current-conclusions.md", readme)
        self.assertIn("docs/research-report-index.md", readme)
        self.assertIn("<summary>展开全部专题报告摘要</summary>", readme)
        self.assertIn("不要从文件列表开始读", self.docs_readme_path.read_text(encoding="utf-8"))
        self.assertIn("整个项目唯一的普通阅读入口", overview)
        self.assertIn("## 当前真正值得看的梯子", overview)
        self.assertIn("## 仍保留、但当前不放在梯子正中的 8 项", overview)
        self.assertIn("## 新扩展池：哪些可能升入主池", overview)
        self.assertIn("## 现在仍然缺少的决定性信息", overview)
        self.assertIn("不是你要排除的“攻防上机”", overview)
        self.assertIn("不是招生预测", overview)
        self.assertIn("按问题找文件，不要从头读", index)
        self.assertIn("## 第一层：做决定时才看的总表", index)
        self.assertIn("## 第六层：项目维护与证据规则", index)

    def test_navigation_documents_have_no_broken_relative_links(self) -> None:
        for document_path in (
            self.readme_path,
            self.docs_readme_path,
            self.overview_path,
            self.index_path,
        ):
            for target in self._local_markdown_targets(document_path):
                self.assertTrue(
                    target.exists(),
                    f"Broken local Markdown link in {document_path}: {target}",
                )

    def test_every_public_markdown_report_is_reachable_from_the_index(self) -> None:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "ls-files",
                "docs/*.md",
                "docs/**/*.md",
            ],
            cwd=self.repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            self.skipTest("Git metadata is unavailable for the public-report inventory")

        tracked = {
            (self.repository_root / line.strip()).resolve()
            for line in completed.stdout.splitlines()
            if line.strip()
        }
        expected = tracked | {
            self.docs_readme_path.resolve(),
            self.overview_path.resolve(),
            self.index_path.resolve(),
        }
        expected.remove(self.index_path.resolve())

        linked = self._local_markdown_targets(self.index_path)
        indexed_documents = {path for path in linked if path.suffix.lower() == ".md"}
        self.assertSetEqual(expected, indexed_documents)

    def test_public_navigation_does_not_expose_long_personal_identifiers(self) -> None:
        pattern = re.compile(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])")
        for document_path in (
            self.readme_path,
            self.docs_readme_path,
            self.overview_path,
            self.index_path,
        ):
            self.assertIsNone(pattern.search(document_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
