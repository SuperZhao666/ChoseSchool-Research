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
  // TraceId: 4fa2880a-e3d3-40b3-a2d9-8c69ad9fd505
  // Each program belongs to one college; directions retain their shared program.
  const entities = new Map(panels.map(panel => [panel, {
    colleges: Array.from(panel.querySelectorAll('.school-college')),
    projects: Array.from(panel.querySelectorAll('.admission-project')),
    notes: panel.querySelector('.admission-notes')
  }]));
  const entitySelector = '.research-direction,.admission-project,.school-college,.admission-notes';
  // TraceId: c4d5b28b-0b67-4d2f-89e1-b46eb1090822
  content.querySelectorAll('.readable-table').forEach(table => {
    const region = table.closest('.table-scroll');
    if (region) {
      region.setAttribute('aria-label', '项目数据记录');
      region.removeAttribute('tabindex');
    }
  });
  // TraceId: 12977bfb-1cef-4a83-b35a-0c58141c1a37
  // Outline actual source headings/folds, without guessing admissions entities.
  function addSchoolContents(panel) {
    if (!panel.dataset.panel.startsWith('school-') || entities.get(panel).colleges.length) return;
    const targets = Array.from(panel.querySelectorAll('h4,h5,h6,summary'));
    if (!targets.length) return;
    const navigation = document.createElement('nav');
    navigation.className = 'school-contents';
    navigation.id = `contents-${panel.dataset.panel}`;
    navigation.setAttribute('data-reader-ui', 'true');
    navigation.setAttribute('aria-label', '本校内容导航');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = '本校内容导航';
    button.setAttribute('aria-expanded', 'true');
    const list = document.createElement('div');
    list.className = 'school-contents-list';
    list.id = `sections-${panel.dataset.panel}`;
    button.setAttribute('aria-controls', list.id);
    button.addEventListener('click', () => {
      list.hidden = !list.hidden;
      button.setAttribute('aria-expanded', String(!list.hidden));
    });
    targets.forEach((target, index) => {
      if (!target.id) target.id = `reading-${panel.dataset.panel}-${index + 1}`;
      const link = document.createElement('a');
      link.href = `#${target.id}`;
      link.dataset.sectionTarget = target.id;
      link.textContent = target.textContent;
      const depth = target.tagName === 'SUMMARY' ? 0 : Number(target.tagName.slice(1)) - 4;
      link.dataset.depth = String(Math.max(0, depth));
      if (target.closest('details')) link.classList.add('fold-section-link');
      list.append(link);
    });
    navigation.append(button, list);
    const intro = panel.querySelector('.switch-flag,.switch-note') || panel.querySelector('.school-tier') || panel.querySelector('h3');
    if (intro) intro.after(navigation); else panel.prepend(navigation);
  }
  panels.forEach(addSchoolContents);
  // Within a chosen project, expose direct links to its actual content headings.
  // This is a project outline, not another school-wide topic classification.
  function updateProjectContents(panel, project, direction) {
    const navigation = panel.querySelector('.admission-navigation');
    if (!navigation) return;
    let outline = navigation.querySelector('.project-contents');
    if (!outline) {
      outline = document.createElement('div');
      outline.className = 'project-contents';
      outline.setAttribute('data-reader-ui', 'true');
      navigation.insertBefore(outline, navigation.querySelector('.admissions-notes-link'));
    }
    outline.hidden = !project;
    if (!project) return;
    const filterDirection = () => outline.querySelectorAll('[data-direction-owner]').forEach(link => {
      link.hidden = Boolean(direction && link.dataset.directionOwner !== direction.id);
    });
    // Preserve focused links while moving between sections of the same project.
    if (outline.dataset.projectId === project.id) { filterDirection(); return; }
    navigation.scrollTop = 0;
    outline.dataset.projectId = project.id;
    outline.replaceChildren();
    const label = document.createElement('p');
    label.className = 'project-contents-title';
    label.textContent = '本项目详细内容';
    outline.append(label);
    const headings = Array.from(project.querySelectorAll('h4[id],h5[id],h6[id]'));
    for (const heading of headings.slice(1)) {
      const owner = heading.closest('.research-direction');
      const link = document.createElement('a');
      link.href = `#${heading.id}`;
      link.dataset.sectionTarget = heading.id;
      if (owner) link.dataset.directionOwner = owner.id;
      link.textContent = heading.textContent;
      outline.append(link);
    }
    filterDirection();
  }
  const selector = 'p,li,tr,h1,h2,h3,h4,h5,h6,summary';
  // Index all panels, including closed folds and parent list text.
  const blocks = new Map();
  const textWalker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
  let textNode;
  while ((textNode = textWalker.nextNode())) {
    if (!textNode.nodeValue.trim()) continue;
    if (textNode.parentElement.closest('[data-reader-ui]')) continue;
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
  function showEntity(panel, selected = null) {
    const group = entities.get(panel);
    if (!group?.colleges.length) return;
    const direction = selected?.closest('.research-direction');
    const project = selected?.closest('.admission-project');
    const college = selected?.closest('.school-college');
    const notes = selected?.closest('.admission-notes');
    panel.dataset.activeEntity = (direction || project || college || notes)?.id || '';
    for (const item of group.colleges) {
      item.hidden = item !== college;
      // The college chooser already carries its name; keep the source heading for project reading.
      Array.from(item.children).filter(child => /^H[1-6]$/.test(child.tagName)).forEach(heading => { heading.hidden = !project; });
    }
    for (const item of group.projects) item.hidden = item !== project;
    if (group.notes) group.notes.hidden = !notes;
    panel.querySelector('.admission-home').hidden = Boolean(college || notes);
    panel.querySelectorAll('.college-overview').forEach(overview => {
      overview.hidden = Boolean(project);
      const heading = overview.querySelector('h4'); if (heading) heading.hidden = false;
    });
    panel.querySelectorAll('[data-projects-for]').forEach(branch => { branch.hidden = branch.dataset.projectsFor !== college?.id; });
    panel.querySelectorAll('[data-directions-for]').forEach(branch => { branch.hidden = branch.dataset.directionsFor !== project?.id; });
    panel.querySelectorAll('.research-direction').forEach(item => item.classList.toggle('is-current-direction', item === direction));
    updateProjectContents(panel, project, direction);
    panel.querySelectorAll('[data-entity-target]').forEach(link => {
      const target = link.dataset.entityTarget;
      if (target === panel.dataset.activeEntity) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
      link.classList.toggle('is-entity-parent', target === college?.id || target === project?.id);
      if (link.classList.contains('college-link') || link.classList.contains('project-link')) {
        link.setAttribute('aria-expanded', String(target === college?.id || target === project?.id));
      }
    });
    const path = [panel.dataset.title, college?.dataset.collegeTitle, project?.dataset.projectTitle,
      direction?.dataset.directionTitle, notes?.dataset.notesTitle].filter(Boolean);
    panel.querySelector('.admission-breadcrumb').textContent = path.join(' / ');
    document.getElementById('current-page').textContent = path.join(' / ');
    document.title = `${path.join(' / ')} · 2027 择校池`;
    document.getElementById('expand-all').textContent = project ? '展开本项目资料' : notes ? '展开共同说明' : '展开项目资料';
    document.getElementById('collapse-all').textContent = project ? '收起本项目资料' : notes ? '收起共同说明' : '收起项目资料';
    document.getElementById('expand-all').disabled = document.getElementById('collapse-all').disabled = !project && !notes;
  }
  function visibleScope() {
    if (entities.get(active)?.colleges.length) {
      return active.querySelector('.admission-project:not([hidden]),.admission-notes:not([hidden])');
    }
    return active;
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
    document.getElementById('expand-all').textContent = '展开本页全部资料';
    document.getElementById('collapse-all').textContent = '收起本页资料';
    document.getElementById('expand-all').disabled = document.getElementById('collapse-all').disabled = false;
    showEntity(panel, document.getElementById(panel.dataset.activeEntity || ''));
  }
  function expandParents(element) {
    const panel = element.closest('.reader-panel');
    if (panel) showEntity(panel, element.closest(entitySelector));
    // A search or legacy heading anchor must reveal the original college heading.
    if (/^H[1-6]$/.test(element.tagName) && element.parentElement?.classList.contains('school-college')) {
      element.hidden = false;
      const heading = element.parentElement.querySelector('.college-overview h4');
      if (heading) heading.hidden = true;
    }
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    if (element.tagName === 'SUMMARY') element.parentElement.open = true;
    panel?.querySelectorAll('.school-contents [data-section-target]').forEach(link => {
      if (link.dataset.sectionTarget === element.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
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
    // Refresh/share preserves the entity that owns this result, even across colleges.
    const destination = element.closest(entitySelector) || panel;
    if (destination && window.history?.replaceState) window.history.replaceState(null, '', `#${destination.id}`);
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
    const start = target.matches('.admission-project,.school-college,.admission-notes,.admission-layout')
      ? target.closest('.reader-panel').querySelector('.admission-breadcrumb') || target : target;
    requestAnimationFrame(() => start.scrollIntoView({block: 'start'}));
  }
  form.addEventListener('submit', event => { event.preventDefault(); closeSidebar(); search(); });
  input.addEventListener('input', () => { clearMarks(); matches = []; current = -1; previous.disabled = next.disabled = true; status.textContent = ''; });
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { input.value = ''; search(); } });
  previous.addEventListener('click', () => showMatch(current - 1));
  next.addEventListener('click', () => showMatch(current + 1));
  document.getElementById('expand-all').addEventListener('click', () => {
    visibleScope()?.querySelectorAll('details').forEach(detail => { detail.open = true; });
  });
  document.getElementById('collapse-all').addEventListener('click', () => {
    clearMarks(); visibleScope()?.querySelectorAll('details').forEach(detail => { detail.open = false; });
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
    // Print only the selected project's complete dossier, restoring fold state afterward.
    visibleScope()?.querySelectorAll('details').forEach(detail => { detail.dataset.printOpen = String(detail.open); detail.open = true; });
  });
  window.addEventListener('afterprint', () => {
    content.querySelectorAll('details[data-print-open]').forEach(detail => { detail.open = detail.dataset.printOpen === 'true'; delete detail.dataset.printOpen; });
  });
})();
