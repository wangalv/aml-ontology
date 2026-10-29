/* AML typology box (the AMLTRIX technique browser) and the Risk indicators box. Mirrors portal/ontology_tab.py. */
const STRENGTH_COLOR = { strong: '#2E9E6B', medium: '#E8C34D', weak: '#9AA0A6' };
const STRENGTH_ORDER = { strong: 0, medium: 1, weak: 2 };
/* field on the technique, label, ontology predicate, direction, node colour.
   "in": entity -> technique (a Mitigation mitigates a Technique); "out": technique -> entity. */
const REL = [
  ['tactics', 'Tactic', 'isAchievedBy', 'in', '#B39DDB'],
  ['mitigations', 'Mitigation', 'mitigates', 'in', '#81C784'],
  ['actors', 'Actor', 'engagesIn', 'in', '#64B5F6'],
  ['instruments', 'Value instrument', 'isUsedBy', 'in', '#FFB74D'],
  ['products', 'Product / service', 'isExploitedBy', 'in', '#F48FB1'],
  ['risks', 'Risk type', 'isAssociatedWith', 'in', '#E57373'],
  ['dataSources', 'Data source', 'isIdentifiedIn', 'out', '#4DB6AC'],
];
const ENTITY = new Set(REL.map((r) => r[0]));
const REL_LABEL = Object.fromEntries(REL.map((r) => [r[0], r[1]]));
const LIST_TABS = [
  ['mitigations', 'Mitigations'], ['dataSources', 'Data sources'], ['actors', 'Actors'],
  ['instruments', 'Instruments'], ['products', 'Products & services'], ['risks', 'Risk types'],
];
const GRAPH_LIMIT = 5, EXPAND_LIMIT = 8, GRAPH_H = 560, TYP_H = 420;
const NEIGHBOR_COLOR = '#FFB199', CENTER_COLOR = '#F0784B', SUB_COLOR = '#90A4AE', INDICATOR_COLOR = '#FFF59D', MORE_COLOR = '#444444';
const TACTIC_COLOR = '#B39DDB';
const LEGEND_TEXT = {
  tactics: 'The goal the technique serves, e.g. Placement, Layering, Integration.',
  mitigations: 'A control that reduces the risk of the technique.',
  actors: 'A party that engages in the technique.',
  instruments: 'An asset or instrument used to move or store value.',
  products: 'A financial product or service the technique exploits.',
  risks: 'The kind of risk the technique is associated with.',
  dataSources: 'A record where evidence of the technique can be found.',
  subs: 'A more specific variant of this technique.',
  indicators: 'Observable red-flag signals (full list in the Risk indicators box).',
};

const O = { query: '', tactics: new Set(), typology: 'All', subs: false, sel: null, focus: null, expanded: [], node: null, section: 'rel' };

function tacticNames(tech) { return tech.tactics.map((x) => DATA.snap.dimensions.tactics[x.ref].name); }

function mappingIndex() {
  const idx = {};
  for (const t of DATA.tmap.typologies) for (const m of t.techniques) (idx[m.id] ||= []).push([t.name, m]);
  return idx;
}

function techniquesUsing(field, ref, exclude) {
  const snap = DATA.snap;
  return Object.keys(snap.techniques)
    .filter((k) => k !== exclude && snap.techniques[k][field].some((x) => x.ref === ref))
    .sort((a, b) => (snap.techniques[a].id < snap.techniques[b].id ? -1 : 1));
}

function buildTable() {
  const snap = DATA.snap, mapped = mappingIndex();
  const columns = ['ID', 'Technique'];
  if (O.subs) columns.push('Level');
  columns.push('Tactics', 'Sub-techniques', 'Indicators', 'Mitigations', 'Data sources', 'Portal typologies');
  if (O.typology !== 'All') columns.push('Match', 'Why');
  const out = [];
  for (const [key, t] of Object.entries(snap.techniques)) {
    if (t.kind === 'subtechnique' && !O.subs) continue;
    const names = tacticNames(t);
    if (O.tactics.size && !names.some((n) => O.tactics.has(n))) continue;
    if (O.query && ![t.id, t.name, ...t.alt].join(' ').toLowerCase().includes(O.query)) continue;
    const hits = mapped[t.id] || [];
    const cells = [t.id, t.name];
    if (O.subs) cells.push(t.kind === 'subtechnique' ? 'Sub-technique' : 'Technique');
    cells.push(names.join(', '), t.subs.length, t.indicators.length, t.mitigations.length, t.dataSources.length,
      hits.map(([n, m]) => `${n} (${m.strength})`).join(', '));
    let rank = 0;
    if (O.typology !== 'All') {
      const hit = hits.find(([n]) => n === O.typology);
      if (!hit) continue;
      cells.push(hit[1].strength, hit[1].basis);
      rank = STRENGTH_ORDER[hit[1].strength];
    }
    out.push({ key, cells, rank, id: t.id });
  }
  out.sort((a, b) => a.rank - b.rank || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return { columns, rows: out };
}

/* ---------- the typology -> technique -> tactic graph ---------- */
function typologyGraph(typology) {
  const snap = DATA.snap;
  const font = { size: 12, color: '#111111' };
  const edgeFont = { size: 10, color: '#9AA0A6', strokeWidth: 0, align: 'middle' };
  const nodes = [{ id: 'typ', label: wrap(typology.name, 18), color: nodeColor(CENTER_COLOR), x: 0, y: 0, fixed: true,
    title: typology.demo_signal, font: { size: 15, color: '#111111' } }];
  const edges = [], seen = new Set();
  for (const m of typology.techniques) {
    const tech = snap.techniques[m.id];
    const color = STRENGTH_COLOR[m.strength];
    nodes.push({ id: m.id, label: `${m.id}\n${wrap(tech.name, 22)}`, color: nodeColor(color), title: `${m.strength} match: ${m.basis}`, font });
    edges.push({ from: 'typ', to: m.id, color: { color }, label: m.strength, font: { ...edgeFont, color }, width: 2 });
    for (const x of tech.tactics) {
      const tid = 'tac:' + x.ref;
      if (!seen.has(tid)) {
        seen.add(tid);
        const tac = snap.dimensions.tactics[x.ref];
        nodes.push({ id: tid, label: tac.name, color: nodeColor(TACTIC_COLOR), title: shorten(tac.short || tac.definition, 400), font });
      }
      edges.push({ from: m.id, to: tid, color: { color: '#9AA0A6' } });
    }
  }
  const graphEl = h('div', { class: 'graph', style: { height: TYP_H + 'px' } });
  const legend = h('div', { class: 'legend' }, h('b', {}, 'Legend'), h('div', { style: { height: '8px' } }),
    legendEntry(CENTER_COLOR, typology.name, 'typology', 'A pattern the portal detects, e.g. via a rule or graph analysis.'),
    [['strong', "AMLTRIX's definition describes the behaviour the rule detects."],
     ['medium', 'Overlapping behaviour, but AMLTRIX frames it differently.'],
     ['weak', 'Related context only; needs extra evidence.']].map(([s, text]) => {
      const n = typology.techniques.filter((m) => m.strength === s).length;
      return n ? legendEntry(STRENGTH_COLOR[s], s[0].toUpperCase() + s.slice(1) + ' match', `(${n})`, 'Technique. ' + text) : null;
    }),
    legendEntry(TACTIC_COLOR, 'Tactic', `(${seen.size})`, 'The goal the technique serves, e.g. Layering.'));
  const root = h('div', {}, h('div', { class: 'cols2 typg' }, graphEl, legend),
    caption('Drag nodes, scroll to zoom, hover a node for the reason behind the match.'));
  whenConnected(graphEl, () => makeNet('typ', graphEl, nodes, edges, graphOptions(), null));
  return root;
}

/* ---------- the relationship graph of one technique ---------- */
function nodeDetails(key, node) {
  const snap = DATA.snap, tech = snap.techniques[key], dims = snap.dimensions;
  const i = (node || '').indexOf(':');
  const prefix = i < 0 ? node || '' : node.slice(0, i), ref = i < 0 ? '' : node.slice(i + 1);
  const box = h('div');
  if (prefix in REL_LABEL && dims[prefix][ref]) {
    const e = dims[prefix][ref];
    box.append(caption(REL_LABEL[prefix]), h('div', {}, h('strong', {}, e.name), ' ', h('code', {}, e.id)));
    if (e.url) box.append(h('p', {}, h('a', { href: e.url, target: '_blank', rel: 'noopener' }, 'AMLTRIX page')));
    box.append(md(e.definition || e.short));
    const note = (tech[prefix].find((x) => x.ref === ref) || {}).note;
    if (note) box.append(h('p', {}, h('strong', {}, `Why it applies to ${tech.id}`)), md(note));
    const users = techniquesUsing(prefix, ref, null);
    box.append(caption(`Used by ${users.length} techniques and sub-techniques`));
    box.append(h('details', {}, h('summary', {}, 'List them'),
      h('ul', {}, users.slice(0, 60).map((tk) => h('li', {}, h('code', {}, snap.techniques[tk].id), ' ', snap.techniques[tk].name))),
      users.length > 60 ? caption(`... and ${users.length - 60} more`) : null));
  } else if ((prefix === 'subs' || prefix === 'tech') && snap.techniques[ref]) {
    const t = snap.techniques[ref];
    box.append(caption(t.kind === 'subtechnique' ? 'Sub-technique' : 'Technique'),
      h('div', {}, h('strong', {}, t.name), ' ', h('code', {}, t.id)),
      h('div', {}, tacticNames(t).map((n) => badge('violet', n))));
    if (t.url) box.append(h('p', {}, h('a', { href: t.url, target: '_blank', rel: 'noopener' }, 'AMLTRIX page')));
    box.append(md(t.definition || t.short),
      caption(`${t.subs.length} sub-techniques · ${t.indicators.length} indicators · ${t.mitigations.length} mitigations · ${t.dataSources.length} data sources`));
    if (ref !== key) {
      box.append(h('button', { class: 'btn', type: 'button', onclick: () => {
        O.focus = ref; O.expanded = []; O.node = null; O.section = 'rel'; refreshDetail();
      } }, 'Open this technique'));
    }
  } else if (node === 'indicators') {
    box.append(h('p', {}, h('strong', {}, `${tech.indicators.length} indicators of ${tech.id}`)),
      h('ul', {}, tech.indicators.map((ind) => h('li', {}, h('code', {}, ind), ' ', snap.indicators[ind]))));
  } else {
    box.append(h('p', {}, h('strong', {}, `${tech.id} · ${tech.name}`)), md(tech.short || tech.definition),
      caption('Click a node in the graph to see its details here.'));
  }
  return box;
}

function relView(key) {
  const snap = DATA.snap, tech = snap.techniques[key], dims = snap.dimensions;
  const detailEl = h('div', { class: 'scroll', style: { height: GRAPH_H + 'px' } });
  const graphEl = h('div', { class: 'graph', style: { height: GRAPH_H + 'px' } });
  const legendEl = h('div', { class: 'legend', style: { height: GRAPH_H + 'px' } });
  const footEl = h('div');
  const root = h('div', {}, h('div', { class: 'cols3 rel' }, detailEl, graphEl, legendEl), footEl);
  let net = null;

  function build() {
    const font = { size: 12, color: '#111111' };
    const edgeFont = { size: 10, color: '#9AA0A6', strokeWidth: 0, align: 'middle' };
    const nodes = [{ id: 'center', label: `${tech.id}\n${wrap(tech.name, 22)}`, color: nodeColor(CENTER_COLOR),
      title: shorten(tech.short || tech.definition, 400), x: 0, y: 0, fixed: true, font: { size: 15, color: '#111111' } }];
    const edges = [], addedTech = new Set();
    const techNode = (tk) => {
      if (addedTech.has(tk)) return;
      addedTech.add(tk);
      const t = snap.techniques[tk];
      nodes.push({ id: 'tech:' + tk, label: `${t.id}\n${wrap(t.name, 22)}`, color: nodeColor(NEIGHBOR_COLOR), font,
        title: shorten(t.short || t.definition, 300) + ' (click to open this technique)' });
    };
    const addGroup = (prefix, items, predicate, direction, color, field) => {
      const limit = O.expanded.includes(prefix + ':more') ? items.length : GRAPH_LIMIT;
      items.slice(0, limit).forEach(([ref, label, tip], i) => {
        const nid = `${prefix}:${ref}`, isOpen = O.expanded.includes(nid);
        const hint = field ? ' (click to see the other techniques that use this)' : ' (click to open this sub-technique)';
        nodes.push({ id: nid, label: wrap(label, 24), color: nodeColor(color), title: tip + hint, font, borderWidth: isOpen ? 4 : 1 });
        const [from, to] = direction === 'in' ? [nid, 'center'] : ['center', nid];
        edges.push({ from, to, label: i === 0 ? predicate : undefined, font: edgeFont });
        if (field && isOpen) {
          const others = techniquesUsing(field, ref, key);
          others.slice(0, EXPAND_LIMIT).forEach((tk, j) => {
            techNode(tk);
            const [f2, t2] = direction === 'in' ? [nid, 'tech:' + tk] : ['tech:' + tk, nid];
            edges.push({ from: f2, to: t2, color: { color: '#C9A27A' }, label: j === 0 ? predicate : undefined, font: edgeFont });
          });
          if (others.length > EXPAND_LIMIT) {
            nodes.push({ id: nid + ':rest', label: `+${others.length - EXPAND_LIMIT} more techniques`, color: nodeColor(MORE_COLOR),
              title: 'Use the table search to find them', font: { size: 11, color: '#DDDDDD' } });
            edges.push({ from: nid, to: nid + ':rest', color: { color: '#666666' }, dashes: true });
          }
        }
      });
      const extra = items.length - limit;
      if (extra > 0) {
        const nid = prefix + ':more';
        nodes.push({ id: nid, label: `+${extra} more`, color: nodeColor(MORE_COLOR), title: 'Click to show all', font: { size: 11, color: '#DDDDDD' } });
        const [from, to] = direction === 'in' ? [nid, 'center'] : ['center', nid];
        edges.push({ from, to, color: { color: '#666666' }, dashes: true });
      }
    };
    for (const [field, label, predicate, direction, color] of REL) {
      const items = tech[field].map((x) => [x.ref, dims[field][x.ref].name, shorten(x.note || dims[field][x.ref].short || label, 400)]);
      addGroup(field, items, predicate, direction, color, field);
    }
    const subs = tech.subs.map((k) => [k, snap.techniques[k].id + ' ' + snap.techniques[k].name,
      shorten(snap.techniques[k].short || snap.techniques[k].definition, 400)]);
    addGroup('subs', subs, 'broader', 'in', SUB_COLOR, null);
    if (tech.indicators.length) {
      nodes.push({ id: 'indicators', label: `${tech.indicators.length} indicators`, color: nodeColor(INDICATOR_COLOR),
        title: 'See the Risk indicators box for the full list', font });
      edges.push({ from: 'center', to: 'indicators', label: 'isIndicatedBy', font: edgeFont });
    }
    return { nodes, edges, addedTech };
  }

  function paint(first) {
    const g = build();
    if (first) {
      whenConnected(graphEl, () => {
        net = makeNet('rel', graphEl, g.nodes, g.edges,
          graphOptions({ nodeDistance: 120, centralGravity: 0.25, springLength: 130, springConstant: 0.05 }), onNode);
      });
    } else if (net) setNet(net, g.nodes, g.edges);
    detailEl.replaceChildren(nodeDetails(key, O.node));
    const legend = [h('b', {}, 'Legend'), h('div', { style: { height: '8px' } }),
      legendEntry(CENTER_COLOR, tech.id, 'selected', 'The technique you are looking at.')];
    for (const [field, label, predicate, direction, color] of REL) {
      const n = tech[field].length;
      if (!n) continue;
      const arrow = direction === 'in' ? `${label} → ${predicate} → Technique` : `Technique → ${predicate} → ${label}`;
      legend.push(legendEntry(color, label, `(${O.expanded.includes(field + ':more') ? n : Math.min(n, GRAPH_LIMIT)} of ${n})`, LEGEND_TEXT[field], arrow));
    }
    if (tech.subs.length) legend.push(legendEntry(SUB_COLOR, 'Sub-technique', `(${tech.subs.length})`, LEGEND_TEXT.subs, 'Sub-technique → broader → Technique'));
    if (tech.indicators.length) legend.push(legendEntry(INDICATOR_COLOR, 'Indicators', `(${tech.indicators.length})`, LEGEND_TEXT.indicators, 'Technique → isIndicatedBy → Indicator'));
    if (g.addedTech.size) legend.push(legendEntry(NEIGHBOR_COLOR, 'Other technique', `(${g.addedTech.size})`, 'Shares an expanded node with this technique. Click it for details.'));
    legend.push(legendEntry(MORE_COLOR, '+N more', '', 'Hidden items. Click to show them all.'));
    legendEl.replaceChildren(...legend);
    fill(footEl,
      caption('Click a node to see its details on the left. Entities (mitigation, actor, ...) also expand to the other techniques that use ' +
        'them, and "+N more" shows the rest. Drag to move, scroll to zoom, hover for a description.'),
      O.expanded.length ? h('button', { class: 'btn', type: 'button', onclick: () => { O.expanded = []; paint(false); } }, 'Collapse expanded nodes') : null);
  }

  function onNode(id) {
    if (id === 'center') O.node = null;
    else if (id.endsWith(':rest')) return;
    else if (id.endsWith(':more')) { if (!O.expanded.includes(id)) O.expanded.push(id); }
    else {
      O.node = id;
      if (ENTITY.has(id.split(':')[0]) && !O.expanded.includes(id)) O.expanded.push(id);
    }
    paint(false);
  }

  paint(true);
  return root;
}

/* ---------- one technique ---------- */
function techDetail(key) {
  const snap = DATA.snap, tech = snap.techniques[key], dims = snap.dimensions;
  const root = h('div');
  root.append(h('h3', {}, `${tech.id} · ${tech.name}`),
    h('div', {}, tacticNames(tech).map((n) => badge('violet', n)), ' ',
      tech.url ? h('a', { href: tech.url, target: '_blank', rel: 'noopener' }, 'AMLTRIX page') : null));
  if (tech.kind === 'subtechnique') {
    const parent = snap.techniques[tech.parent];
    root.append(caption(`Sub-technique of ${parent.id} · ${parent.name}`));
  }
  if (tech.alt.length) root.append(caption('Also known as: ' + tech.alt.join(', ')));
  const mapped = DATA.tmap.typologies.flatMap((t) => t.techniques.filter((m) => m.id === tech.id).map((m) => [t.name, m]));
  if (mapped.length) root.append(h('p', {}, h('strong', {}, 'Mapped from portal typologies (draft): '), mapped.map(([n, m]) => `${n} (${m.strength})`).join(', ')));
  root.append(md(tech.definition || tech.short));

  const labels = { rel: 'Relationships', ind: `Indicators (${tech.indicators.length})` };
  if (tech.subs.length) labels.subs = `Sub-techniques (${tech.subs.length})`;
  for (const [field, name] of LIST_TABS) labels[field] = `${name} (${tech[field].length})`;
  const order = ['rel', ...(tech.subs.length ? ['subs'] : []), 'ind', ...LIST_TABS.map((x) => x[0])];
  const pillBox = h('div'), body = h('div');
  root.append(pillBox, body);

  const indList = (t) => h('ul', {}, t.indicators.map((ind) => h('li', {}, h('code', {}, ind), ' ', snap.indicators[ind])));
  function show() {
    dropNet('rel');
    pillBox.replaceChildren(pills(order.map((id) => [id, labels[id]]), O.section, (id) => { O.section = id; show(); }));
    const s = O.section;
    if (s === 'rel') body.replaceChildren(relView(key));
    else if (s === 'subs') body.replaceChildren(...tech.subs.map((sk) => {
      const sub = snap.techniques[sk];
      return h('details', { class: 'card tight' }, h('summary', {}, `${sub.id} · ${sub.name}  (${sub.indicators.length} indicators)`), md(sub.definition || sub.short), indList(sub));
    }));
    else if (s === 'ind') body.replaceChildren(indList(tech));
    else if (!tech[s].length) body.replaceChildren(caption('None recorded for this technique.'));
    else body.replaceChildren(...tech[s].map((it) => {
      const e = dims[s][it.ref];
      return h('details', { class: 'card tight' }, h('summary', {}, `${e.id} · ${e.name}`), md(it.note || e.short || ''));
    }));
  }
  show();
  return root;
}

/* ---------- the AML typology box ---------- */
let refreshDetail = () => {};
function renderOntology(root) {
  const snap = DATA.snap, tmap = DATA.tmap;
  const nTech = Object.values(snap.techniques).filter((t) => t.kind === 'technique').length;
  const typBox = h('div'), tableBox = h('div'), detailBox = h('div');

  root.append(h('p', {}, 'All ', h('strong', {}, `${nTech} AML typology techniques`),
    '. Click a row to see its indicators, relationships, mitigations and data sources. Filter by tactic, or by a typology the portal detects to see which techniques it corresponds to.'),
    h('div', { class: 'warn' }, '⚠️ The typology → technique mapping is a ', h('strong', {}, 'draft'),
      ` (${tmap.status.split(' - ').slice(1).join(' - ') || tmap.status}). Match strength: strong = AMLTRIX's definition describes the behaviour the rule detects; medium = overlapping but framed differently; weak = related context only.`));

  const query = h('input', { type: 'text', placeholder: 'e.g. mule, shell, structuring', value: O.query,
    oninput: (e) => { O.query = e.target.value.trim().toLowerCase(); refreshTable(); } });
  const typSelect = h('select', { onchange: (e) => { O.typology = e.target.value; refreshTable(); } },
    ['All', ...tmap.typologies.map((t) => t.name)].map((n) => h('option', { value: n, selected: n === O.typology }, n)));
  const subs = h('input', { type: 'checkbox', checked: O.subs, onchange: (e) => { O.subs = e.target.checked; refreshTable(); } });
  const chips = h('div', { class: 'chips' }, Object.values(snap.dimensions.tactics).map((t) => {
    const chip = h('button', { class: 'chip' + (O.tactics.has(t.name) ? ' on' : ''), type: 'button', onclick: () => {
      O.tactics.has(t.name) ? O.tactics.delete(t.name) : O.tactics.add(t.name);
      chip.classList.toggle('on', O.tactics.has(t.name));
      refreshTable();
    } }, t.name);
    return chip;
  }));
  root.append(h('div', { class: 'controls' },
    h('label', {}, 'Search', query), h('label', {}, 'Portal typology', typSelect),
    h('label', { class: 'inline' }, subs, 'Include sub-techniques')),
    h('div', { class: 'controls' }, h('label', {}, 'Tactic', chips)), typBox, tableBox, hr(), detailBox);

  function markSelected() {
    for (const tr of tableBox.querySelectorAll('tr[data-key]')) tr.classList.toggle('sel', tr.dataset.key === O.sel);
  }
  function select(key) {
    O.sel = key; O.focus = null; O.expanded = []; O.node = null; O.section = 'rel';
    markSelected(); refreshDetail();
  }
  function refreshTable() {
    const { columns, rows } = buildTable();
    if (O.sel && !rows.some((r) => r.key === O.sel)) { O.sel = null; O.focus = null; O.expanded = []; O.node = null; }
    const total = O.subs ? Object.keys(snap.techniques).length : nTech;
    typBox.replaceChildren();
    dropNet('typ');
    if (O.typology !== 'All') {
      const t = tmap.typologies.find((x) => x.name === O.typology);
      typBox.append(h('p', {}, h('strong', {}, `How the demo detects ${O.typology}: `), t.demo_signal, h('br'), `Related policy: ${t.policy.join(', ')}`), typologyGraph(t));
    }
    tableBox.replaceChildren(caption(`${rows.length} of ${total} ${O.subs ? 'techniques and sub-techniques' : 'techniques'}`),
      rows.length ? dataTable(columns, rows, { onSelect: select, selected: O.sel, maxHeight: 380 }) : h('div', { class: 'card' }, 'No technique matches these filters.'));
    refreshDetail();
  }
  refreshDetail = () => {
    dropNet('rel');
    if (!O.sel) { detailBox.replaceChildren(h('div', { class: 'card' }, '👆 Click a row to see the technique\'s indicators and relationships')); return; }
    const focus = O.focus || O.sel;
    const parts = [];
    if (focus !== O.sel) {
      const origin = snap.techniques[O.sel];
      parts.push(h('button', { class: 'btn', type: 'button', onclick: () => { O.focus = null; O.expanded = []; O.node = null; O.section = 'rel'; refreshDetail(); } },
        `← Back to ${origin.id} · ${origin.name}`));
    }
    parts.push(techDetail(focus));
    detailBox.replaceChildren(...parts);
  };
  refreshTable();
}

function hr() { return h('hr'); }

/* ---------- the Risk indicators box ---------- */
const IND = { query: '', tech: 'All', tactic: 'All', limit: 200 };
let INDROWS = null;
function indicatorRows() {
  if (INDROWS) return INDROWS;
  const snap = DATA.snap, rows = {};
  for (const tech of Object.values(snap.techniques)) {
    for (const ind of tech.indicators) {
      const r = (rows[ind] ||= { techniques: [], tactics: new Set(), sources: new Set() });
      r.techniques.push(`${tech.id} ${tech.name}`);
      tacticNames(tech).forEach((n) => r.tactics.add(n));
      tech.dataSources.forEach((d) => r.sources.add(snap.dimensions.dataSources[d.ref].name));
    }
  }
  INDROWS = Object.entries(snap.indicators).map(([id, text]) => {
    const r = rows[id];
    return { id, text, techniques: r ? r.techniques : [], tactics: r ? [...r.tactics].sort() : [], sources: r ? [...r.sources].sort() : [] };
  });
  return INDROWS;
}

function renderIndicators(root) {
  const snap = DATA.snap, all = indicatorRows();
  const tableBox = h('div');
  root.append(h('p', {}, 'All ', h('strong', {}, `${all.length.toLocaleString()} AMLTRIX risk indicators`),
    '. Search the description, or narrow by technique or tactic. "Where to look" lists the data sources AMLTRIX gives for the technique.'));
  const query = h('input', { type: 'text', placeholder: 'e.g. cash, cross-border, ownership', value: IND.query,
    oninput: (e) => { IND.query = e.target.value.trim().toLowerCase(); IND.limit = 200; refresh(); } });
  const tech = h('select', { onchange: (e) => { IND.tech = e.target.value; IND.limit = 200; refresh(); } },
    ['All', ...Object.values(snap.techniques).map((t) => `${t.id} ${t.name}`)].map((n) => h('option', { value: n, selected: n === IND.tech }, n)));
  const tactic = h('select', { onchange: (e) => { IND.tactic = e.target.value; IND.limit = 200; refresh(); } },
    ['All', ...Object.values(snap.dimensions.tactics).map((t) => t.name)].map((n) => h('option', { value: n, selected: n === IND.tactic }, n)));
  root.append(h('div', { class: 'controls' }, h('label', {}, 'Search', query), h('label', {}, 'Technique', tech), h('label', {}, 'Tactic', tactic)), tableBox);

  function refresh() {
    const shown = all.filter((r) =>
      (!IND.query || r.text.toLowerCase().includes(IND.query) || r.id.toLowerCase().includes(IND.query)) &&
      (IND.tech === 'All' || r.techniques.includes(IND.tech)) && (IND.tactic === 'All' || r.tactics.includes(IND.tactic)));
    const rows = shown.slice(0, IND.limit).map((r) => ({ key: r.id, cells: [r.id, r.text, r.techniques.join('; '), r.tactics.join(', '), r.sources.join(', ')] }));
    fill(tableBox, caption(`${shown.length.toLocaleString()} of ${all.length.toLocaleString()} indicators` +
      (shown.length > rows.length ? ` (showing the first ${rows.length})` : '')),
      dataTable(['Indicator', 'Description', 'Technique', 'Tactic', 'Where to look'], rows, { maxHeight: 460 }),
      shown.length > rows.length ? h('div', { style: { marginTop: '8px' } },
        h('button', { class: 'btn', type: 'button', onclick: () => { IND.limit += 400; refresh(); } }, 'Show more')) : null);
  }
  refresh();
}
