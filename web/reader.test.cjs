/* TraceId: a5a6f785-04be-4f85-8104-c604a2d186af */
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
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'reader.js'), 'utf8'), {
    document, window, location, NodeFilter: {SHOW_TEXT: 4},
    requestAnimationFrame: fn => fn()
  });
  const click = id => document.getElementById(id).dispatchEvent(new window.Event('click'));
  const search = value => {
    document.getElementById('search-input').value = value;
    document.getElementById('search-form').dispatchEvent(new window.Event('submit', {cancelable: true}));
  };
  return {document, window, location, click, search};
}

const fixture = `<html><body><header class="toolbar"></header>
<form id="search-form"><input id="search-input"></form><output id="search-status"></output>
<button id="previous-result"></button><button id="next-result"></button>
<button id="collapse-all"></button><select id="school-select"><option value="s">s</option></select>
<main id="research-content"><h1>AI与数据</h1><details><summary>历史</summary>
<details><summary>深层</summary><a id="s"></a><p>冷门人工智能 2026</p></details></details>
<ul><li>父项独有文本<ul><li>子项</li></ul></li></ul>
<table><tr><td>085410</td><td>41人</td></tr></table><p>末端 AI</p></main></body></html>`;

test('search reaches closed nested content, parent list text, table codes and final text', () => {
  const r = reader(fixture);
  r.search('人工智能');
  assert.equal(r.document.getElementById('search-status').textContent, '1 / 1 处');
  assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  assert.equal(r.document.querySelector('mark').textContent, '人工智能');
  for (const query of ['父项独有文本', '085410', '末端 AI']) {
    r.search(query);
    assert.equal(r.document.getElementById('search-status').textContent, '1 / 1 处', query);
  }
});

test('next/previous wrap; empty and missing queries clear marks safely', () => {
  const r = reader(fixture); r.search('ai');
  assert.equal(r.document.getElementById('search-status').textContent, '1 / 2 处');
  r.click('next-result');
  assert.equal(r.document.getElementById('search-status').textContent, '2 / 2 处');
  r.click('next-result'); r.click('previous-result');
  assert.equal(r.document.getElementById('search-status').textContent, '2 / 2 处');
  r.search('<img onerror=alert(1)>');
  assert.equal(r.document.querySelectorAll('img').length, 0);
  assert.equal(r.document.getElementById('search-status').textContent, '没有找到匹配内容');
  r.search(''); assert.equal(r.document.querySelectorAll('mark').length, 0);
  assert.equal(r.document.getElementById('search-status').textContent, '');
});

test('direct hash and later hash navigation open ancestors; print restores open states', () => {
  const r = reader(fixture, '#s');
  assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  r.click('collapse-all'); assert.equal(r.document.querySelectorAll('details[open]').length, 0);
  r.window.dispatchEvent(new r.window.Event('hashchange'));
  assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  r.click('collapse-all');
  r.window.dispatchEvent(new r.window.Event('beforeprint'));
  assert.equal(r.document.querySelectorAll('details[open]').length, 2);
  r.window.dispatchEvent(new r.window.Event('afterprint'));
  assert.equal(r.document.querySelectorAll('details[open]').length, 0);
});

test('actual complete page search reaches final evidence without losing text', () => {
  const html = fs.readFileSync(path.join(__dirname, '../dist/index.html'), 'utf8');
  const r = reader(html);
  const content = r.document.getElementById('research-content');
  const before = content.textContent;
  for (const query of ['原有34张图片线索的研究范围', '085410', '贵州大学']) {
    r.search(query);
    assert.match(r.document.getElementById('search-status').textContent, /^1 \/ \d+ 处$/, query);
  }
  r.search(''); assert.equal(content.textContent, before);
  assert.equal(r.document.querySelectorAll('a[id^="school-"]').length, 104);
});
