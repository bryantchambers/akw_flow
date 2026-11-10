'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { resources: [], category: 'All resources', query: '' };
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
function link(label, url, cls) {
  const a = el('a', cls, label);
  a.href = url; a.target = '_blank'; a.rel = 'noopener';
  return a;
}
function size(bytes) { return bytes >= 1e6 ? (bytes / 1e6).toFixed(1) + ' MB' : Math.round(bytes / 1000) + ' KB'; }
function renderStats(stats) {
  const items = [[stats.pdfs, 'PDF documents', 'Papers, supplement & proceedings'],
    [stats.supplements, 'DOCX supplement', 'Publisher supporting information'],
    [stats.source_archives, 'Source-code archive', 'Feature extraction · not hydraulics'],
    [stats.context_datasets || 0, 'Modern GIS context datasets', 'Historical GIS / LiDAR still needed'],
    [stats.hydraulic_projects, 'Runnable hydraulic projects', 'Acquisition needed']];
  $('#stats').replaceChildren(...items.map(([value, label, note], index) => {
    const card = el('div', 'stat' + (index >= 3 ? ' missing' : ''));
    card.append(el('div', 'stat-value', String(value)), el('div', 'stat-label', label), el('small', '', note));
    return card;
  }));
}
function resourceCard(r) {
  const card = el('article', 'resource');
  const top = el('div', 'card-top'); top.append(el('span', 'category', r.category), el('span', 'kind', r.kind));
  card.append(top, el('h3', '', r.title), el('p', 'citation', r.citation), el('p', 'description', r.description), el('p', 'scope', r.scope));
  const details = el('details'); details.append(el('summary', '', 'Purpose & limitations'));
  for (const [label, text] of [['Supports', r.supports], ['Keep in mind', r.limitation]]) {
    const p = el('p'); p.append(el('b', '', label), document.createTextNode(text)); details.append(p);
  }
  card.append(details);
  const foot = el('div', 'card-bottom');
  const a = r.artifact;
  if (a.available) {
    const kind = a.path.endsWith('.pdf') ? 'Open PDF' : a.path.endsWith('.html') ? 'Download reference HTML' : a.path.endsWith('.docx') ? 'Download DOCX' : a.path.endsWith('.tif') ? 'Download terrain' : a.path.endsWith('.geojson') ? 'Download GIS' : a.path.endsWith('.demi2') ? 'Download raw DEM' : 'Download code';
    foot.append(link(kind + ' ↗', a.url, 'file-link'), el('span', 'file-size', (a.pages ? a.pages + ' pp · ' : '') + size(a.bytes)));
  } else foot.append(el('span', 'file-size', 'File not acquired'));
  if (a.source_url) foot.append(link('Source ↗', a.source_url, 'source-link'));
  card.append(foot);
  if(r.viewer_url)card.append(link('Open 5 m terrain preview ↗',r.viewer_url,'file-link related'));
  if (r.related_artifacts.some(a => a.available)) {
    const related = el('div', 'related');
    for (const a of r.related_artifacts.filter(a => a.available)) related.append(link(a.path.endsWith('.zip') ? 'Related source code ↗' : 'Supplement ↗', a.url));
    card.append(related);
  }
  return card;
}
function renderResources() {
  const query = state.query.trim().toLowerCase();
  const resources = state.resources.filter(r => (state.category === 'All resources' || r.category === state.category) &&
    [r.title, r.citation, r.category, r.scope, r.kind, r.description, r.supports, r.limitation].join(' ').toLowerCase().includes(query));
  $('#resources').replaceChildren(...resources.map(resourceCard));
  $('#result-count').textContent = resources.length + ' of ' + state.resources.length + ' resources';
  $('#empty').hidden = resources.length > 0;
  for (const b of $('#filters').children) { const selected = b.textContent === state.category; b.classList.toggle('selected', selected); b.setAttribute('aria-pressed', String(selected)); }
}
function renderNeeds(needs) {
  $('#needs-list').replaceChildren(...needs.map(n => {
    const row = el('details', 'need');
    const summary = el('summary');
    summary.append(el('span', 'priority ' + (n.priority === 'Critical' ? 'critical' : n.priority === 'Next stage' ? 'next' : ''), n.priority), el('span', 'need-title', n.title), el('span', 'need-state', n.state));
    const body = el('div', 'need-body');
    for (const [label, text, cls] of [['The missing resource', n.description, ''], ['What it unlocks', n.why, ''], ['What to request', n.request, 'request']]) {
      const block = el('div', cls); block.append(el('h4', '', label), el('p', '', text)); body.append(block);
    }
    const owner = el('div', 'need-owner', 'Route: ' + n.owner + ' ');
    if (n.source) owner.append(link('Institution / source ↗', n.source));
    body.append(owner); row.append(summary, body); return row;
  }));
}
async function init() {
  try {
    const response = await fetch('/api/catalog');
    if (!response.ok) throw new Error('Catalog request failed');
    const data = await response.json(); state.resources = data.resources;
    renderStats(data.stats); $('#nav-count').textContent = data.resources.length;
    $('#snapshot').textContent = new Date(data.updated + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    const categories = ['All resources', ...new Set(data.resources.map(r => r.category))];
    $('#filters').replaceChildren(...categories.map(category => {
      const b = el('button', '', category); b.type = 'button'; b.addEventListener('click', () => { state.category = category; renderResources(); }); return b;
    }));
    renderResources(); renderNeeds(data.needs);
    $('#search').addEventListener('input', e => { state.query = e.target.value; renderResources(); });
    $('#reset').addEventListener('click', () => { state.query = ''; state.category = 'All resources'; $('#search').value = ''; renderResources(); });
    const sections = [...document.querySelectorAll('main>section')];
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        for (const a of document.querySelectorAll('nav a')) a.classList.toggle('active', a.hash === '#' + entry.target.id);
      }
    }, { rootMargin: '-5% 0px -65% 0px', threshold: 0 });
    sections.forEach(s => observer.observe(s));
  } catch (error) {
    $('#stats').replaceChildren(el('p', '', 'The catalog could not be loaded. Reload the page or open the collection inventory.'));
    $('#resources').append(link('Open the text inventory ↗', '/assets/README.md', 'file-link'));
    console.error(error);
  }
}
init();
