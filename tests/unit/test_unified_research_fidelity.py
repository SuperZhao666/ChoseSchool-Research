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


# TraceId: 6e1e24ca-cd0a-45ae-9808-f82bd5b15ad8
# These eight reviewed rows are old HNU catalogue/personal-policy summaries,
# not scores. Their replacement facts now live in the relevant project or in
# the research notes. The immutable archive and all other signatures still apply.
HNU_POLICY_ROW_MIGRATIONS = {
    ('2023', '085400', '101', '204', '302', '866', '408'): 'historical:2023',
    ('2024', '101', '204', '302', '866'): 'historical:2024',
    ('2025', '085400', '101', '204', '302', '866'): 'historical:2025',
    ('2026', '085400', '101', '204', '302', '866'): 'current:2026',
    ('2027', '085400', '408', '866', '408', '101', '204', '302', '408'): 'notice:2027',
    ('2026', '101', '204', '302', '866', '22408'): 'notes:2026-status',
    ('2027', '408'): 'notice:2027',
    ('2027', '22408'): 'notes:2027-status',
}
HNU_MIGRATION_GROUP = ('school-029', 'root-expanded.md', '湖南大学')


def hnu_source(readme: str) -> str:
    start = readme.index('<a id="school-029"></a>')
    following = re.search(r'<a id="school-\d+"></a>', readme[start + 1:])
    return readme[start:start + 1 + following.start()] if following else readme[start:]


def _hnu_entity(body: str, attribute: str, key: str) -> str:
    opening = re.search(r'<section\b[^>]*' + attribute + '="' + re.escape(key) + r'"[^>]*>', body)
    assert opening, f'Missing HNU entity: {attribute}={key}'
    depth = 1
    for tag in re.finditer(r'</?section\b[^>]*>', body[opening.end():]):
        depth += -1 if tag.group().startswith('</') else 1
        if not depth:
            return body[opening.end():opening.end() + tag.start()]
    raise AssertionError(f'Unclosed HNU entity: {key}')


def _hnu_table_rows(body: str) -> list[list[str]]:
    return [[cell.strip().replace('**', '') for cell in line.split('|')[1:-1]]
            for line in body.splitlines() if line.startswith('| 20')]


def reviewed_hnu_numeric_migrations(readme: str) -> dict[tuple[str, ...], str]:
    """Approve only the listed row moves after checking their new entity facts."""
    body = hnu_source(readme)
    college = _hnu_entity(body, 'data-college-key', 'csee')
    current = _hnu_entity(college, 'data-project-key', 'csee-085400')
    former = _hnu_entity(body, 'data-college-key', 'former-csee')
    history = _hnu_entity(former, 'data-project-key', 'former-csee-085400')
    notes = _hnu_entity(body, 'class', 'admission-notes')
    rows = _hnu_table_rows(current)
    catalog = [row for row in rows if len(row) == 7 and row[0] in ('2026', '2027')]
    assert len(catalog) == 2, 'HNU current project must retain both annual catalogue rows'
    by_year = {row[0]: row for row in catalog}
    assert '计算机学院 085400' in by_year['2026'][1]
    assert '全日制' in by_year['2026'][1]
    assert by_year['2026'][2:6] == ['101 思想政治理论', '204 英语二', '302 数学二', '866 数据结构']
    assert '085400' in by_year['2027'][1]
    assert by_year['2027'][2:5] == ['公告未列出'] * 3
    assert by_year['2027'][5] == '866 数据结构 → 408 计算机学科专业基础'
    assert '只确认第四科变化' in by_year['2027'][6]
    assert '普通统考计划和完整四科仍待核' in by_year['2027'][6]
    assert '英语一或英语二均可' in current
    assert '不能因为不是英语二而自动排除' in current
    assert '2026 正式四科 `101+204+302+866` 已核，因此记录为 `non_strict`' in notes
    assert '2027 保持“当年正式目录待核”' in notes
    assert '同一年度、同一项目正式完整 `101+204+302+408` 原行' in notes

    # Check every score row, including repeated comparison rows, in its entity.
    # This prevents a correct duplicate from masking a changed displayed score.
    expected = {
        'computer-history': [('2023', '96', '325', '326', '365.5', '367.24', '411'),
                             ('2024', '62', '356', '356', '371.5', '374.15', '408'),
                             ('2025', '80', '364', '364', '385', '385.20', '417')],
        'software-history': [('2023', '38', '360', '361', '384.5', '385.42', '414'),
                             ('2024', '25', '348', '348', '364', '366.80', '422'),
                             ('2025', '24', '350', '350', '369', '372.54', '415')],
    }
    all_expected = {row for values in expected.values() for row in values}
    all_expected.add(('2026', '105', '368', '368', '396', '396.10', '437'))
    for key, annual in expected.items():
        direction = _hnu_entity(history, 'data-direction-key', key)
        direction_rows = [row for row in _hnu_table_rows(direction) if len(row) == 9]
        assert [tuple([row[0], *row[3:]]) for row in direction_rows] == annual
        for row in direction_rows:
            assert numeric_signature(row[1]) == ('101', '204', '302', '866')
            assert '信息科学与工程学院' in row[2]
    for row in [r for r in rows if len(r) == 9]:
        assert tuple([row[0], *row[3:]]) in all_expected, 'Changed HNU score/population'
        assert numeric_signature(row[1]) == ('101', '204', '302', '866')
        if row[0] == '2026':
            assert '计算机学院，合并后 085400' in row[2]
    assert any(row[0] == '2026' and len(row) == 9 for row in rows)
    return dict(HNU_POLICY_ROW_MIGRATIONS)


def is_reviewed_hnu_migration(group: dict, row: list[str], migrations: dict) -> bool:
    return ((group['destination'], group['module'], group['topic']) == HNU_MIGRATION_GROUP
            and tuple(row) in migrations)


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
        migrations = reviewed_hnu_numeric_migrations(self.readme)
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
                    if is_reviewed_hnu_migration(group, row, migrations):
                        continue
                    self.assertIn(tuple(row), sections[group["destination"]])

    def test_hnu_migrations_are_limited_to_eight_reviewed_policy_rows(self) -> None:
        migrations = reviewed_hnu_numeric_migrations(self.readme)
        self.assertEqual(len(migrations), 8)
        group = {'destination': 'school-029', 'module': 'root-expanded.md', 'topic': '湖南大学'}
        self.assertTrue(is_reviewed_hnu_migration(group, ['2027', '408'], migrations))
        for field, value in [('destination', 'school-069'), ('module', 'empirical.md'), ('topic', '其他学校')]:
            self.assertFalse(is_reviewed_hnu_migration({**group, field: value}, ['2027', '408'], migrations))
        self.assertFalse(is_reviewed_hnu_migration(group, ['2026', '105', '368', '396'], migrations))
        self.assertFalse(is_reviewed_hnu_migration(group, ['2027', '409'], migrations))

    def test_hnu_policy_migrations_reject_changed_scores_subjects_or_confirmation(self) -> None:
        body = hnu_source(self.readme)
        mutations = [
            body.replace('| 105 | 368 | 368 | **396** |', '| 105 | 369 | 368 | **396** |', 1),
            body.replace('| 105 | 368 | 368 | **396** |', '| 105 | 368 | 368 | **397** |', 1),
            body.replace('| 866 数据结构 | 当年正式目录已核', '| 408 数据结构 | 当年正式目录已核', 1),
            body.replace('2027 保持“当年正式目录待核”', '2027 已确认完整 22408', 1),
            body.replace('| 公告未列出 | 公告未列出 | 公告未列出 |',
                         '| 101 思想政治理论 | 204 英语二 | 302 数学二 |', 1),
            body.replace('data-direction-key="computer-history"', 'data-direction-key="wrong-project"', 1),
        ]
        for mutated in mutations:
            with self.subTest(mutation=mutations.index(mutated)):
                self.assertNotEqual(mutated, body, 'Negative case must mutate the current source')
                with self.assertRaises(AssertionError):
                    reviewed_hnu_numeric_migrations(mutated)

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
