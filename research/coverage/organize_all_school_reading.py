"""One-time, insertion-only migration of the sole public research pool.

TraceId: 8d98f22a-7a30-4d09-b60c-59c407ea8b93
Run as python -m research.coverage.organize_all_school_reading.
"""
from pathlib import Path
import hashlib
import html
import json
import re

from web.build import make_panels
from research.coverage.all_school_reading_catalog import CATALOG, GAPS, DIRECTIONS, LATE_PROJECTS

ROOT = Path(__file__).resolve().parents[2]
TRACE = '8d98f22a-7a30-4d09-b60c-59c407ea8b93'


def project_source(school, college, project):
    esc = lambda value: html.escape(value, quote=True)
    status = '下半年改考408公告 · 完整条件见正文' if project['key'] in LATE_PROJECTS.get(school, set()) else '已有资料整理 · 年度条件见结论'
    terms = esc(json.dumps(project['terms'], ensure_ascii=False))
    title = esc(project['title'])
    directions = ''.join(
        f'\n<section class="research-direction" data-direction-key="{key}" data-direction-title="{esc(name)}">\n\n'
        f'###### {name}\n\n本项目下的研究或培养方向；是否分组排名、名额与科目，以同年原资料中该方向为准。\n\n</section>\n'
        for key, name in DIRECTIONS.get((school, project['key']), []))
    return (f'\n<section class="admission-project" data-project-key="{project["key"]}" data-project-title="{title}" data-project-status="{status}">\n\n'
            f'##### {project["title"]}\n\n<div class="project-verdict">\n\n{project["brief"]}\n\n</div>\n\n'
            f'<div class="project-source-selector" data-reader-ui="true" data-project-terms="{terms}"></div>\n'
            f'{directions}\n</section>\n')


def native_colleges(source):
    stack, result = [], {}
    for tag in re.finditer(r'(?m)^</?section\b[^>]*>[ \t]*$', source):
        if tag[0].startswith('</'):
            opening = stack.pop()
            if 'class="school-college"' in opening[0]:
                key = re.search(r'data-college-key="([^"]+)"', opening[0])[1]
                result[key] = tag.start()
        else:
            stack.append(tag)
    return result


def main():
    path = ROOT / 'README.md'
    source = path.read_text(encoding='utf-8')
    if f'全库项目阅读 TraceId: {TRACE}' in source:
        raise SystemExit('Migration already applied; edit the authoritative README in place.')
    panels = make_panels(source)
    schools = [p for p in panels if p['tier']]
    assert {p['key'][7:] for p in schools} == set(CATALOG) | set(GAPS)
    insertions, audit, offset = [], [], 0
    for panel in panels:
        body, key = panel['source'], panel['key'][7:]
        if not panel['tier']:
            offset += len(body); continue
        header_end = list(re.finditer(r'(?m)^<p class="(?:school-tier|switch-flag|switch-note)"[^\n]*</p>', body))[-1].end()
        existing = native_colleges(body)
        notes_match = re.search(r'(?m)^<section class="admission-notes"', body)
        notes_at = notes_match.start() if notes_match else header_end
        definitions = CATALOG.get(key, [])
        new_projects = sum(len(c['projects']) for c in definitions)
        marker = f'\n\n<!-- 全库项目阅读 TraceId: {TRACE} -->\n'
        intro = ''
        if key in GAPS:
            intro = f'\n<div class="school-reading-status">\n\n**当前查到哪里**\n\n{GAPS[key]}\n\n</div>\n'
        else:
            intro = '\n<p class="school-reading-hint">先选学院下的具体项目，再分别看科目、历年分数、复试和培养。历史项目与待核线索已在名称和结论中注明。</p>\n'
        insertions.append((offset + header_end, marker + intro))
        colleges_added = []
        for college in definitions:
            project_text = ''.join(project_source(key, college, p) for p in college['projects'])
            if college['key'] in existing:
                insertions.append((offset + existing[college['key']], project_text))
            else:
                title = html.escape(college['title'], quote=True)
                colleges_added.append(f'\n<section class="school-college" data-college-key="{college["key"]}" data-college-title="{title}">\n\n#### {college["title"]}\n{project_text}\n</section>\n')
        if existing:
            assert notes_match, panel['key']
            insertions.append((offset + notes_at, '\n'.join(colleges_added) + '\n'))
        else:
            # All original paragraphs, rows and their order survive inside the bank.
            insertions.append((offset + header_end, '\n'.join(colleges_added) + '\n\n<section class="admission-notes" data-notes-title="本校完整原文与共同说明">\n\n'))
            insertions.append((offset + len(body), '\n</section>\n\n'))
        audit.append(dict(school=panel['key'], title=panel['title'], old_projects=len(re.findall(r'class="admission-project"', body)),
                          added_projects=new_projects, reading_state='evidence_gap' if key in GAPS else 'project_tree',
                          old_source_sha256=hashlib.sha256(body.encode()).hexdigest(), old_tables=body.count('\n|---')))
        offset += len(body)
    # Stable sort places the short status before the new layout at a shared offset.
    insertions.sort(key=lambda item: item[0])
    pieces, original_parts, cursor = [], [], 0
    for position, addition in insertions:
        pieces.extend([source[cursor:position], addition]); original_parts.append(source[cursor:position]); cursor = position
    pieces.append(source[cursor:]); original_parts.append(source[cursor:])
    assert ''.join(original_parts) == source, 'Original source changed'
    result = ''.join(pieces)
    new_panels = make_panels(result)
    assert len([p for p in new_panels if p['tier']]) == 104
    report = dict(trace_id=TRACE, source='README.md', source_preservation='insertion-only; every original character retained in order',
                  before_sha256=hashlib.sha256(source.encode()).hexdigest(), after_sha256=hashlib.sha256(result.encode()).hexdigest(), schools=audit)
    path.write_bytes(result.encode('utf-8'))
    (ROOT / 'research/coverage/all-school-reading-ownership.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(schools=len(audit), projects=sum(a['old_projects']+a['added_projects'] for a in audit), gaps=len(GAPS), trace_id=TRACE)))


if __name__ == '__main__':
    main()
