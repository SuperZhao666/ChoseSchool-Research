"""One-time, source-preserving reading migration. Not a public research report.

TraceId: 620a4022-cd30-48ab-992b-4a26e0cff841
Only explicitly named project dossiers are assigned; shared evidence stays shared.
"""
from pathlib import Path
import re
import json
import hashlib
from web.build import make_panels

ROOT = Path(__file__).resolve().parents[2]
BRIEFS = {
    ('005', '308', '085405'): '2026年已考英语二、数学二、408。普通一志愿清洗人口136人，中位321.5；2027正式目录与普通名额仍待核。乌鲁木齐、三年学费1.74万元，先确认地域与培养安排。',
    ('007', '048', '085410'): '2026年改为英语二、数学二、408，考试招生19人、中位340。2024—2025考840，旧年分数不能直接比较；名额较小，2027目录和普通份额仍待核。',
    ('012', '010', '085405'): '2026年英语二、数学二、408，备注空白全日制人口87人、中位363；该人口与另列的4名士兵分开。北京两年学费4万元，普通专硕不安排住宿；2027条件待核。',
    ('013', '018', '085405'): '2026年英语二、数学二、408。一志愿、全日制、非定向22人，中位344.5；原表无专项分类，不能把22人全叫普通统考。初试占70%，三年学费4.5万元；2027目录与名额待核。',
    ('014', '084', '085410'): '2026年英语二、数学二、408。全日制、非定向、专项栏为“无”的最终人口86人，中位368。初复试各50%，三年学费2.4万元；不同培养路径及2027普通名额需要分别核对。',
    ('030', '014', '085404'): '2026年学院普通复试线355。最终名单中无显式国家专项的115人，中位387，但仍可能包含校内专项，不能称纯普通本部人口。2027完整条件继续以同年正式目录为准。',
    ('031', '131', '085404'): '2026年英语二、数学二、408，复试总分线321。普通拟录取43人、中位374，其中含嘉庚联培2人；核心校内人口另列，不能混用。2027目录与普通份额待核。',
    ('032', '047', '085404'): '2026年英语二、数学二、408，复试线353。核心备注空白人口44人，中位386；另有委培、联培，计划45与最终总人数47属于不同口径。2027条件待核。',
    ('033', '002', '085404-01'): '这里仅看全日制01方向。2026年复试线364，正式最终原件尚缺；29人、中位378来自公开镜像，属于旁证，不能当官方已核录取分布。其他方向和卓工同码项目另看。',
    ('034', '005', '085404'): '2026年英语二、数学二、408，复试线358。校方扣推免阶段计划41，正式逐行最终数据仍缺；二手平均379不是官方录取结论，也没有可用的正式中位数。',
    ('035', '018', '085405'): '2026年英语二、数学二、408，复试线346。全国统考、全日制、非定向人口10人，中位376.5；容量小，有普通编程机试。2027目录与普通名额待核。',
}
NAMES = {'085404': '计算机技术', '085405': '软件工程', '085410': '人工智能', '085400': '电子信息'}

def outer_details(source):
    result, start, depth = [], None, 0
    for match in re.finditer(r'</?details>', source):
        if match[0] == '<details>':
            if depth == 0: start = match.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                end = match.end()
                text = source[start:end]
                title = re.search(r'<summary>(.*?)</summary>', text, re.S)[1]
                result.append({'start': start, 'end': end, 'title': title, 'text': text})
    assert depth == 0
    return result

def migrate(source):
    panels, audit = make_panels(source), []
    for panel in panels:
        body = panel['source']
        if not panel['tier'] or 'class="school-college"' in body: continue
        folds = outer_details(body)
        projects = []
        for fold in folds:
            match = re.match(r'历年科目、录取人口与全部成绩分布：\d+\. .+? (\d{3}) (.+?) `([^`]+)`(.*)', fold['title'])
            if not match: continue
            college, college_name, code, qualification = match.groups()
            name = NAMES.get(code[:6], code)
            title = f'{code[:6]} {name}'
            if '-' in code: title += f' · {code.split("-", 1)[1]}方向（历史范围）'
            if qualification.strip(): title += qualification.strip()
            projects.append({'college':college,'college_name':college_name,'key':f'{college}-{code.lower()}',
                             'code':code,'title':title,'folds':[fold]})
        if not projects: continue
        owned = {id(p['folds'][0]) for p in projects}
        for project in projects:
            # Only an unambiguous project-specific training dossier is assigned.
            suffix = project['college'] + NAMES.get(project['code'][:6], '')[:2]
            for fold in folds:
                target = fold['title'].split('｜')[-1]
                if id(fold) not in owned and target.startswith(suffix) and not re.search(r'与|／|等|其他|之外', target):
                    project['folds'].append(fold); owned.add(id(fold))
        # Explicit extra project dossiers, already named in source (not inferred).
        extras = {
            'school-013': [('018','信息学部','085410','人工智能','018—085410人工智能')],
            'school-014': [('084','计算机与人工智能学院、软件学院','085404','计算机技术','084—085404计算机技术')],
            'school-031': [('software','信息学院软件工程系','085405','软件工程','软件工程系085405')],
        }
        for college,college_name,code,name,marker in extras.get(panel['key'], []):
            matched = [f for f in folds if id(f) not in owned and marker in f['title']]
            if matched:
                projects.append({'college':college,'college_name':college_name,'key':f'{college}-{code}',
                                 'code':code,'title':f'{code} {name}','folds':matched})
                owned.update(map(id, matched))
        # Preserve unassigned narrative and original fold blocks in their original order.
        remainder = body
        for fold in reversed(folds):
            if id(fold) in owned: remainder = remainder[:fold['start']] + remainder[fold['end']:]
        # Source intro remains a school-level account; never copied to every project.
        first_source_fold = body.find('<details>')
        intro = body[:first_source_fold]
        rest = remainder[len(intro):]
        sections = []
        colleges = list(dict.fromkeys(p['college'] for p in projects))
        for college in colleges:
            group = [p for p in projects if p['college']==college]
            sections.append(f'<section class="school-college" data-college-key="{college}" data-college-title="{college} {group[0]["college_name"]}">\n\n#### {college} {group[0]["college_name"]}\n')
            for p in group:
                sections.append(f'<section class="admission-project" data-project-key="{p["key"]}" data-project-title="{p["title"]}" data-project-status="已查历史项目 · 2027条件见项目说明">\n\n##### {p["title"]}\n')
                brief = BRIEFS.get((panel['key'][-3:],college,p['code']))
                if brief:
                    sections.append(f'<div class="project-verdict">\n\n**先看结论**\n\n{brief}\n\n</div>\n')
                for fold in p['folds']:
                    sections.append(fold['text'])
                sections.append('</section>\n')
            sections.append('</section>\n')
        sections.append('<section class="admission-notes" data-notes-title="其他项目、学院共同规则与完整取证">\n\n#### 其他项目、学院共同规则与完整取证\n\n'+rest+'\n\n</section>\n')
        panel['source'] = intro+'\n<!-- 项目阅读归属 TraceId: 620a4022-cd30-48ab-992b-4a26e0cff841 -->\n\n'+'\n\n'.join(sections)
        for fold in folds:
            assert panel['source'].count(fold['text'])==1, fold['title']
        audit.append({'school':panel['key'],'title':panel['title'],'original_sha256':hashlib.sha256(body.encode()).hexdigest(),
                      'projects':[{'key':p['key'],'title':p['title'],'assigned_source_dossiers':[f['title'] for f in p['folds']]} for p in projects],
                      'all_original_dossiers_retained_once':True})
    return ''.join(p['source'] for p in panels), audit

if __name__ == '__main__':
    path=ROOT/'README.md'
    source,audit=migrate(path.read_text(encoding='utf-8'))
    if not audit:
        raise SystemExit('No unmigrated project dossiers; existing source and audit were not changed.')
    path.write_text(source,encoding='utf-8')
    report={'trace_id':'620a4022-cd30-48ab-992b-4a26e0cff841','purpose':'Project ownership and conclusion-first reading; no new catalog verification','schools':audit}
    (ROOT/'research/coverage/2026-09-17-project-reading-ownership.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'schools':len(audit),'projects':sum(len(s['projects']) for s in audit)}))
