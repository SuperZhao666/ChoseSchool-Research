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
  const schoolFilter=document.getElementById('school-filter');
  schoolFilter?.addEventListener('input',()=>{
    const query=schoolFilter.value.trim().toLocaleLowerCase();let count=0;
    document.querySelectorAll('#school-navigation .school-link').forEach(link=>{
      const name=link.querySelector('.school-name').textContent.toLocaleLowerCase();
      const tier=link.querySelector('.school-meta').textContent;
      const matchesTier=query==='985'?tier==='985':query==='211'?tier.startsWith('211'):query==='双非'?tier==='双非':false;
      link.hidden=Boolean(query && !name.includes(query) && !matchesTier);if(!link.hidden)count++;
    });
    document.getElementById('school-filter-status').textContent=query?`${count} 所匹配` : '';
  });
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
    if (!panel.dataset.panel.startsWith('school-') || panel.querySelector('.admission-layout')) return;
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
    button.setAttribute('aria-expanded', 'false');
    const list = document.createElement('div');
    list.className = 'school-contents-list';
    list.id = `sections-${panel.dataset.panel}`;
    list.hidden = true;
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
  // TraceId: 620a4022-cd30-48ab-992b-4a26e0cff841
  // The first screen chooses a real admissions entity, not a research appendix.
  for (const panel of panels) {
    const layout = panel.querySelector('.admission-layout');
    if (!layout) continue;
    const intro = []; let collecting = false;
    for (const node of Array.from(panel.childNodes)) {
      if (node === layout) break;
      if (node.nodeType === 1 && node.matches('.school-reading-status,.school-reading-hint')) continue;
      if (node.nodeType === 1 && !node.matches('a[id],h3,.school-tier,.switch-flag,.switch-note') && !node.querySelector('a[id]')) collecting = true;
      if (collecting) intro.push(node);
    }
    if (intro.length) {
      const fold = document.createElement('details'); fold.className = 'school-background';
      const summary = document.createElement('summary');
      summary.setAttribute('data-reader-ui', 'true'); summary.textContent = '学校概况与待核事项';
      intro[0].before(fold); fold.append(summary);
      for (const node of intro) fold.append(node);
    }
  }
  const readingScopes = new Map();
  const topicNames = {overview:'先看结论',admissions:'招生与科目',scores:'历年分数',retest:'复试与面试',training:'培养与费用',judgment:'竞争与经验',sources:'来源与补充'};
  function topicFor(title, fallback = 'sources') {
    if (/历史分数能参考|竞争|经验|真题|难度|参考价值|个人/.test(title)) return 'judgment';
    if (/历年科目、录取人口|分数|复试线|单科线|分布|录取人数|最终录取|最终拟录取|复试人数|统计|递补|人口|科目与成绩|公开项目数据/.test(title)) return 'scores';
    const retest=/复试|面试|机试|上机|材料清单/.test(title);
    const training=/培养|费用|住宿|导师|实践|毕业|学费|地点|合同/.test(title);
    if (retest && training) return 'retest training';
    if (training) return 'training';
    if (retest) return 'retest';
    if (/科目|目录|改考|招生|方向|计划/.test(title)) return 'admissions';
    if (/判断|竞争|经验|真题|难度|参考|个人|风险|边界/.test(title)) return 'judgment';
    if (/来源|依据|核验|审计|证据/.test(title)) return 'sources';
    return fallback;
  }
  function setReadingTopic(scope, topic) {
    const flow = readingScopes.get(scope); if (!flow) return;
    scope.dataset.readingTopic = topic;
    for (const chapter of flow.chapters) {
      const owner=chapter.closest('.research-direction');
      const relevantDirection=!scope.dataset.readingDirection || !owner || owner.id===scope.dataset.readingDirection;
      chapter.hidden = !chapter.textContent.trim() || (topic !== 'all' && (!chapter.dataset.readingTopic.split(' ').includes(topic) || !relevantDirection));
    }
    for (const container of [...flow.containers].reverse()) {
      container.hidden=!container.querySelector('.reading-chapter:not([hidden])');
      if (!container.hidden && container.tagName==='DETAILS') container.open=true;
    }
    flow.nav.querySelectorAll('[data-reading-view]').forEach(link => {
      if (link.dataset.readingView === topic) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    const seen=new Set();
    scope.querySelectorAll('[data-material-id]').forEach(node=>{
      node.hidden=topic==='all' && seen.has(node.dataset.materialId);seen.add(node.dataset.materialId);
    });
    if(topic==='all')scope.querySelectorAll('.additional-record').forEach(fold=>{fold.open=true;});
  }
  // TraceId: 8d98f22a-7a30-4d09-b60c-59c407ea8b93
  // The README keeps each original once. Project views copy complete source
  // rows on demand, retain their context, and never calculate admissions facts.
  const sourceIndexes = new Map();
  function materialIndex(panel) {
    if (sourceIndexes.has(panel)) return sourceIndexes.get(panel);
    const specs = entities.get(panel).projects.map(project => {
      const college=project.closest('.school-college');
      const selector=project.querySelector('.project-source-selector');
      const title=project.dataset.projectTitle || '';
      const terms=selector?JSON.parse(selector.dataset.projectTerms):[title];
      const codes=(title.match(/\b(?:0\d{5}|1\d{5}|\d{4}[A-Za-z]\d)\b/g)||[]).map(s=>s.toLowerCase());
      const collegeTitle=college.dataset.collegeTitle || '';
      const collegeCode=collegeTitle.match(/(?:^|[ ·])([0-9]{3})(?:\s|—)/)?.[1];
      const collegeNames=collegeTitle.split(/[·／（(]/).map(s=>s.replace(/^\s*\d{3}\s*/,'').trim()).filter(s=>s.length>=4 && !/待核|培养单位|招生单位|历史|由原/.test(s));
      return {project, college, terms, codes, collegeCode, collegeNames};
    });
    const all=specs.map(s=>s.project.id);
    function owners(text, inherited=all) {
      text=text.toLowerCase().replace(/\s+/g,'');
      const codeOwners=specs.filter(s=>s.codes.some(code=>text.includes(code)));
      // A comparison row for an unlisted program must not inherit every
      // project in its enclosing school-wide table. Explicit single-project
      // historical sections may still contain a former program code.
      if(!codeOwners.length && /(?:0\d{5}|1\d{5}|\d{4}[a-z]\d)/.test(text) && inherited.length>1)return [];
      const collegeOwners=specs.filter(s=>s.collegeNames.some(name=>text.includes(name.toLowerCase().replace(/\s+/g,''))) ||
        s.collegeCode && new RegExp(`(^|[^0-9])${s.collegeCode}(?=[—－/／·\\-\\u4e00-\\u9fff])`).test(text));
      const named=specs.filter(s=>s.terms.some(term=>term.length>=2 && /[\u4e00-\u9fff]/.test(term) && text.includes(term.toLowerCase().replace(/\s+/g,''))));
      let candidates=codeOwners.length?codeOwners:(named.length?named:collegeOwners);
      if (!candidates.length) return inherited;
      if(codeOwners.length && named.length) {
        const narrowed=candidates.filter(s=>named.includes(s));
        if(narrowed.length)candidates=narrowed;
      }
      if(collegeOwners.length) {
        const narrowed=candidates.filter(s=>collegeOwners.includes(s));
        if(narrowed.length) candidates=narrowed;
      } else if (inherited.length<all.length) {
        const narrowed=candidates.filter(s=>inherited.includes(s.project.id));
        if(narrowed.length) candidates=narrowed;
      }
      return candidates.map(s=>s.project.id);
    }
    const groups=[];
    function visit(container, trail=[], inherited=all) {
      let nodes=[], path=trail.slice(), scope=inherited;
      function flush(){if(nodes.some(n=>n.textContent.trim()))groups.push({nodes,path:path.slice(),owners:scope});nodes=[];}
      for(const node of Array.from(container.children)) {
        if(node.matches('[data-reader-ui],.admission-project,.school-college,summary,a[id]')) continue;
        if(node.matches('details')) {
          flush();const title=node.querySelector('summary')?.textContent || '';
          visit(node,[...path,title],owners(title,scope));continue;
        }
        if(node.matches('h4,h5,h6')) {
          flush();const title=node.textContent;
          path=[...trail,title];scope=owners(title,inherited);continue;
        }
        nodes.push(node);
      }
      flush();
    }
    for(const root of [panel.querySelector('.school-background'),entities.get(panel).notes].filter(Boolean)) visit(root);
    const result={groups,owners,all};sourceIndexes.set(panel,result);return result;
  }
  function cleanCopy(node) {
    const copy=node.cloneNode(true);
    if(copy.id)copy.removeAttribute('id');
    copy.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
    copy.querySelectorAll('[hidden]').forEach(n=>n.removeAttribute('hidden'));
    return copy;
  }
  function hydrateProject(project) {
    const selector=project?.querySelector('.project-source-selector');
    if(!selector || selector.dataset.ready) return;
    selector.dataset.ready='true';
    const panel=project.closest('.reader-panel'), index=materialIndex(panel);
    const slots=new Map([...project.querySelectorAll('.project-excerpts')].map(s=>[s.dataset.excerptTopic,s]));
    const counts=new Map();
    function add(topic,node){const slot=slots.get(topic);if(!slot)return;slot.append(node);counts.set(topic,(counts.get(topic)||0)+1);}
    function contextFold(group, title='口径、出处与相邻说明') {
      const fold=document.createElement('details');fold.className='evidence-context';
      const summary=document.createElement('summary');summary.textContent=title;fold.append(summary);
      for(const node of group.nodes) if(!node.matches('.table-scroll,table'))fold.append(cleanCopy(node));
      const link=document.createElement('a');link.href=`#${entities.get(panel).notes.id}`;link.textContent='查看本校完整原文';fold.append(link);
      return fold;
    }
    for(const [groupIndex,group] of index.groups.entries()) {
      const title=(group.path.at(-1) || '已查项目情况').replace(/^(?:补回早期已查到的公开项目数据|目录、招生历史与补充核验|报考需求、容量、改考与新增项目证据)[：:]\s*/, '');
      const headingContext=group.path.join(' / ');
      let hasTable=false;
      for(const [tableIndex,node] of group.nodes.filter(n=>n.matches('.table-scroll,table')).entries()) {
        const table=node.matches('table')?node:node.querySelector('table');if(!table)continue;
        const rows=Array.from(table.querySelectorAll('tbody > tr'));
        const rowOwners=rows.map(row=>index.owners(row.querySelector('td')?.textContent || '',group.owners));
        const wanted=rows.filter((row,i)=>rowOwners[i].includes(project.id));
        if(!wanted.length)continue;
        const shared=rowOwners.some((ids,i)=>wanted.includes(rows[i]) && ids.length>1);
        const copy=cleanCopy(node), copyTable=copy.matches('table')?copy:copy.querySelector('table');
        Array.from(copyTable.querySelectorAll('tbody > tr')).forEach((row,i)=>{if(!wanted.includes(rows[i]))row.remove();});
        const headers=Array.from(table.querySelectorAll('th')).map(th=>th.textContent).join(' ');
        const topics=new Set();
        if(/科目|初试|专业|计划|方向|招生|目录/.test(headers))topics.add('admissions');
        if(/分数|分布|成绩|复试线|最低|中位|均值|均分|最高|分位|单科|拟录取|录取人数|实录/.test(headers+' '+headingContext))topics.add('scores');
        if(/机考|机试|面试|复试规则|复试内容|复试安排|权重|复试科目/.test(headers+' '+title))topics.add('retest');
        if(/学费|费用|学制|住宿|培养|导师|实践|毕业|课程|学分|地点/.test(headers+' '+title))topics.add('training');
        if(!topics.size)topicFor(title,'sources').split(' ').forEach(t=>topics.add(t));
        // Unscoped multi-project material stays explicitly shared, never an
        // invented fact for the currently selected program.
        if(shared && group.owners.length===index.all.length && wanted.length===rows.length && index.all.length>1 &&
           rowOwners.every(ids=>ids.length===index.all.length)) {topics.clear();topics.add('sources');}
        const card=document.createElement('article');card.className='project-record';
        card.dataset.materialId=`table-${groupIndex}-${tableIndex}`;
        const h=document.createElement('h6');h.textContent=title;card.append(h);
        const label=document.createElement('p');label.className='evidence-scope';
        label.textContent=shared?'共用／比较材料：以各行学院、项目和人口口径为准':'本项目原表记录 · 保留年度科目与人口口径';card.append(label,copy,contextFold(group));
        for(const topic of topics)add(topic,card.cloneNode(true));
        hasTable=true;
      }
      const prose=group.nodes.filter(n=>!n.matches('.table-scroll,table'));
      const proseOwners=index.owners(prose.map(n=>n.textContent).join(' '),group.owners);
      if(prose.length && proseOwners.includes(project.id)) {
        const shared=proseOwners.length>1;
        let topics=topicFor(title,hasTable?'sources':'admissions').split(' ');
        if(shared && group.owners.length===index.all.length && index.all.length>1)topics=['sources'];
        const fold=contextFold(group,(shared?'共同说明 · ':'')+title);
        fold.dataset.materialId=`prose-${groupIndex}`;
        for(const topic of topics)add(topic,fold.cloneNode(true));
      }
    }
    for(const [topic,slot] of slots) {
      if(!counts.get(topic)) {
        const message=document.createElement('p');message.className='reading-gap';
        message.textContent=`本项目的“${topicNames[topic]}”尚未单独形成可归属资料。现有线索和限制已保留在结论及来源中；不能借同校其他项目补齐。`;
        slot.append(message);
      }
      const tab=project.querySelector(`[data-reading-view="${topic}"]`);
      if(tab && counts.get(topic))tab.dataset.materialCount=String(counts.get(topic));
      // One readable record first; further original tables remain one click away.
      Array.from(slot.children).filter(n=>n.matches('article')).slice(1).forEach(card=>{
        const fold=document.createElement('details');fold.className='additional-record';
        fold.dataset.materialId=card.dataset.materialId;delete card.dataset.materialId;
        const summary=document.createElement('summary');summary.textContent='更多记录 · '+card.querySelector('h6').textContent;
        card.before(fold);fold.append(summary,card);
      });
      const firstFold=slot.querySelector('details');
      if(!slot.querySelector('article') && firstFold && firstFold.textContent.length<1800)firstFold.open=true;
    }
  }
  function createProjectFlow(project) {
    const chapters=[], containers=[]; let index=0;
    function split(parent, inherited, skipTitle) {
      let chapter, topic=inherited, sawTitle=false;
      for (const node of Array.from(parent.childNodes)) {
        const element=node.nodeType===1?node:null;
        if (element?.matches('[data-reader-ui],summary')) { chapter=null;continue; }
        if (!element && !node.textContent.trim() && !chapter) continue;
        if (element?.matches('h4,h5,h6') && skipTitle && !sawTitle) { sawTitle=true;chapter=null;continue; }
        if (element?.matches('details,.research-direction')) {
          chapter=null; containers.push(element);
          const heading=element.querySelector('summary,h4,h5,h6');
          const fallback=element.matches('.research-direction')?'admissions':inherited==='overview'?'sources':inherited;
          const base=topicFor(heading?.textContent || '',fallback);
          split(element,base,element.matches('.research-direction'));
          if(inherited==='overview') topic='sources';
          continue;
        }
        if (element?.matches('a[id]') || element?.matches('p') && element.querySelector('a[id]') && !element.textContent.trim()) { chapter=null;continue; }
        if (element?.matches('h4,h5,h6')) { topic=topicFor(element.textContent,inherited==='overview'?'sources':inherited);chapter=null; }
        if (element?.matches('.project-verdict')) { topic='overview';chapter=null; }
        if (!chapter) {
          chapter=document.createElement('div');chapter.className='reading-chapter';
          chapter.dataset.readingTopic=topic;chapter.id=`chapter-${project.id}-${++index}`;
          node.before(chapter);chapters.push(chapter);
        }
        chapter.append(node);
      }
    }
    split(project,'overview',true);
    if(project.querySelector('.project-source-selector')) {
      for(const topic of Object.keys(topicNames).filter(t=>t!=='overview')) {
        const chapter=document.createElement('div');chapter.className='reading-chapter project-excerpts';
        chapter.dataset.readingTopic=topic;chapter.dataset.excerptTopic=topic;
        chapter.setAttribute('data-reader-ui','true');chapter.id=`chapter-${project.id}-${++index}`;
        project.append(chapter);chapters.push(chapter);
      }
    }
    const meaningful=chapters.filter(ch=>ch.textContent.trim() || ch.matches('.project-excerpts'));
    const nav=document.createElement('nav');nav.className='reading-tabs';
    nav.setAttribute('data-reader-ui','true');nav.setAttribute('aria-label','本项目阅读栏目');
    for (const [key,label] of Object.entries({...topicNames,all:'完整资料'})) {
      if (key!=='all' && !meaningful.some(ch=>ch.dataset.readingTopic.split(' ').includes(key))) continue;
      const link=document.createElement('a');link.id=`view-${project.id}-${key}`;
      link.href=`#${link.id}`;link.dataset.readingView=key;link.textContent=label;nav.append(link);
    }
    const first=project.querySelector('h4,h5,h6');if(first)first.after(nav);else project.prepend(nav);
    const directions=Array.from(project.querySelectorAll('.research-direction'));
    if (directions.length) {
      const chooser=document.createElement('nav');chooser.className='direction-choices';
      chooser.setAttribute('data-reader-ui','true');chooser.setAttribute('aria-label','选择本项目研究方向');
      const label=document.createElement('span');label.textContent='研究方向';chooser.append(label);
      const all=document.createElement('a');all.id=`directions-${project.id}`;all.href=`#${all.id}`;
      all.dataset.directionView='all';all.textContent='全部';chooser.append(all);
      for(const direction of directions) {
        const link=document.createElement('a');link.href=`#${direction.id}`;
        link.dataset.directionView=direction.id;link.textContent=direction.dataset.directionTitle;chooser.append(link);
      }
      nav.before(chooser);
    }
    readingScopes.set(project,{nav,chapters,containers});
    const initial=meaningful.some(ch=>ch.dataset.readingTopic==='overview')?'overview':meaningful[0]?.dataset.readingTopic.split(' ')[0];
    setReadingTopic(project,initial || 'all');
  }
  content.querySelectorAll('.admission-project').forEach(createProjectFlow);
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
    if (!group || !panel.querySelector('.admission-layout')) return;
    const direction = selected?.closest('.research-direction');
    const project = selected?.closest('.admission-project');
    if(project) hydrateProject(project);
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
    if (active.querySelector('.admission-layout')) {
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
    const project = element.closest('.admission-project');
    let chapter = element.closest('.reading-chapter');
    if (!chapter && element.matches('.research-direction,summary')) {
      const container=element.matches('summary')?element.parentElement:element;
      chapter=Array.from(container.querySelectorAll('.reading-chapter')).find(ch=>ch.textContent.trim());
    }
    if (!chapter && project && element.matches('a[id]:not([data-reading-view])')) {
      const anchor = element.parentElement?.matches('p') && !element.parentElement.textContent.trim() ? element.parentElement : element;
      for (let next=anchor.nextElementSibling;next;next=next.nextElementSibling) {
        if (next.matches('.reading-chapter') && next.textContent.trim()) { chapter=next;break; }
        if (next.matches('details,.research-direction')) { chapter=Array.from(next.querySelectorAll('.reading-chapter')).find(ch=>ch.textContent.trim());break; }
      }
    }
    if (project && element.dataset.directionView==='all') {
      delete project.dataset.readingDirection;
      setReadingTopic(project,project.dataset.readingTopic || 'overview');
    }
    else if (project && element.dataset.readingView) {
      if(element.dataset.readingView==='all') delete project.dataset.readingDirection;
      setReadingTopic(project, element.dataset.readingView);
    }
    else if (project && chapter) {
      const direction=element.closest('.research-direction');
      if(direction) project.dataset.readingDirection=direction.id;
      setReadingTopic(project, chapter.dataset.readingTopic.split(' ')[0]);
    }
    else if (project && element === project) {
      delete project.dataset.readingDirection;
      const flow=readingScopes.get(project);
      const initial=flow?.chapters.find(ch=>ch.dataset.readingTopic==='overview' && ch.textContent.trim());
      if (flow) setReadingTopic(project,initial?'overview':flow.chapters.find(ch=>ch.textContent.trim())?.dataset.readingTopic.split(' ')[0] || 'all');
    }
    project?.querySelectorAll('[data-direction-view]').forEach(link=>{
      if(link.dataset.directionView===(project.dataset.readingDirection || 'all')) link.setAttribute('aria-current','true');
      else link.removeAttribute('aria-current');
    });
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
    if (visibleScope()) setReadingTopic(visibleScope(), 'all');
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
    visibleScope()?.querySelectorAll('.reading-chapter,.research-direction,details').forEach(chapter => { chapter.dataset.printHidden=String(chapter.hidden); chapter.hidden=false; });
    const seen=new Set();
    visibleScope()?.querySelectorAll('[data-material-id]').forEach(node=>{
      if(!node.hasAttribute('data-print-hidden'))node.dataset.printHidden=String(node.hidden);
      node.hidden=seen.has(node.dataset.materialId);seen.add(node.dataset.materialId);
    });
  });
  window.addEventListener('afterprint', () => {
    content.querySelectorAll('[data-print-hidden]').forEach(chapter=>{chapter.hidden=chapter.dataset.printHidden==='true';delete chapter.dataset.printHidden;});
    content.querySelectorAll('details[data-print-open]').forEach(detail => { detail.open = detail.dataset.printOpen === 'true'; delete detail.dataset.printOpen; });
  });
})();
