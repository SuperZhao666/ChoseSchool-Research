/* TraceId: a5a6f785-04be-4f85-8104-c604a2d186af */
'use strict';
(() => {
  const content = document.getElementById('research-content');
  const form = document.getElementById('search-form');
  const input = document.getElementById('search-input');
  const status = document.getElementById('search-status');
  const previous = document.getElementById('previous-result');
  const next = document.getElementById('next-result');
  const toolbar = document.querySelector('.toolbar');
  const selector = 'p,li,tr,h1,h2,h3,h4,h5,h6,summary';
  // Group every text node by its nearest readable block, including the text
  // before nested lists. Filtering to leaf elements would silently omit it.
  const blocks = new Map();
  const textWalker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
  let textNode;
  while ((textNode = textWalker.nextNode())) {
    if (!textNode.nodeValue.trim()) continue;
    const element = textNode.parentElement.closest(selector) || textNode.parentElement;
    if (!blocks.has(element)) blocks.set(element, {element, text: ''});
    blocks.get(element).text += textNode.nodeValue;
  }
  const entries = Array.from(blocks.values()).map(entry => ({...entry, text: entry.text.toLocaleLowerCase()}));
  let matches = [], current = -1, marked = [];

  function expandParents(element) {
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
  }
  function clearMarks() {
    content.querySelectorAll('.search-current').forEach(el => el.classList.remove('search-current'));
    for (const mark of marked) {
      const parent = mark.parentNode;
      if (parent) { mark.replaceWith(document.createTextNode(mark.textContent)); parent.normalize(); }
    }
    marked = [];
  }
  function highlight(element, query) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const nodes = []; let node;
    while ((node = walker.nextNode())) nodes.push(node);
    for (const textNode of nodes) {
      const text = textNode.nodeValue, lower = text.toLocaleLowerCase();
      let start = 0, found = lower.indexOf(query); if (found < 0) continue;
      const fragment = document.createDocumentFragment();
      while (found >= 0) {
        fragment.append(document.createTextNode(text.slice(start, found)));
        const mark = document.createElement('mark'); mark.textContent = text.slice(found, found + query.length);
        fragment.append(mark); marked.push(mark); start = found + query.length;
        found = lower.indexOf(query, start);
      }
      fragment.append(document.createTextNode(text.slice(start))); textNode.replaceWith(fragment);
    }
  }
  function showMatch(index) {
    clearMarks();
    if (!matches.length) { current = -1; previous.disabled = next.disabled = true; return; }
    current = (index + matches.length) % matches.length;
    const element = matches[current].element;
    expandParents(element); element.classList.add('search-current');
    highlight(element, input.value.trim().toLocaleLowerCase());
    status.textContent = `${current + 1} / ${matches.length} 处`;
    previous.disabled = next.disabled = matches.length < 2;
    requestAnimationFrame(() => element.scrollIntoView({block: 'center', behavior: 'auto'}));
  }
  function search() {
    clearMarks(); const query = input.value.trim().toLocaleLowerCase();
    matches = query ? entries.filter(entry => entry.text.includes(query)) : [];
    current = -1;
    status.textContent = query ? '没有找到匹配内容' : '';
    showMatch(0);
  }
  form.addEventListener('submit', event => { event.preventDefault(); search(); });
  input.addEventListener('input', () => { clearMarks(); matches = []; current = -1; previous.disabled = next.disabled = true; status.textContent = ''; });
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { input.value = ''; search(); } });
  previous.addEventListener('click', () => showMatch(current - 1));
  next.addEventListener('click', () => showMatch(current + 1));
  document.getElementById('collapse-all').addEventListener('click', () => {
    clearMarks(); content.querySelectorAll('details').forEach(detail => { detail.open = false; });
  });
  document.getElementById('school-select').addEventListener('change', event => {
    if (event.target.value) location.hash = event.target.value;
  });
  function followHash() {
    let id; try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    expandParents(target);
    requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
  }
  window.addEventListener('hashchange', followHash);
  content.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (link && link.getAttribute('href') === location.hash) followHash();
  });
  if (location.hash) followHash();
  if ('ResizeObserver' in window) {
    new ResizeObserver(() => document.documentElement.style.setProperty('--toolbar-height', `${toolbar.offsetHeight}px`)).observe(toolbar);
  }
  window.addEventListener('beforeprint', () => {
    content.querySelectorAll('details').forEach(detail => { detail.dataset.printOpen = String(detail.open); detail.open = true; });
  });
  window.addEventListener('afterprint', () => {
    content.querySelectorAll('details').forEach(detail => { detail.open = detail.dataset.printOpen === 'true'; delete detail.dataset.printOpen; });
  });
})();
