"""Render the complete authoritative README into a static reading site.

TraceId: 4633df94-71b7-4339-ae57-1ad2dd0576cb
This build never selects, summarizes, modifies, or drops research paragraphs.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = '4633df94-71b7-4339-ae57-1ad2dd0576cb'
ENTITY_TRACE_ID = '4fa2880a-e3d3-40b3-a2d9-8c69ad9fd505'
ENTITY_CLASSES = {'school-college': 'college', 'admission-project': 'project',
                  'research-direction': 'direction', 'admission-notes': 'notes'}


class _SectionAttributes(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)


def prepare_admissions(source: str, panel_key: str) -> str:
    """Derive a college → project → direction tree from explicit source entities.

    TraceId: 4fa2880a-e3d3-40b3-a2d9-8c69ad9fd505
    Body text is never moved or summarized. Entity keys identify reading routes,
    not catalog confirmation; the same program code in two colleges stays apart.
    """
    if not any(f'class="{name}"' in source for name in ENTITY_CLASSES):
        return source
    if not panel_key.startswith('school-'):
        raise ValueError(f'招生实体只能属于学校：{panel_key}')
    tags = list(re.finditer(r'(?m)^</?section\b[^>]*>[ \t]*$', source))
    if len(tags) != len(re.findall(r'</?section\b', source)):
        raise ValueError(f'招生实体标记必须独占一行：{panel_key}')
    stack, colleges, nodes, all_keys = [], [], [], set()
    notes = None
    for tag in tags:
        if tag[0].startswith('</section'):
            if not stack:
                raise ValueError(f'招生实体闭合标记无对应实体：{panel_key}')
            stack.pop()['end'] = tag.end()
            continue
        parser = _SectionAttributes(); parser.feed(tag[0]); attrs = parser.attrs
        kind = ENTITY_CLASSES.get(attrs.get('class'))
        if kind is None:
            raise ValueError(f'招生实体内存在未知 section：{panel_key}')
        parent = stack[-1] if stack else None
        expected = {'college': None, 'project': 'college', 'direction': 'project', 'notes': None}[kind]
        if (parent['kind'] if parent else None) != expected:
            raise ValueError(f'招生实体层级必须是学院→项目→方向：{panel_key}')
        title = attrs.get(f'data-{kind}-title', '')
        key = attrs.get(f'data-{kind}-key', 'notes' if kind == 'notes' else '')
        if not title or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9-]*', key):
            raise ValueError(f'招生实体标题或键无效：{panel_key}')
        qualified_key = (kind, parent['key'] if kind == 'direction' else '', key)
        if qualified_key in all_keys:
            raise ValueError(f'招生实体键重复：{panel_key}/{key}')
        all_keys.add(qualified_key)
        suffix = f'{parent["key"]}-{key}' if kind == 'direction' else key
        identifier = f'{kind}-{panel_key}' + (f'-{suffix}' if kind != 'notes' else '')
        node = {'kind': kind, 'key': key, 'title': title, 'id': identifier,
                'status': attrs.get('data-project-status', ''), 'start': tag.start(),
                'tag_end': tag.end(), 'tag': tag[0].rstrip(), 'children': []}
        if parent: parent['children'].append(node)
        elif kind == 'college': colleges.append(node)
        else: notes = node
        nodes.append(node); stack.append(node)
    if stack or (not colleges and not notes) or any(not college['children'] for college in colleges):
        raise ValueError(f'招生实体未闭合或学院没有招生项目：{panel_key}')

    def link(node, css=''):
        title = html.escape(node['title'])
        if node['kind'] == 'project' and '改考408' in node['status'] and 'data-status="late-announcement"' in source:
            css += ' late-project'
        status = f'<small class="project-status">{html.escape(node["status"])}</small>' if node['status'] else ''
        return f'<a class="{css}" href="#{node["id"]}" data-entity-target="{node["id"]}"><span>{title}</span>{status}</a>'

    branches = []
    for college in colleges:
        projects = []
        for project in college['children']:
            directions = ''.join(f'<li>{link(direction, "direction-link")}</li>' for direction in project['children'])
            project_tree = f'<ul class="direction-tree" data-directions-for="{project["id"]}" hidden>{directions}</ul>' if directions else ''
            projects.append(f'<li>{link(project, "project-link")}{project_tree}</li>')
        branches.append(f'<li>{link(college, "college-link")}<ul class="project-tree" data-projects-for="{college["id"]}" hidden>{"".join(projects)}</ul></li>')
    home_id = f'admissions-{panel_key}'
    navigation = (f'<div class="admission-layout" id="{home_id}">\n\n'
                  '<nav class="admission-navigation" data-reader-ui="true" aria-label="学院、招生项目与研究方向">'
                  f'<a class="admissions-home-link" href="#{home_id}" data-entity-home="true">本校招生结构</a>'
                  '<p class="entity-tree-caption">学院 → 招生项目 → 研究方向</p>'
                  f'<ul class="college-tree">{"".join(branches)}</ul>'
                  + (link(notes, 'admissions-notes-link') if notes else '') + '</nav>\n\n'
                  '<div class="admission-detail">\n\n'
                  '<nav class="admission-breadcrumb" data-reader-ui="true" aria-label="当前招生项目位置">本校招生结构</nav>\n\n'
                  '<nav class="admission-home" data-reader-ui="true" aria-label="选择招生学院与项目">'
                  + ('<h4>选择招生项目</h4>' if colleges else '<h4>待核学校资料</h4><p>尚未恢复可单独列出的招生项目。下方保留已经查到的原文与证据缺口。</p>')
                  + ''.join('<div class="college-choice"><h5>' + link(college, 'college-choice-title')
                            + '</h5><div class="entity-cards">' + ''.join(link(project, 'entity-card') for project in college['children'])
                            + '</div></div>' for college in colleges)
                  + (link(notes, 'shared-reading-link') if notes else '') + '</nav>\n\n')
    edits = []
    for node in nodes:
        hidden = ' hidden' if node['kind'] in ('college', 'project', 'notes') else ''
        enhanced = node['tag'][:-1] + f' id="{node["id"]}" aria-label="{html.escape(node["title"], quote=True)}"{hidden}>'
        if node['kind'] == 'college':
            enhanced += ('\n\n<nav class="college-overview" data-reader-ui="true" aria-label="本学院招生项目">'
                         f'<h4>{html.escape(node["title"])}</h4><p>选择具体项目，查看属于该项目的完整资料。</p>'
                         '<div class="entity-cards">' + ''.join(link(project, 'entity-card') for project in node['children']) + '</div></nav>')
        edits.append((node['start'], node['tag_end'], enhanced))
    edits.append((nodes[0]['start'], nodes[0]['start'], navigation))
    last_end = max(node['end'] for node in nodes)
    edits.append((last_end, last_end, '\n\n</div>\n\n</div>'))
    # Apply right to left, enhancing the first marker before inserting navigation.
    for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        source = source[:start] + replacement + source[end:]
    return source


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
        panel_body = prepare_admissions(panel['source'], key)
        wrapped.append(f'<section id="panel-{key}" class="reader-panel" data-panel="{key}" data-title="{html.escape(panel["title"], quote=True)}"{hidden}>\n\n{panel_body}\n\n</section>\n\n')
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    tokens = md.parse(''.join(wrapped))
    # TraceId: d36580a9-e711-47ec-9786-53ec83803d21
    # Keep long exam notes legible without changing any source cell or its order.
    # TraceId: c4d5b28b-0b67-4d2f-89e1-b46eb1090822
    # Labels are derived from the same table, never a second copy of its values.
    # TraceId: 12977bfb-1cef-4a83-b35a-0c58141c1a37
    # All school tables get original column labels. Wide/narrative tables use
    # records immediately; compact tables can use them in a narrow container.
    table_start = None
    headers = []
    column = 0
    record_sections = []
    record_table = False
    for i, token in enumerate(tokens):
        if token.type == 'html_block':
            for match in re.finditer(r'</?section\b[^>]*>', token.content):
                if match[0].startswith('</'):
                    if record_sections: record_sections.pop()
                else:
                    attrs = _SectionAttributes(); attrs.feed(match[0])
                    record_sections.append(attrs.attrs.get('data-reading-layout') == 'records'
                                           or attrs.attrs.get('data-panel', '').startswith('school-')
                                           or bool(record_sections and record_sections[-1]))
        elif token.type == 'table_open':
            table_start = i
            headers = []
            record_table = bool(record_sections and record_sections[-1])
        elif token.type == 'thead_close' and table_start is not None:
            headers = [''.join(child.content for child in (item.children or [])
                               if child.type in ('text', 'code_inline'))
                       for item in tokens[table_start:i] if item.type == 'inline']
            if len(headers) > 1 and headers[1] == '当年初试科目与证据':
                tokens[table_start].attrSet('class', 'exam-subjects')
            if record_table:
                tokens[table_start].attrJoin('class', 'readable-table')
                if len(headers) >= 5:
                    tokens[table_start].attrJoin('class', 'record-table')
                if sum(bool(re.search(r'最低|中位|均值|均分|平均|最高|P25|P75|复试.*线|总分线', h)) for h in headers) >= 3:
                    tokens[table_start].attrJoin('class', 'score-summary-table')
                if headers == ['招生年度', '当年初试科目与证据', '当年学院与统计方向',
                               '普通录取人数', '复试总分线', '录取最低分', '录取中位数',
                               '录取平均分', '录取最高分']:
                    tokens[table_start].attrJoin('class', 'score-record-table')
        elif token.type == 'tr_open':
            column = 0
        elif token.type == 'th_open' and record_table:
            token.attrSet('scope', 'col')
        elif token.type == 'td_open' and record_table:
            if column >= len(headers):
                raise ValueError('表格数据列多于表头，不能生成年度阅读标签。')
            token.attrSet('data-label', headers[column])
            cell = tokens[i + 1]
            text = ''.join(child.content for child in (cell.children or [])
                           if child.type in ('text', 'code_inline'))
            if len(text) > 80 or re.search(r'初试科目|当年.*科目', headers[column]):
                token.attrJoin('class', 'long-field')
            if len(text) <= 40 and re.search(r'最低|中位|均值|均分|平均|最高|P25|P75|复试.*线|总分线|人数|名单|拟录取', headers[column]):
                token.attrJoin('class', 'metric-field')
            if len(text) > 140 and 'record-table' not in (tokens[table_start].attrGet('class') or '').split():
                tokens[table_start].attrJoin('class', 'record-table')
            column += 1
        elif token.type == 'table_close': table_start = None
    used = set(re.findall(r'\bid="([^"]+)"', ''.join(wrapped)))
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
    body = re.sub(r'(<table(?:\s[^>]*)?>.*?</table>)', r'<div class="table-scroll" tabindex="0" role="region" aria-label="可横向滚动的数据表">\1</div>', body, flags=re.S)
    schools = [panel for panel in panels if panel['tier']]
    if not schools or not body.count('<table'):
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
                'table_count': body.count('<table'),
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
