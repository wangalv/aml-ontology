/* Small DOM helpers shared by every view. Text is always inserted as text nodes, never as HTML. */
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'style') Object.assign(e.style, v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return e;
}

function inline(text) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    out.push(t.startsWith('**') ? h('strong', {}, t.slice(2, -2)) : h('code', {}, t.slice(1, -1)));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/* The AMLTRIX texts use paragraphs, "- " bullets and **bold**; nothing else. */
function md(text) {
  const box = h('div', { class: 'md' });
  let list = null, para = [];
  const flush = () => { if (para.length) { box.append(h('p', {}, inline(para.join(' ')))); para = []; } };
  for (const raw of String(text || '').split('\n')) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      flush();
      if (!list) { list = h('ul'); box.append(list); }
      list.append(h('li', {}, inline(bullet[1])));
    } else if (!line.trim()) { flush(); list = null; }
    else { list = null; para.push(line.trim()); }
  }
  flush();
  return box;
}

/* replaceChildren that skips null and false, which it would otherwise print as text */
function fill(el, ...kids) { el.replaceChildren(...kids.flat(Infinity).filter((k) => k != null && k !== false)); }

function badge(color, text) { return h('span', { class: 'badge ' + color }, text); }
function caption(text) { return h('div', { class: 'caption' }, text); }

function shorten(text, n) {
  const t = String(text || '').replace(/\s+/g, ' ').trim();
  if (t.length <= n) return t;
  return t.slice(0, n - 5).replace(/\s+\S*$/, '') + ' [...]';
}

function wrap(text, width) {
  const lines = [];
  let line = '';
  for (const word of String(text).split(/\s+/)) {
    if (line && (line + ' ' + word).length > width) { lines.push(line); line = word; }
    else line = line ? line + ' ' + word : word;
  }
  if (line) lines.push(line);
  return lines.join('\n');
}

/* Buttons that behave like st.pills: one is selected, and the caller re-renders only that section. */
function pills(options, selected, onChange) {
  const box = h('div', { class: 'pills' });
  for (const [id, label] of options) {
    box.append(h('button', { class: 'pill' + (id === selected ? ' on' : ''), type: 'button', onclick: () => onChange(id) }, label));
  }
  return box;
}

/* rows: [{key, cells: [string | Node]}]; clicking a row calls onSelect(key). */
function dataTable(columns, rows, opts) {
  opts = opts || {};
  const head = h('tr', {}, columns.map((c) => h('th', {}, c)));
  const body = rows.map((r) => h('tr', {
    'data-key': r.key,
    class: (opts.onSelect ? 'click ' : '') + (r.key === opts.selected ? 'sel' : ''),
    onclick: opts.onSelect ? () => opts.onSelect(r.key) : null,
  }, r.cells.map((c) => h('td', {}, c))));
  const wrapEl = h('div', { class: 'tbl-wrap', style: { maxHeight: (opts.maxHeight || 420) + 'px' } },
    h('table', {}, h('thead', {}, head), h('tbody', {}, body)));
  return wrapEl;
}

function jsonBlock(obj, height) {
  return h('pre', { style: { maxHeight: (height || 360) + 'px' } }, JSON.stringify(obj, null, 2));
}

function legendEntry(color, title, detail, text, code) {
  return h('div', { class: 'legend-item' },
    h('span', { class: 'sw', style: { background: color } }),
    h('div', {}, h('b', {}, title), ' ', h('span', { class: 'muted' }, detail || ''), h('br'),
      h('span', { class: 'tx' }, text, code ? [h('br'), h('code', {}, code)] : null)));
}

/* vis-network keeps one network per slot, and needs its container in the page when it starts. */
const NETS = {};
function dropNet(slot) { if (NETS[slot]) { NETS[slot].destroy(); delete NETS[slot]; } }
function dropAllNets() { Object.keys(NETS).forEach(dropNet); }

/* Run fn once el is in the page. A view is built before it is attached, so wait for the DOM to change
   (a MutationObserver, which also runs while the tab is in the background, unlike requestAnimationFrame). */
const PENDING = [];
function flushPending() {
  for (let i = PENDING.length - 1; i >= 0; i--) {
    if (PENDING[i].el.isConnected) PENDING.splice(i, 1)[0].fn();
  }
  if (PENDING.length > 100) PENDING.splice(0, PENDING.length - 100);
}
new MutationObserver(flushPending).observe(document.documentElement, { childList: true, subtree: true });
function whenConnected(el, fn) {
  if (el.isConnected) fn();
  else PENDING.push({ el, fn });
}

function nodeColor(c) {
  return { background: c, border: 'rgba(0,0,0,.35)', highlight: { background: c, border: '#000' }, hover: { background: c, border: '#000' } };
}

function graphOptions(overrides) {
  const repulsion = Object.assign({ nodeDistance: 170, centralGravity: 0.12, springLength: 200, springConstant: 0.04 }, overrides || {});
  return {
    autoResize: true,
    physics: { enabled: true, solver: 'repulsion', repulsion, stabilization: { iterations: 250 } },
    interaction: { hover: true, zoomView: true, dragNodes: true, tooltipDelay: 150 },
    edges: { arrows: { to: { enabled: true, scaleFactor: 0.6 } }, smooth: { type: 'dynamic' }, color: { color: '#9AA0A6' } },
    nodes: { shape: 'box', margin: 8 },
  };
}

function makeNet(slot, el, nodes, edges, options, onClick) {
  dropNet(slot);
  const net = new vis.Network(el, { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) }, options);
  if (onClick) net.on('click', (p) => { if (p.nodes.length) onClick(p.nodes[0]); });
  NETS[slot] = net;
  return net;
}

function setNet(net, nodes, edges) {
  net.setData({ nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) });
}

/* Mark wording that also appears in the AML typology text the agent was given: runs of four or more words in a row,
   ignoring runs made up of little words. A rough marker of context in use, not a judgement of the text. */
const STOP = new Set('the a an of and or to in on for with by from at as is are was were be been that this it its into than then not no any all'.split(' '));
function wordsOf(text) {
  const out = [], re = /[A-Za-z0-9']+/g;
  let m;
  while ((m = re.exec(text))) out.push({ w: m[0].toLowerCase(), start: m.index, end: m.index + m[0].length });
  return out;
}
function ngramSet(texts, n) {
  const set = new Set();
  for (const t of texts) {
    const ws = wordsOf(t).map((x) => x.w);
    for (let i = 0; i + n <= ws.length; i++) {
      const g = ws.slice(i, i + n);
      if (g.filter((w) => !STOP.has(w)).length >= 2) set.add(g.join(' '));
    }
  }
  return set;
}
const GRAM = 4; // words in a row that count as shared wording
function highlight(text, grams, n) {
  n = n || GRAM;
  const ws = wordsOf(text), flags = new Array(ws.length).fill(false);
  for (let i = 0; i + n <= ws.length; i++) {
    if (grams.has(ws.slice(i, i + n).map((x) => x.w).join(' '))) for (let j = i; j < i + n; j++) flags[j] = true;
  }
  const nodes = [];
  let pos = 0, i = 0;
  while (i < ws.length) {
    if (!flags[i]) { i++; continue; }
    let j = i;
    while (j + 1 < ws.length && flags[j + 1]) j++;
    if (ws[i].start > pos) nodes.push(text.slice(pos, ws[i].start));
    nodes.push(h('mark', {}, text.slice(ws[i].start, ws[j].end)));
    pos = ws[j].end;
    i = j + 1;
  }
  if (pos < text.length) nodes.push(text.slice(pos));
  return { nodes, hit: flags.some(Boolean) };
}
