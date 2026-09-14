/* TraceId: c8929f22-a836-4ff9-87db-e9ee2a86a402 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {parseHTML} = require('linkedom');
const path = require('node:path');

function reader(html, hash = '') {
  const {document, window} = parseHTML(html);
  // DOM-only integration: no browser process or network request is used.
  Object.defineProperty(window.HTMLElement.prototype, 'open', {
    get() { return this.hasAttribute('open'); },
    set(value) { value ? this.setAttribute('open', '') : this.removeAttribute('open'); },
    configurable: true
  });
  window.HTMLElement.prototype.scrollIntoView = function() { this.dataset.scrolled = 'true'; };
  const location = {hash};
  window.history = {replaceState: (_, __, value) => { location.hash = value; }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'reader.js'), 'utf8'), {
    document, window, location, NodeFilter: {SHOW_TEXT: 4}, requestAnimationFrame: fn => fn()
  });
  const click = id => document.getElementById(id).dispatchEvent(new window.Event('click', {bubbles: true, cancelable: true}));
  const search = value => {
    document.getElementById('search-input').value = value;
    document.getElementById('search-form').dispatchEvent(new window.Event('submit', {cancelable: true}));
  };
  const visible = () => [...document.querySelectorAll('.reader-panel')].filter(p => !p.hidden).map(p => p.dataset.panel);
  const go = value => { location.hash = value; window.dispatchEvent(new window.Event('hashchange')); };
  return {document, window, location, click, search, visible, go};
}

const fixture = `<html><body><header class="toolbar"></header><aside id="sidebar">
<a id="nav1" data-panel-target="school-001" href="#s1">学校一</a>
<a id="nav2" data-panel-target="school-002" href="#s">学校二</a></aside>
<button id="toggle-sidebar"></button><span id="current-page"></span>
<form id="search-form"><input id="search-input"></form><output id="search-status"></output>
<button id="previous-result"></button><button id="next-result"></button>
<button id="expand-all"></button><button id="collapse-all"></button>
<main id="research-content">
<section id="panel-school-001" class="reader-panel" data-panel="school-001" data-title="学校一"><a id="s1"></a>
<h3>AI与数据</h3><details id="first-fold"><summary>本校</summary><p>第一校完整资料</p></details>
<ul><li>父项独有文本<ul><li>子项</li></ul></li></ul></section>
<section id="panel-school-002" class="reader-panel" data-panel="school-002" data-title="学校二" hidden>
<details id="second-fold"><summary>历史</summary><details><summary>深层</summary><a id="s"></a><p>冷门人工智能 2026</p></details></details>
<table><tr><td>085410</td><td>41人</td></tr></table><p>末端 AI</p></section>
</main></body></html>`;

// TraceId: 4fa2880a-e3d3-40b3-a2d9-8c69ad9fd505
const entityFixture = fixture.replace('<h3>AI与数据</h3>', `<h3>AI与数据</h3>
<div class="admission-layout" id="admissions-school-001">
<nav class="admission-navigation" data-reader-ui="true">
<a id="home-link" href="#admissions-school-001" data-entity-home="true">本校招生结构</a>
<a id="college1-link" class="college-link" href="#college1" data-entity-target="college1">207 计算机学院</a>
<ul data-projects-for="college1" hidden><li><a id="project1-link" class="project-link" href="#project1" data-entity-target="project1">085404 计算机技术</a>
<ul data-directions-for="project1" hidden><li><a id="direction1-link" href="#direction1" data-entity-target="direction1">00 不区分研究方向</a></li></ul></li></ul>
<a id="college2-link" class="college-link" href="#college2" data-entity-target="college2">241 医学技术学院</a>
<ul data-projects-for="college2" hidden><li><a id="project2-link" class="project-link" href="#project2" data-entity-target="project2">085404 计算机技术</a>
<ul data-directions-for="project2" hidden><li><a id="direction2-link" href="#direction2" data-entity-target="direction2">00 不区分研究方向</a></li></ul></li></ul>
<a id="notes-link" href="#notes" data-entity-target="notes">共同说明入口仅界面文字</a></nav>
<div class="admission-detail"><nav class="admission-breadcrumb" data-reader-ui="true"></nav>
<nav class="admission-home" data-reader-ui="true"><h4>选择学院</h4></nav>
<section class="school-college" id="college1" data-college-key="207" data-college-title="207 计算机学院" hidden>
<nav class="college-overview" data-reader-ui="true"><h4>207 计算机学院</h4>本学院项目入口</nav>
<h4 id="college-source-heading">学院源标题独有检索文字</h4>
<section class="admission-project" id="project1" data-project-key="207-085404" data-project-title="085404 计算机技术" hidden>
<h4>计算机学院项目完整资料</h4><p>本项目共有科目、名额与历年分数</p>
<section class="research-direction" id="direction1" data-direction-key="00" data-direction-title="00 不区分研究方向"><h5>计算机方向说明</h5></section>`)
  .replace('<ul><li>父项独有文本<ul><li>子项</li></ul></li></ul>', `</section></section>
<section class="school-college" id="college2" data-college-key="241" data-college-title="241 医学技术学院" hidden>
<nav class="college-overview" data-reader-ui="true">本学院项目入口</nav>
<section class="admission-project" id="project2" data-project-key="241-085404" data-project-title="085404 计算机技术" hidden>
<h4>医学技术学院项目完整资料</h4><p>本医学项目2026考数学二408</p>
<section class="research-direction" id="direction2" data-direction-key="00" data-direction-title="00 不区分研究方向"><h5>医学方向说明</h5><p>共享项目名额，不能独立拆分</p>
<details id="score-fold"><summary>医学成绩</summary><a id="score-evidence"></a><p>年度2026，院线300</p></details></section></section></section>
<section class="admission-notes" id="notes" data-notes-title="共同口径与来源核验" hidden><details id="notes-fold"><summary>口径</summary><p>不属于具体招生实体的方法说明</p></details></section></div></div>`);

function visibleProjects(r) {
  return [...r.document.querySelectorAll('.admission-project')].filter(project => !project.hidden).map(project => project.dataset.projectKey);
}

function researchText(content) {
  const copy = content.cloneNode(true);
  copy.querySelectorAll('[data-reader-ui]').forEach(element => element.remove());
  return copy.textContent;
}

test('school landing → college → program → direction keeps shared project facts and separates identical codes', () => {
  const r = reader(entityFixture, '#s1');
  assert.deepEqual(visibleProjects(r), []);
  assert.equal(r.document.querySelector('.admission-home').hidden, false);
  assert.equal(r.document.getElementById('expand-all').disabled, true);
  r.click('college1-link');
  assert.equal(r.location.hash, '#college1');
  assert.equal(r.document.getElementById('college1').hidden, false);
  assert.equal(r.document.getElementById('college2').hidden, true);
  assert.deepEqual(visibleProjects(r), []);
  assert.equal(r.document.getElementById('college-source-heading').hidden, true);
  assert.equal(r.document.querySelector('#college1 .college-overview h4').hidden, false);
  assert.equal(r.document.querySelector('[data-projects-for="college1"]').hidden, false);
  r.click('project1-link');
  assert.deepEqual(visibleProjects(r), ['207-085404']);
  assert.equal(r.document.querySelector('#college1 .college-overview').hidden, true);
  assert.equal(r.document.getElementById('expand-all').textContent, '展开本项目资料');
  assert.equal(r.document.querySelector('.admission-breadcrumb').dataset.scrolled, 'true');
  r.click('direction1-link');
  assert.deepEqual(visibleProjects(r), ['207-085404']);
  assert.equal(r.document.getElementById('direction1').classList.contains('is-current-direction'), true);
  assert.equal(r.document.querySelector('.admission-breadcrumb').textContent, '学校一 / 207 计算机学院 / 085404 计算机技术 / 00 不区分研究方向');
  assert.equal(r.document.getElementById('project1').querySelector('p').hidden, false);
  r.click('college2-link'); r.click('project2-link');
  assert.deepEqual(visibleProjects(r), ['241-085404']);
  assert.equal(r.document.getElementById('college1').hidden, true);
  assert.equal(r.document.getElementById('project2-link').getAttribute('aria-current'), 'location');
  r.click('home-link');
  assert.deepEqual(visibleProjects(r), []);
  assert.equal(r.document.querySelector('.admission-home').hidden, false);
});

test('full-text search, old anchors and shared direction links open the owning college and program', () => {
  const r = reader(entityFixture);
  r.search('院线300');
  assert.deepEqual(visibleProjects(r), ['241-085404']);
  assert.equal(r.document.getElementById('score-fold').open, true);
  assert.equal(r.document.querySelector('mark').textContent, '院线300');
  assert.equal(r.location.hash, '#direction2');
  assert.equal(r.document.querySelector('[data-directions-for="project2"]').hidden, false);
  r.click('project1-link'); r.go('#score-evidence');
  assert.deepEqual(visibleProjects(r), ['241-085404']);
  assert.equal(r.document.getElementById('direction2').classList.contains('is-current-direction'), true);
  const direct = reader(entityFixture, '#direction2');
  assert.deepEqual(visibleProjects(direct), ['241-085404']);
  assert.equal(direct.document.getElementById('college2').hidden, false);
  r.search('共同说明入口仅界面文字');
  assert.equal(r.document.getElementById('search-status').textContent, '没有找到匹配内容');
  r.search('学院源标题独有检索文字');
  assert.equal(r.document.getElementById('college-source-heading').hidden, false);
  assert.equal(r.document.querySelector('#college1 .college-overview h4').hidden, true);
  assert.equal(r.document.querySelector('#college1 .college-overview').hidden, false);
  assert.equal(r.document.getElementById('college1').hidden, false);
  assert.deepEqual(visibleProjects(r), []);
  r.click('home-link'); r.go('#college-source-heading');
  assert.equal(r.document.getElementById('college-source-heading').hidden, false);
  r.search('具体招生实体的方法说明');
  assert.deepEqual(visibleProjects(r), []);
  assert.equal(r.document.getElementById('notes').hidden, false);
});

test('fold controls and printing affect only the selected project and restore fold state', () => {
  const r = reader(entityFixture, '#project1');
  r.click('expand-all');
  assert.equal(r.document.getElementById('first-fold').open, true);
  assert.equal(r.document.getElementById('score-fold').open, false);
  r.click('project2-link'); r.click('collapse-all');
  assert.equal(r.document.getElementById('first-fold').open, true);
  r.window.dispatchEvent(new r.window.Event('beforeprint'));
  assert.deepEqual(visibleProjects(r), ['241-085404']);
  assert.deepEqual(r.visible(), ['school-001']);
  assert.equal(r.document.getElementById('score-fold').open, true);
  assert.equal(r.document.getElementById('notes-fold').open, false);
  assert.equal(r.document.getElementById('second-fold').open, false);
  r.window.dispatchEvent(new r.window.Event('afterprint'));
  assert.deepEqual(visibleProjects(r), ['241-085404']);
  assert.equal(r.document.getElementById('first-fold').open, true);
  assert.equal(r.document.getElementById('score-fold').open, false);
  assert.equal(r.document.querySelectorAll('[data-print-open]').length, 0);
  r.click('nav2'); assert.equal(r.document.getElementById('expand-all').textContent, '展开本页全部资料');
  r.click('nav1'); assert.deepEqual(visibleProjects(r), []);
});

test('sidebar selects exactly one school; hash back and empty hash restore prior/default panel', () => {
  const r = reader(fixture);
  assert.deepEqual(r.visible(), ['school-001']);
  r.click('nav2'); assert.deepEqual(r.visible(), ['school-002']);
  assert.equal(r.document.getElementById('current-page').textContent, '学校二');
  assert.equal(r.document.getElementById('nav2').getAttribute('aria-current'), 'page');
  assert.equal(r.document.getElementById('nav1').hasAttribute('aria-current'), false);
  assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  r.go('#s1'); assert.deepEqual(r.visible(), ['school-001']);
  r.go('#s'); r.go(''); assert.deepEqual(r.visible(), ['school-001']);
});

test('search reaches hidden school, nested folds, parent list text and table codes', () => {
  const r = reader(fixture); r.search('人工智能');
  assert.equal(r.document.getElementById('search-status').textContent, '1 / 1 处');
  assert.deepEqual(r.visible(), ['school-002']);
  assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  assert.equal(r.document.querySelector('mark').textContent, '人工智能');
  for (const [query, school] of [['父项独有文本', 'school-001'], ['085410', 'school-002'], ['末端 AI', 'school-002']]) {
    r.search(query); assert.equal(r.document.getElementById('search-status').textContent, '1 / 1 处', query);
    assert.deepEqual(r.visible(), [school]);
  }
});

test('next/previous cross panels; empty/missing queries do not reveal all schools', () => {
  const r = reader(fixture); r.search('ai');
  assert.equal(r.document.getElementById('search-status').textContent, '1 / 2 处');
  assert.deepEqual(r.visible(), ['school-001']);
  r.click('next-result'); assert.deepEqual(r.visible(), ['school-002']);
  r.click('next-result'); assert.deepEqual(r.visible(), ['school-001']);
  r.click('previous-result'); assert.deepEqual(r.visible(), ['school-002']);
  assert.equal(r.document.getElementById('search-status').textContent, '2 / 2 处');
  r.search('<img onerror=alert(1)>');
  assert.equal(r.document.querySelectorAll('img').length, 0);
  assert.equal(r.document.getElementById('search-status').textContent, '没有找到匹配内容');
  r.search(''); assert.equal(r.document.querySelectorAll('mark').length, 0);
  assert.deepEqual(r.visible(), ['school-002']);
});

test('direct/same hash opens ancestors; expand/collapse and print affect current school only', () => {
  const r = reader(fixture, '#s');
  assert.deepEqual(r.visible(), ['school-002']);
  r.click('collapse-all'); assert.equal(r.document.querySelectorAll('details[open]').length, 0);
  r.click('nav2'); assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  r.click('nav1'); r.click('expand-all');
  assert.equal(r.document.querySelectorAll('details[open]').length, 3);
  r.click('collapse-all'); assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  r.window.dispatchEvent(new r.window.Event('beforeprint'));
  assert.equal(r.document.querySelectorAll('details[data-print-open]').length, 1);
  assert.equal(r.document.getElementById('first-fold').open, true);
  r.window.dispatchEvent(new r.window.Event('afterprint'));
  assert.equal(r.document.getElementById('first-fold').open, false);
  assert.equal(r.document.getElementById('second-fold').open, true);
});

test('mobile navigation toggle closes on selection and Escape', () => {
  const r = reader(fixture); r.click('toggle-sidebar');
  assert.equal(r.document.getElementById('toggle-sidebar').getAttribute('aria-expanded'), 'true');
  r.click('nav2'); assert.equal(r.document.getElementById('sidebar').classList.contains('is-open'), false);
  r.click('toggle-sidebar');
  const escape = new r.window.Event('keydown'); escape.key = 'Escape'; r.document.dispatchEvent(escape);
  assert.equal(r.document.getElementById('toggle-sidebar').getAttribute('aria-expanded'), 'false');
});

test('actual page preserves complete text, old deep links and cross-school evidence', () => {
  const r = reader(fs.readFileSync(path.join(__dirname, '../dist/index.html'), 'utf8'));
  const content = r.document.getElementById('research-content'), before = researchText(content);
  assert.deepEqual(r.visible(), ['school-001']);
  assert.equal(r.document.querySelectorAll('#school-navigation .school-link').length, 104);
  assert.equal(r.document.querySelectorAll('#school-navigation .late-switch').length, 4);
  r.go('#empirical-group-03'); assert.deepEqual(r.visible(), ['school-008']);
  r.go('#evidence-072'); assert.deepEqual(r.visible(), ['chapter-7']);
  r.go('#complete-evidence'); assert.deepEqual(r.visible(), ['chapter-7']);
  for (const query of ['原有34张图片线索的研究范围', '085410', '贵州大学']) {
    r.search(query); assert.match(r.document.getElementById('search-status').textContent, /^1 \/ \d+ 处$/, query);
    assert.equal(r.visible().length, 1);
  }
  r.search(''); assert.equal(researchText(content), before);
  assert.equal(r.document.querySelectorAll('a[id^="school-"]').length, 104);
});

// TraceId: 6e1e24ca-cd0a-45ae-9808-f82bd5b15ad8
test('Hunan merged admissions and historical directions stay distinct across school navigation', () => {
  const r = reader(fs.readFileSync(path.join(__dirname, '../dist/index.html'), 'utf8'), '#school-029');
  const hnu = r.document.getElementById('panel-school-029');
  const current = r.document.getElementById('project-school-029-csee-085400');
  const historical = r.document.getElementById('project-school-029-former-csee-085400');
  const software = r.document.getElementById('direction-school-029-former-csee-085400-software-history');
  assert.deepEqual(r.visible(), ['school-029']);
  assert.equal(hnu.querySelector('.admission-home').hidden, false);
  assert.equal(current.hidden, true);
  assert.equal(historical.hidden, true);
  assert.equal(hnu.querySelectorAll('.late-project').length, 0, 'May announcement must not become a second-half red label');
  r.go('#empirical-group-33');
  assert.equal(current.hidden, false);
  assert.equal(historical.hidden, true);
  assert.equal(r.document.getElementById('empirical-group-33').closest('.admission-project'), current);
  r.go('#' + software.id);
  assert.equal(software.closest('.admission-project'), historical);
  assert.equal(current.hidden, true);
  assert.equal(historical.hidden, false);
  assert.match(hnu.querySelector('.admission-breadcrumb').textContent, /软件工程/);
  assert.match(software.textContent, /2023/);
  assert.match(software.textContent, /2025/);
  assert.match(software.textContent, /866/);
  r.go('#project-school-069-207-085405');
  assert.deepEqual(r.visible(), ['school-069']);
  assert.equal(hnu.hidden, true);
  assert.match(r.document.getElementById('current-page').textContent, /北京理工大学/);
  r.go('#school-029');
  assert.deepEqual(r.visible(), ['school-029']);
  assert.equal(hnu.querySelector('.admission-home').hidden, false);
  assert.equal(current.hidden, true);
  assert.equal(historical.hidden, true);
});

// TraceId: c4d5b28b-0b67-4d2f-89e1-b46eb1090822
test('Hunan direction outline reaches shared retest facts and keeps every annual field', () => {
  const r = reader(fs.readFileSync(path.join(__dirname, '../dist/index.html'), 'utf8'), '#direction-school-029-former-csee-085400-computer-history');
  const panel = r.document.getElementById('panel-school-029');
  const history = r.document.getElementById('project-school-029-former-csee-085400');
  const direction = r.document.getElementById('direction-school-029-former-csee-085400-computer-history');
  const before = researchText(r.document.getElementById('research-content'));
  assert.equal(history.dataset.readingLayout, 'records');
  const rows = [...direction.querySelectorAll('table.score-record-table tbody tr')];
  assert.equal(rows.length, 3);
  for (const row of rows) {
    assert.deepEqual([...row.querySelectorAll('td')].map(td => td.dataset.label), [
      '招生年度', '当年初试科目与证据', '当年学院与统计方向', '普通录取人数',
      '复试总分线', '录取最低分', '录取中位数', '录取平均分', '录取最高分'
    ]);
  }
  const outline = panel.querySelector('.project-contents');
  assert.equal(outline.hidden, false);
  assert.ok([...outline.querySelectorAll('[data-direction-owner$="software-history"]')].every(link => link.hidden));
  const retest = [...outline.querySelectorAll('a')].find(link => /共同初试与复试|逐年笔试|共同复试/.test(link.textContent));
  assert.ok(retest, 'Shared retest section is one click away from this direction');
  retest.dispatchEvent(new r.window.Event('click', {bubbles:true,cancelable:true}));
  assert.equal(panel.querySelector(`.project-contents [data-section-target="${retest.dataset.sectionTarget}"]`), retest, 'In-project navigation must preserve the focused link node');
  assert.equal(history.hidden, false);
  assert.equal(r.document.getElementById('project-school-029-csee-085400').hidden, true);
  assert.equal(r.document.getElementById(retest.dataset.sectionTarget).dataset.scrolled, 'true');
  assert.equal(direction.querySelector('.table-scroll').getAttribute('aria-label'), '项目数据记录');
  assert.equal(direction.querySelector('.table-scroll').hasAttribute('tabindex'), false);
  r.go('#school-029');
  assert.equal(panel.querySelector('.project-contents').hidden, true);
  assert.equal(researchText(r.document.getElementById('research-content')), before);
});
