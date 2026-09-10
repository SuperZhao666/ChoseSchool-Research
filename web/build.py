"""Render the complete authoritative README into a static reading site.

TraceId: a5a6f785-04be-4f85-8104-c604a2d186af
This build never selects, summarizes, modifies, or drops research paragraphs.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = 'a5a6f785-04be-4f85-8104-c604a2d186af'


def render(source: str) -> tuple[str, dict]:
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    tokens = md.parse(source)
    used = set(re.findall(r'<a id="([^"]+)"', source))
    for i, token in enumerate(tokens):
        if token.type != 'heading_open':
            continue
        children = tokens[i + 1].children or []
        title = ''.join(child.content for child in children if child.type in ('text', 'code_inline'))
        base = ''.join(c for c in title.lower() if c.isalnum() or c in '_- ').replace(' ', '-') or 'section'
        slug = base; number = 1
        while slug in used:
            slug = f'{base}-{number}'; number += 1
        used.add(slug); token.attrSet('id', slug)
    body = md.renderer.render(tokens, md.options, {})
    body = re.sub(r'(<table>.*?</table>)', r'<div class="table-scroll" tabindex="0" role="region" aria-label="可横向滚动的数据表">\1</div>', body, flags=re.S)
    schools = re.findall(r'<a id="(school-\d+)"></a>\s*\n\s*### ([^\n]+)', source)
    if not schools or not body.count('<table>'):
        raise ValueError('完整正文或学校导航未生成，构建已停止。')
    source_sha = hashlib.sha256(source.encode('utf-8')).hexdigest()
    options = ''.join(f'<option value="{html.escape(anchor, quote=True)}">{html.escape(name)}</option>' for anchor, name in schools)
    template = (ROOT / 'web/template.html').read_text(encoding='utf-8')
    result = template.replace('{{SOURCE_SHA}}', source_sha).replace('{{SCHOOL_OPTIONS}}', options).replace('{{SCHOOL_COUNT}}', str(len(schools))).replace('{{CONTENT}}', body)
    metadata = {'trace_id': TRACE_ID, 'source': 'README.md', 'source_sha256': source_sha,
                'source_encoding': 'UTF-8, LF-normalized',
                'school_count': len(schools), 'table_count': body.count('<table>'),
                'foldout_count': body.count('<details>'), 'source_bytes': len(source.encode('utf-8'))}
    return result, metadata


def build() -> dict:
    source = (ROOT / 'README.md').read_text(encoding='utf-8')
    page, metadata = render(source)
    output = ROOT / 'dist'; output.mkdir(exist_ok=True)
    files = {'index.html': page, 'README.md': source,
             'reader.css': (ROOT / 'web/reader.css').read_text(encoding='utf-8'),
             'reader.js': (ROOT / 'web/reader.js').read_text(encoding='utf-8'),
             'content-manifest.json': json.dumps(metadata, ensure_ascii=False, indent=2) + '\n'}
    for name, content in files.items():
        path = output / name; temporary = path.with_suffix(path.suffix + '.new')
        temporary.write_bytes(content.encode('utf-8')); temporary.replace(path)
    return metadata


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
