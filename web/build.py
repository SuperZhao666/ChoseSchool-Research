"""Render the complete authoritative README into a static reading site.

TraceId: c8929f22-a836-4ff9-87db-e9ee2a86a402
This build never selects, summarizes, modifies, or drops research paragraphs.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = 'c8929f22-a836-4ff9-87db-e9ee2a86a402'


def make_panels(source: str) -> list[dict]:
    """Split only at document-level boundaries; preserve every source character."""
    boundaries = [(0, 'overview', '研究概览')]
    chapter = 0
    for match in re.finditer(r'(?m)^## ([^\n]+)$|^<a id="(school-\d+)"></a>', source):
        start = match.start()
        if match[2]:
            title = re.match(r'<a[^>]+></a>\s*\n\s*### ([^\n]+)', source[start:])[1]
            key = match[2]
        else:
            chapter += 1; key = f'chapter-{chapter}'; title = match[1]
            if title == '完整比较依据与历史证据':
                start = source.rfind('<a id="complete-evidence"></a>', 0, start)
                if start < 0: raise ValueError('缺少完整证据入口。')
        boundaries.append((start, key, title))
    panels = []
    for i, (start, key, title) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(source)
        body = source[start:end]
        if body.count('<details>') != body.count('</details>'):
            raise ValueError(f'阅读区边界切断了折叠资料：{key}')
        tier = re.search(r'<p class="school-tier">院校层次：(985|211（非985）|双非)</p>', body) if key.startswith('school-') else None
        if key.startswith('school-') and not tier:
            raise ValueError('请先明确标注每所学校的院校层次。')
        late = re.search(r'<p class="switch-flag" data-status="late-announcement" data-announced="([0-9-]+)" data-target-year="(\d{4})">', body)
        if late:
            announced = date.fromisoformat(late[1]); target = int(late[2])
            if not date(target - 1, 7, 1) <= announced <= date(target - 1, 12, 31):
                raise ValueError(f'下半年改考标记日期不符：{key}')
        panels.append({'key': key, 'title': title, 'source': body,
                       'tier': tier[1] if tier else None, 'late': bool(late)})
    if ''.join(panel['source'] for panel in panels) != source:
        raise ValueError('阅读区切分未完整保留正文。')
    return panels


def render(source: str) -> tuple[str, dict]:
    panels = make_panels(source)
    default_panel = next(panel['key'] for panel in panels if panel['tier'])
    wrapped = []
    for panel in panels:
        key = panel['key']; hidden = '' if key == default_panel else ' hidden'
        wrapped.append(f'<section id="panel-{key}" class="reader-panel" data-panel="{key}" data-title="{html.escape(panel["title"], quote=True)}"{hidden}>\n\n{panel["source"]}\n\n</section>\n\n')
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    tokens = md.parse(''.join(wrapped))
    used = set(re.findall(r'<a id="([^"]+)"', source)) | {f'panel-{panel["key"]}' for panel in panels}
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
    schools = [panel for panel in panels if panel['tier']]
    if not schools or not body.count('<table>'):
        raise ValueError('完整正文或学校导航未生成，构建已停止。')
    source_sha = hashlib.sha256(source.encode('utf-8')).hexdigest()
    navigation = []
    for school in schools:
        key = school['key']; late_class = ' late-switch' if school['late'] else ''
        current = ' aria-current="page"' if key == default_panel else ''
        badge = '<span class="late-badge">下半年改408公告</span>' if school['late'] else ''
        navigation.append(f'<a href="#{key}" class="school-link{late_class}" data-panel-target="{key}"{current}><span class="school-name">{html.escape(school["title"])}</span><span class="school-meta">{school["tier"]}</span>{badge}</a>')
    resources = ''.join(f'<a href="#panel-{panel["key"]}" data-panel-target="{panel["key"]}">{html.escape(panel["title"])}</a>' for panel in panels if not panel['tier'])
    template = (ROOT / 'web/template.html').read_text(encoding='utf-8')
    result = template.replace('{{SOURCE_SHA}}', source_sha).replace('{{SCHOOL_NAVIGATION}}', ''.join(navigation)).replace('{{RESOURCE_NAVIGATION}}', resources).replace('{{SCHOOL_COUNT}}', str(len(schools))).replace('{{CONTENT}}', body).replace('{{DEFAULT_TITLE}}', html.escape(schools[0]['title']))
    metadata = {'trace_id': TRACE_ID, 'source': 'README.md', 'source_sha256': source_sha,
                'source_encoding': 'UTF-8, LF-normalized',
                'school_count': len(schools), 'panel_count': len(panels),
                'late_switch_school_count': sum(school['late'] for school in schools),
                'table_count': body.count('<table>'),
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
