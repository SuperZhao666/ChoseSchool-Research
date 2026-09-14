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

// TraceId: aab7da2b-f5ac-4368-932e-f8f414c5ad61
const topicFixture = fixture.replace('<h3>AI与数据</h3>', `<h3>AI与数据</h3>
<nav class="school-topic-navigation" data-reader-ui="true" aria-label="本校资料分类">
<p>本校资料分类</p><button type="button" id="topic-programs" data-topic-target="programs" aria-controls="programs" aria-pressed="true">招生项目</button>
<button type="button" id="topic-scores" data-topic-target="scores" aria-controls="scores" aria-pressed="false">历年分数</button></nav>
<section class="school-topic" id="programs" data-topic-key="programs" data-topic-title="招生项目"><h4>招生项目正文</h4>`)
  .replace('<ul><li>父项独有文本<ul><li>子项</li></ul></li></ul>', `</section>
<section class="school-topic" id="scores" data-topic-key="scores" data-topic-title="历年分数" hidden><h4>历年分数正文</h4>
<details id="score-fold"><summary>软件分数</summary><a id="score-evidence"></a><p>科目885，年度2026，初试341</p></details></section>`);

function visibleTopics(r) {
  return [...r.document.querySelectorAll('#panel-school-001 .school-topic')].filter(topic => !topic.hidden).map(topic => topic.dataset.topicKey);
}

test('school topics show one category, retain per-school choice and preserve original school hashes', () => {
  const r = reader(topicFixture, '#s1');
  const before = r.document.getElementById('research-content').textContent;
  assert.deepEqual(visibleTopics(r), ['programs']);
  assert.equal(r.document.getElementById('expand-all').textContent, '展开本栏资料');
  assert.equal(r.document.getElementById('collapse-all').textContent, '收起本栏资料');
  r.click('topic-scores');
  assert.deepEqual(visibleTopics(r), ['scores']);
  assert.equal(r.document.getElementById('topic-scores').getAttribute('aria-pressed'), 'true');
  assert.equal(r.document.getElementById('topic-programs').getAttribute('aria-pressed'), 'false');
  assert.equal(r.location.hash, '#s1');
  r.click('nav2');
  assert.equal(r.document.getElementById('expand-all').textContent, '展开本页全部资料');
  assert.equal(r.document.getElementById('collapse-all').textContent, '收起本页资料');
  r.click('nav1');
  assert.equal(r.document.getElementById('expand-all').textContent, '展开本栏资料');
  assert.equal(r.document.getElementById('collapse-all').textContent, '收起本栏资料');
  assert.deepEqual(r.visible(), ['school-001']);
  assert.deepEqual(visibleTopics(r), ['scores']);
  assert.equal(r.document.getElementById('research-content').textContent, before);
  for (const button of r.document.querySelectorAll('[data-topic-target]')) {
    assert.equal(button.tagName, 'BUTTON');
    assert.equal(button.getAttribute('type'), 'button');
    assert.ok(r.document.getElementById(button.getAttribute('aria-controls')));
  }
});

test('full-text search and old deep links reveal the matching topic and its folded evidence', () => {
  const r = reader(topicFixture);
  r.search('初试341');
  assert.deepEqual(visibleTopics(r), ['scores']);
  assert.equal(r.document.getElementById('score-fold').open, true);
  assert.equal(r.document.querySelector('mark').textContent, '初试341');
  r.click('topic-programs'); r.go('#score-evidence');
  assert.deepEqual(visibleTopics(r), ['scores']);
  assert.equal(r.document.getElementById('score-fold').open, true);
  r.search('本校资料分类');
  assert.equal(r.document.getElementById('search-status').textContent, '没有找到匹配内容');
  r.search('招生项目');
  assert.equal(r.document.getElementById('search-status').textContent, '1 / 1 处');
  assert.deepEqual(visibleTopics(r), ['programs']);
});

test('fold controls affect the selected topic; printing includes all current-school topics and restores state', () => {
  const r = reader(topicFixture);
  r.click('expand-all');
  assert.equal(r.document.getElementById('first-fold').open, true);
  assert.equal(r.document.getElementById('score-fold').open, false);
  r.click('topic-scores'); r.click('collapse-all');
  assert.equal(r.document.getElementById('first-fold').open, true);
  r.window.dispatchEvent(new r.window.Event('beforeprint'));
  assert.deepEqual(visibleTopics(r), ['programs', 'scores']);
  assert.deepEqual(r.visible(), ['school-001']);
  assert.equal(r.document.getElementById('score-fold').open, true);
  assert.equal(r.document.getElementById('second-fold').open, false);
  r.window.dispatchEvent(new r.window.Event('afterprint'));
  assert.deepEqual(visibleTopics(r), ['scores']);
  assert.equal(r.document.getElementById('first-fold').open, true);
  assert.equal(r.document.getElementById('score-fold').open, false);
  assert.equal(r.document.querySelectorAll('[data-print-open],[data-print-hidden]').length, 0);
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
  const content = r.document.getElementById('research-content'), before = content.textContent;
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
  r.search(''); assert.equal(content.textContent, before);
  assert.equal(r.document.querySelectorAll('a[id^="school-"]').length, 104);
});
