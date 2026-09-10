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
from web.build import make_panels, render
from tests.unit.test_unified_research_fidelity import numeric_signature


class ReaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []; self.links = []; self.rows = defaultdict(set)
        self.section = None; self.cells = None; self.cell = None
        self.tables = []; self.table = None; self.main = False; self.text = []
        self.main_links = []; self.panels = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
            if re.fullmatch(r'(school|evidence)-\d+|complete-evidence', attrs['id']):
                self.section = attrs['id']
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
            if self.main: self.main_links.append(attrs['href'])
        if tag == 'section' and attrs.get('class') == 'reader-panel':
            self.panels.append(attrs)
        if tag == 'main': self.main = True
        if tag == 'table': self.table = []
        if tag == 'tr': self.cells = []
        if tag in ('td', 'th'): self.cell = []

    def handle_data(self, data):
        if self.main: self.text.append(data)
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'main': self.main = False
        if tag in ('td', 'th') and self.cell is not None:
            self.cells.append(''.join(self.cell)); self.cell = None
        if tag == 'tr' and self.cells is not None:
            self.rows[self.section].add(numeric_signature(' | '.join(self.cells)))
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


if __name__ == '__main__':
    unittest.main()
