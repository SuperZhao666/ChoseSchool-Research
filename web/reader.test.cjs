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
