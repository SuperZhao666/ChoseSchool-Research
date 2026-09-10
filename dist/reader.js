/* TraceId: c8929f22-a836-4ff9-87db-e9ee2a86a402 */
'use strict';
(() => {
  const content = document.getElementById('research-content');
  const panels = Array.from(content.querySelectorAll('.reader-panel'));
  const links = Array.from(document.querySelectorAll('[data-panel-target]'));
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('toggle-sidebar');
  const form = document.getElementById('search-form');
  const input = document.getElementById('search-input');
  const status = document.getElementById('search-status');
  const previous = document.getElementById('previous-result');
  const next = document.getElementById('next-result');
  const toolbar = document.querySelector('.toolbar');
  const selector = 'p,li,tr,h1,h2,h3,h4,h5,h6,summary';
  // Index all panels, including closed folds and parent list text.
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
  let active = panels.find(panel => !panel.hidden) || panels[0];

  function closeSidebar() {
    sidebar.classList.remove('is-open'); toggle.setAttribute('aria-expanded', 'false');
  }
  function showPanel(panel) {
    if (!panel) return;
    active = panel;
    for (const item of panels) item.hidden = item !== panel;
    for (const link of links) {
      if (link.dataset.panelTarget === panel.dataset.panel) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    document.getElementById('current-page').textContent = panel.dataset.title;
    document.title = `${panel.dataset.title} · 2027 择校池`;
  }
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
    const panel = element.closest('.reader-panel');
    showPanel(panel); expandParents(element); element.classList.add('search-current');
    highlight(element, input.value.trim().toLocaleLowerCase());
    status.textContent = `${current + 1} / ${matches.length} 处`;
    previous.disabled = next.disabled = matches.length < 2;
    // Keep refresh/share on the visible panel without adding a history entry per match.
    if (panel && window.history?.replaceState) window.history.replaceState(null, '', `#${panel.id}`);
    requestAnimationFrame(() => element.scrollIntoView({block: 'center', behavior: 'auto'}));
  }
  function search() {
    clearMarks(); const query = input.value.trim().toLocaleLowerCase();
    matches = query ? entries.filter(entry => entry.text.includes(query)) : [];
    current = -1;
    status.textContent = query ? '没有找到匹配内容' : '';
    showMatch(0);
  }
  function followHash() {
    let id; try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (!id) { showPanel(panels.find(panel => panel.dataset.panel.startsWith('school-'))); return; }
    const target = document.getElementById(id);
    if (!target || (!content.contains(target) && target !== content)) return;
    clearMarks(); showPanel(target.closest('.reader-panel')); expandParents(target);
    closeSidebar();
    requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
  }
  form.addEventListener('submit', event => { event.preventDefault(); closeSidebar(); search(); });
  input.addEventListener('input', () => { clearMarks(); matches = []; current = -1; previous.disabled = next.disabled = true; status.textContent = ''; });
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { input.value = ''; search(); } });
  previous.addEventListener('click', () => showMatch(current - 1));
  next.addEventListener('click', () => showMatch(current + 1));
  document.getElementById('expand-all').addEventListener('click', () => {
    active.querySelectorAll('details').forEach(detail => { detail.open = true; });
  });
  document.getElementById('collapse-all').addEventListener('click', () => {
    clearMarks(); active.querySelectorAll('details').forEach(detail => { detail.open = false; });
  });
  toggle.addEventListener('click', () => {
    const open = sidebar.classList.toggle('is-open'); toggle.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeSidebar(); });
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const href = link.getAttribute('href');
    let target; try { target = document.getElementById(decodeURIComponent(href.slice(1))); } catch { return; }
    if (!target) return;
    event.preventDefault(); location.hash = href; followHash();
  });
  window.addEventListener('hashchange', followHash);
  showPanel(active); if (location.hash) followHash();
  if ('ResizeObserver' in window) {
    new ResizeObserver(() => document.documentElement.style.setProperty('--toolbar-height', `${toolbar.offsetHeight}px`)).observe(toolbar);
  }
  window.addEventListener('beforeprint', () => {
    active.querySelectorAll('details').forEach(detail => { detail.dataset.printOpen = String(detail.open); detail.open = true; });
  });
  window.addEventListener('afterprint', () => {
    content.querySelectorAll('details[data-print-open]').forEach(detail => { detail.open = detail.dataset.printOpen === 'true'; delete detail.dataset.printOpen; });
  });
})();
