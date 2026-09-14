"""Validate the delivered full-text site, including original numeric evidence.

TraceId: a5a6f785-04be-4f85-8104-c604a2d186af
"""
import hashlib
import json
import re
import unittest
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt
from web.build import make_panels, prepare_admissions, render
from tests.unit.test_unified_research_fidelity import numeric_signature, original_cells, SCORE_SUBJECT_COLUMN


class ReaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []; self.links = []; self.rows = defaultdict(set)
        self.section = None; self.cells = None; self.cell = None
        self.tables = []; self.table = None; self.main = False; self.text = []
        self.main_links = []; self.panels = []
        self.generated_navigation = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'nav' and attrs.get('data-reader-ui') == 'true':
            self.generated_navigation = True
        if 'id' in attrs:
            self.ids.append(attrs['id'])
            if re.fullmatch(r'(school|evidence)-\d+|complete-evidence', attrs['id']):
                self.section = attrs['id']
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
            if self.main and not self.generated_navigation: self.main_links.append(attrs['href'])
        if tag == 'section' and attrs.get('class') == 'reader-panel':
            self.panels.append(attrs)
        if tag == 'main': self.main = True
        if tag == 'table': self.table = []
        if tag == 'tr': self.cells = []
        if tag in ('td', 'th'): self.cell = []

    def handle_data(self, data):
        if self.main and not self.generated_navigation: self.text.append(data)
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'nav': self.generated_navigation = False
        if tag == 'main': self.main = False
        if tag in ('td', 'th') and self.cell is not None:
            self.cells.append(''.join(self.cell)); self.cell = None
        if tag == 'tr' and self.cells is not None:
            header = self.table[0] if self.table else self.cells
            self.rows[self.section].add(numeric_signature(' | '.join(original_cells(self.cells, header))))
            self.table.append(self.cells); self.cells = None
        if tag == 'table':
            self.tables.append(self.table); self.table = None


class WebReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.source = (cls.root / 'README.md').read_text(encoding='utf-8')
        cls.page = (cls.root / 'dist/index.html').read_text(encoding='utf-8')
        cls.parser = ReaderParser(); cls.parser.feed(cls.page)
        cls.manifest = json.loads((cls.root / 'research/coverage/unified-readme-fidelity.json').read_text(encoding='utf-8'))

    def test_published_assets_are_from_current_complete_source(self):
        page, meta = render(self.source)
        self.assertEqual(self.page, page)
        self.assertEqual(json.loads((self.root / 'dist/content-manifest.json').read_text(encoding='utf-8')), meta)
        download = (self.root / 'dist/README.md').read_bytes()
        self.assertEqual(download, self.source.encode('utf-8'))
        self.assertEqual(hashlib.sha256(download).hexdigest(), meta['source_sha256'])
        for name in ('reader.css', 'reader.js'):
            self.assertEqual((self.root / 'dist' / name).read_text(encoding='utf-8'), (self.root / 'web' / name).read_text(encoding='utf-8'))

    def test_every_local_anchor_resolves_without_duplicate_ids(self):
        ids = Counter(self.parser.ids)
        self.assertFalse([name for name, count in ids.items() if count != 1])
        for target in self.parser.links:
            if target.startswith('#'):
                self.assertIn(unquote(target[1:]), ids, target)
            elif target.startswith('./'):
                self.assertTrue((self.root / 'dist' / target[2:]).is_file(), target)
        self.assertIn('完整比较依据与历史证据', ids)

    def test_school_navigation_retains_all_existing_ids(self):
        source_ids = re.findall(r'<a id="(school-\d+)"', self.source)
        self.assertEqual(len(source_ids), 104)
        for value in source_ids:
            self.assertIn(value, self.parser.ids)
            self.assertIn(f'data-panel-target="{value}"', self.page)
        self.assertEqual(self.page.count('<details>'), self.source.count('<details>'))
        self.assertEqual(self.page.count('<p class="school-tier">'), len(source_ids))
        for school, tier in [('华东师范大学', '985'), ('西南大学', '211（非985）'), ('贵州大学', '211（非985）')]:
            self.assertIn(f'<span class="school-name">{school}</span><span class="school-meta">{tier}</span>', self.page)
        self.assertIn('双非指非985、非211', self.source)

    def test_panels_preserve_every_paragraph_link_table_and_old_anchor(self):
        panels = make_panels(self.source)
        self.assertEqual(''.join(panel['source'] for panel in panels), self.source)
        self.assertEqual(len(panels), 112)
        self.assertEqual([p['data-panel'] for p in self.parser.panels if 'hidden' not in p], ['school-001'])
        plain = ReaderParser()
        plain.feed('<main>' + MarkdownIt('commonmark', {'html': True}).enable('table').render(self.source) + '</main>')
        normalize = lambda parts: re.sub(r'\s+', ' ', ''.join(parts)).strip()
        self.assertEqual(normalize(self.parser.text), normalize(plain.text))
        self.assertEqual(self.parser.main_links, plain.main_links)
        self.assertEqual(self.parser.tables, plain.tables)
        for panel in panels:
            depth = 0
            for tag in re.findall(r'</?details>', panel['source']):
                depth += 1 if tag == '<details>' else -1
                self.assertGreaterEqual(depth, 0, panel['key'])
            self.assertEqual(depth, 0, panel['key'])

    def test_late_switch_labels_require_explicit_current_year_project_evidence(self):
        panels = make_panels(self.source)
        self.assertEqual({p['key'] for p in panels if p['late']}, {'school-028', 'school-061', 'school-068', 'school-069'})
        self.assertIn('data-status="date-unresolved"', next(p['source'] for p in panels if p['key'] == 'school-008'))
        bad = self.source.replace('data-announced="2026-07-06"', 'data-announced="2026-06-30"')
        with self.assertRaises(ValueError): make_panels(bad)
        bad = self.source.replace('data-announced="2026-07-06"', 'data-announced="2025-07-06"')
        with self.assertRaises(ValueError): make_panels(bad)

    def test_guizhou_restored_aggregates_keep_rule_derived_population_limits(self):
        guizhou = next(p['source'] for p in make_panels(self.source) if p['key'] == 'school-003')
        for text in ('336.35', '333.68', '23／75', '326', 'official_mixed', '不是最终拟录取名单逐人直证', '官方旧PDF404'):
            self.assertIn(text, guizhou)

    def test_score_rows_show_their_own_year_subjects_not_the_new_408_notice(self):
        # TraceId: 4633df94-71b7-4339-ae57-1ad2dd0576cb
        annotated = [table for table in self.parser.tables if SCORE_SUBJECT_COLUMN in table[0]]
        self.assertEqual(self.page.count('<table class="exam-subjects">'), len(annotated))
        self.assertGreaterEqual(len(annotated), 194)
        self.assertGreaterEqual(sum(len(table) - 1 for table in annotated), 935)
        expected = {
            'school-001': {2023: '907', 2024: '907', 2025: '891', 2026: '891'},
            'school-012': {2023: '901', 2024: '902', 2025: '861', 2026: '408'},
            'school-068': {2023: '914', 2024: '914', 2025: '824', 2026: '824'},
            'school-069': {2023: '885', 2024: '885', 2025: '885', 2026: '885'},
        }
        for panel in make_panels(self.source):
            if panel['key'] not in expected: continue
            parser = ReaderParser()
            parser.feed('<main>' + MarkdownIt('commonmark', {'html': True}).enable('table').render(panel['source']) + '</main>')
            annual = defaultdict(list)
            for table in parser.tables:
                if SCORE_SUBJECT_COLUMN not in table[0]: continue
                column = table[0].index(SCORE_SUBJECT_COLUMN)
                self.assertEqual(column, 1, '科目应紧跟年份，不能放到远端说明区')
                for row in table[1:]:
                    match = re.match(r'\s*(20\d\d)', row[0])
                    if match: annual[int(match[1])].append(row[column])
            for year, code in expected[panel['key']].items():
                self.assertTrue(any(re.search(r'(?<!\d)' + code + r'(?!\d)', value) for value in annual[year]),
                                (panel['key'], year, code))

    def test_subject_annotations_keep_unknown_and_mixed_exam_boundaries_visible(self):
        panels = {p['key']: p['source'] for p in make_panels(self.source)}
        for key, fragments in {
            'school-010': ['915', '混'],
            'school-008': ['2025', '待核'],
            'school-034': ['301', '302'],
        }.items():
            parser = ReaderParser()
            parser.feed('<main>' + MarkdownIt('commonmark', {'html': True}).enable('table').render(panels[key]) + '</main>')
            annotations = []
            for table in parser.tables:
                if SCORE_SUBJECT_COLUMN in table[0]:
                    column = table[0].index(SCORE_SUBJECT_COLUMN)
                    annotations.extend(row[0] + ' ' + row[column] for row in table[1:])
            text = '\n'.join(annotations)
            for fragment in fragments: self.assertIn(fragment, text, key)

    def test_total_score_distributions_do_not_depend_on_subjects_in_a_previous_heading(self):
        # TraceId: d36580a9-e711-47ec-9786-53ec83803d21
        for table in self.parser.tables:
            if table[0][0] not in ('成绩项目', '初试字段'):
                continue
            if not any(row[0] in ('初试总分', '总分') for row in table[1:]):
                continue
            self.assertEqual(table[0][1], SCORE_SUBJECT_COLUMN, table[0])
            for row in table[1:]:
                self.assertRegex(row[1], r'20\d{2}', row)

    def test_subject_years_follow_explicit_population_headings_not_table_order(self):
        # TraceId: 08b14bba-791f-4838-89fc-df06a775482c
        lines = self.source.splitlines()
        checked = 0
        for token in MarkdownIt('commonmark', {'html': True}).enable('table').parse(self.source):
            if token.type != 'table_open':
                continue
            start, end = token.map
            if SCORE_SUBJECT_COLUMN not in lines[start]:
                continue
            heading = next((lines[i] for i in range(start - 1, max(-1, start - 5), -1)
                            if lines[i].strip()), '')
            match = re.match(r'\*\*分科及总分：(20\d{2})\b', heading)
            if not match:
                continue
            checked += 1
            for line in lines[start + 2:end]:
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                with self.subTest(heading=heading, field=cells[0]):
                    self.assertTrue(cells[1].startswith(match[1] + '：'), cells[1])
        self.assertGreaterEqual(checked, 48)

    def test_all_individual_subject_distributions_keep_full_exam_context(self):
        # Covers horizontal subject columns and vertical subject rows alike.
        # TraceId: 08b14bba-791f-4838-89fc-df06a775482c
        checked = 0
        for table in self.parser.tables:
            headers = table[0]
            vertical = '成绩字段' in headers and '招生年度' in headers and any(
                '思想政治理论' in cell for row in table[1:] for cell in row)
            horizontal = any('政治' in cell for cell in headers) and any(
                '平均' in cell or '总分' in cell or '中位' in cell for cell in headers)
            if not (vertical or horizontal):
                continue
            checked += 1
            with self.subTest(headers=headers):
                self.assertIn(SCORE_SUBJECT_COLUMN, headers)
                column = headers.index(SCORE_SUBJECT_COLUMN)
                for row in table[1:]:
                    self.assertTrue(row[column].strip(), row)
        self.assertGreaterEqual(checked, 7)

    def test_backtest_rows_show_input_and_target_exams_without_rewriting_scores(self):
        tables = [table for table in self.parser.tables if table[0][0] == '学校项目/目标年']
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(len(table) - 1, 27)
        self.assertEqual(table[0][1], SCORE_SUBJECT_COLUMN)
        for row in table[1:]:
            self.assertIn('输入', row[1])
            self.assertIn('目标', row[1])
            if row[0] == '西南交通大学 048-085410／2026':
                self.assertIn('2024、2025', row[1])
                self.assertIn('840数据结构与程序设计', row[1])
                self.assertIn('目标2026', row[1])
                self.assertIn('408计算机学科专业基础', row[1])
                self.assertEqual(row[4], '340（19）')
            if row[0] == '北京交通大学 010-085405／2026':
                self.assertIn('输入2025', row[1])
                self.assertIn('861软件工程专业基础', row[1])
                self.assertIn('目标2026', row[1])
                self.assertIn('408计算机学科专业基础', row[1])

    def test_swu334_annual_lines_use_its_own_restored_catalogues(self):
        swu = next(p['source'] for p in make_panels(self.source) if p['key'] == 'school-001')
        parser = ReaderParser()
        parser.feed('<main>' + MarkdownIt('commonmark', {'html': True}).enable('table').render(swu) + '</main>')
        annual_lines = [table for table in parser.tables
                        if SCORE_SUBJECT_COLUMN in table[0] and any(
                            row[0] == '2023' and row[2] == '318' for row in table[1:])]
        self.assertEqual(len(annual_lines), 1)
        for row, (year, code, score) in zip(annual_lines[0][1:], [(2023,'907','318'),(2024,'907','311'),(2025,'891','292'),(2026,'891','307')], strict=True):
            self.assertEqual(row[0], str(year))
            self.assertIn(code + '计算机基础与数字电路', row[1])
            self.assertIn('334独立行', row[1])
            self.assertEqual(row[2], score)
        self.assertNotIn('当年完整目录未恢复，不能借321或2027四科', swu)
        self.assertIn('不能据目录认定每个录取者原试卷', swu)

    def test_cuc_initial_and_material_review_thresholds_remain_separate(self):
        # TraceId: 08b14bba-791f-4838-89fc-df06a775482c
        panel = next(p['source'] for p in make_panels(self.source) if p['key'] == 'school-048')
        parser = ReaderParser()
        parser.feed('<main>' + MarkdownIt('commonmark', {'html': True}).enable('table').render(panel) + '</main>')
        tables = [table for table in parser.tables if '进入复试的综合成绩门槛' in table[0]]
        self.assertEqual(len(tables), 1)
        for row, direction, threshold, recommended in zip(tables[0][1:], ['02', '03'], ['54.9', '57.1'], ['6', '2'], strict=True):
            self.assertIn('2026：085411/' + direction, row[0])
            self.assertIn('204英语（二）', row[1])
            self.assertIn('302数学（二）', row[1])
            self.assertIn('408计算机学科专业基础', row[1])
            self.assertEqual(row[2:6], ['264', '各35', '各53', threshold])
            self.assertEqual(row[-1], recommended)
        self.assertIn('不能称普通净名额或扩招人数', panel)
        self.assertIn('没有学院、专业或方向列', panel)

    def test_original_numeric_rows_remain_tables_in_correct_sections(self):
        for group in self.manifest['quantitative_groups']:
            for row in group['numeric_rows']:
                with self.subTest(destination=group['destination'], row=row):
                    self.assertIn(tuple(row), self.parser.rows[group['destination']])

    def test_tables_preserve_columns_and_have_accessible_scroll_regions(self):
        self.assertGreaterEqual(len(self.parser.tables), 558)
        for table in self.parser.tables:
            for row in table:
                self.assertEqual(len(row), len(table[0]))
        self.assertEqual(self.page.count('aria-label="可横向滚动的数据表"'), len(self.parser.tables))
        self.assertIn('max-width:100%', (self.root / 'dist/reader.css').read_text(encoding='utf-8'))


class SchoolEntityBuildTests(unittest.TestCase):
    """TraceId: 4fa2880a-e3d3-40b3-a2d9-8c69ad9fd505"""

    def test_entity_hierarchy_keeps_research_text_tables_and_links_intact(self):
        source = '''<a id="school-069"></a>
### 北京理工大学
<p class="school-tier">院校层次：985</p>

<section class="school-college" data-college-key="207" data-college-title="207 计算机学院">

<section class="admission-project" data-project-key="207-085405" data-project-title="085405 软件工程" data-project-status="2027下半年改考408公告">

#### 软件工程：历年分数

| 年份 | 科目 | 分数 |
| --- | --- | --- |
| 2026 | 885 | 341 |

<section class="research-direction" data-direction-key="00" data-direction-title="00 不区分研究方向">

##### 不区分研究方向

<details>
<summary>软件工程</summary>

<a id="existing-evidence"></a>

[已有来源](https://example.com/source)和完整正文。

</details>

</section>

</section>

</section>

<section class="admission-notes" data-notes-title="共同口径与来源核验">

共同样本范围与来源界限。

</section>
'''
        page, _ = render(source)
        original = ReaderParser(); original.feed('<main>' + MarkdownIt('commonmark', {'html': True}).enable('table').render(source) + '</main>')
        generated = ReaderParser(); generated.feed(page)
        normalize = lambda parts: re.sub(r'\s+', ' ', ''.join(parts)).strip()
        self.assertEqual(normalize(generated.text), normalize(original.text))
        self.assertEqual(generated.tables, original.tables)
        self.assertEqual(generated.main_links, original.main_links)
        self.assertIn('id="project-school-069-207-085405" aria-label="085405 软件工程" hidden', page)
        self.assertIn('href="#direction-school-069-207-085405-00"', page)
        self.assertIn('id="college-school-069-207" aria-label="207 计算机学院" hidden', page)
        self.assertIn('data-projects-for="college-school-069-207" hidden', page)
        self.assertIn('data-directions-for="project-school-069-207-085405" hidden', page)
        self.assertNotIn('本校资料分类', page)
        self.assertIn('existing-evidence', generated.ids)

    def test_entities_require_distinct_project_keys_and_correct_parentage(self):
        direction = '<section class="research-direction" data-direction-key="00" data-direction-title="00 不区分研究方向">\n\n正文\n\n</section>\n'
        project = '<section class="admission-project" data-project-key="207-085404" data-project-title="085404 计算机技术">\n\n' + direction + '\n</section>\n'
        college = '<section class="school-college" data-college-key="207" data-college-title="计算机学院">\n\n' + project + '\n</section>\n'
        other = college.replace('207', '241').replace('计算机学院', '医学技术学院')
        self.assertEqual(prepare_admissions('原有学校正文', 'school-001'), '原有学校正文')
        generated = prepare_admissions(college + other, 'school-069')
        for key in ('207-085404', '241-085404'):
            self.assertIn(f'id="project-school-069-{key}"', generated)
            self.assertIn(f'id="direction-school-069-{key}-00"', generated)
        invalid = [college + college, college.replace('</section>', ''), project, direction,
                   college.replace(project, direction), college.replace(direction, direction + direction),
                   college.replace(project, project + project), college.replace('207-085404', 'bad/key'),
                   college + other.replace('241-085404', '207-085404')]
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(ValueError): prepare_admissions(source, 'school-069')
        with self.assertRaises(ValueError): prepare_admissions(college, 'chapter-1')

    def test_only_explicit_late_switch_project_status_gets_red_navigation(self):
        project = '<section class="school-college" data-college-key="207" data-college-title="计算机学院">\n\n<section class="admission-project" data-project-key="207-085405" data-project-title="软件工程" data-project-status="2027下半年改考408公告">\n\n正文\n\n</section>\n\n</section>'
        self.assertNotIn('class="project-link late-project"', prepare_admissions(project, 'school-069'))
        flag = '<p class="switch-flag" data-status="late-announcement" data-announced="2026-07-06" data-target-year="2027">软件工程改考公告</p>\n\n'
        result = prepare_admissions(flag + project, 'school-069')
        self.assertIn('class="project-link late-project"', result)
        self.assertIn('class="entity-card late-project"', result)
        self.assertNotIn('late-project', prepare_admissions(flag + project.replace('2027下半年改考408公告', '2026历史数一对照'), 'school-069'))


if __name__ == '__main__':
    unittest.main()
