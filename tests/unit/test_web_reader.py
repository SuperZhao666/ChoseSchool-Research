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

from web.build import render
from tests.unit.test_unified_research_fidelity import numeric_signature


class ReaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []; self.links = []; self.rows = defaultdict(set)
        self.section = None; self.cells = None; self.cell = None
        self.tables = []; self.table = None; self.main = False; self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
            if re.fullmatch(r'(school|evidence)-\d+|complete-evidence', attrs['id']):
                self.section = attrs['id']
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
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
            self.assertIn(f'<option value="{value}">', self.page)
        self.assertEqual(self.page.count('<details>'), self.source.count('<details>'))

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
