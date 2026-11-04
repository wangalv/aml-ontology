/* The architecture map: a grid of clickable boxes with a detail panel below. Mirrors render() in portal/semantic_tab.py. */
const DATA = {};
let selected = DEFAULT_ITEM;
const boxes = {};

function makeBox(id, label, extraClass) {
  const live = CLICKABLE.has(id);
  const btn = h('button', { class: 'box ' + (extraClass || ''), type: 'button', 'data-item': id, ...(live ? { onclick: () => select(id) } : { disabled: true }) });
  boxes[id] = boxes[id] || [];
  boxes[id].push({ btn, label: label || ITEMS[id].name });
  return btn;
}

function panel(title, ids) {
  return h('div', { class: 'panel-box' }, h('div', { class: 'title' }, title), ids.map((id) => makeBox(id)));
}

function paintBoxes() {
  for (const [id, list] of Object.entries(boxes)) {
    for (const { btn, label } of list) {
      btn.classList.toggle('sel', id === selected);
      btn.textContent = label;
    }
  }
}

// The technologies behind the integration layer and the semantic layer to its right, top to bottom in the same order. Mirrors TECH_STACK in portal/semantic_tab.py.
// [term, what it does here, built?]
const TECH_STACK = [
  ['Integration layer', [
    ['JSON-LD', 'source fields to ontology terms', true],
    ['Mapping table, data dictionary', '', true],
    ['MCP, API', 'layer exposed to agents', false],
  ]],
  ['Semantic layer', [
    ['OWL', 'classes and properties', true],
    ['SKOS', 'typology techniques, indicators', true],
    ['RDF, Turtle', 'storage format', true],
    ['SHACL', 'valid-record rules (pyshacl)', true],
    ['SPARQL', 'cross-record checks (rdflib)', true],
  ]],
];

function techBox([term, does, built]) {
  return h('div', { class: 'tech-box' + (built ? '' : ' design') },
    h('b', { class: 'tech-term' }, term), h('span', { class: 'tech-does' }, (does ? ' · ' + does : '') + (built ? '' : ' (design only)')));
}

function techStack() {
  return h('div', { class: 'tech-col' }, TECH_STACK.map(([layer, rows]) => h('div', { class: 'panel-box tech' + (layer === 'Semantic layer' ? ' pink' : '') },
    h('div', { class: 'stack-head' }, layer), rows.map(techBox))));
}

function buildArchitecture() {
  const grid = h('div', { class: 'arch' });
  grid.append(
    panel('Data asset', ['acct', 'party', 'tx', 'other']),
    panel('FinCrime data management', ['er', 'fs', 'lm']),
    panel('Risk identification systems', ['ml', 'rule', 'graph', 'osol']),
    panel('Investigation systems', ['ucm']),
    h('div'), ...['ag1', 'ag2', 'ag3'].map((id) => makeBox(id, 'Agent', 'agent')),
    techStack(),
    ...['int1', 'int2', 'int3'].map((id) => makeBox(id, 'Integration (MCP, API)')),
    h('div', { class: 'layer' }, h('div', { class: 'title' }, 'FinCrime Semantic Layer'),
      h('div', { class: 'row' }, ['typ', 'ind', 'scn', 'det', 'inv'].map((id) => makeBox(id))), makeBox('kmg')),
    h('div', { class: 'base' }, makeBox('ent')),
  );
  return h('div', { class: 'arch-wrap' }, grid);
}

function detailView(id) {
  const it = ITEMS[id];
  const root = h('div');
  const uses = it.relies.length ? 'Relies on: ' + it.relies.map((k) => SEMANTIC[k]).join(', ') : 'Part of the semantic layer';
  root.append(h('h2', {}, it.name), h('div', {}, badge(BADGE[it.kind], it.kind), ' ', h('span', { class: 'muted' }, uses)));
  const body = h('div', { style: { marginTop: '10px' } });
  root.append(body);
  if (id in INT_AREA) renderIntegration(body, id);
  else if (id === 'ag2') renderIdentificationAgent(body);
  else if (id === 'ag3') renderInvestigationAgent(body);
  else if (id === 'ind') renderIndicators(body);
  else if (id === 'inv') renderInvestigation(body);
  else if (id === 'typ') renderOntology(body);
  else {
    body.append(h('div', { class: 'card' }, caption('Preview: ' + it.preview), h('p', {}, it.text)));
  }
  return root;
}

function select(id) {
  selected = id;
  try { history.replaceState(null, '', '#' + id); } catch (e) { /* file:// or sandboxed frames */ }
  paintBoxes();
  dropAllNets();
  document.getElementById('detail').replaceChildren(detailView(id));
}

async function main() {
  const app = document.getElementById('app');
  try {
    const names = { snap: 'amlo_snapshot', tmap: 'typology_map', inv: 'investigation_snapshot', agent: 'agent_snapshot', integ: 'integration_snapshot' };
    const loaded = await Promise.all(Object.values(names).map((n) => fetch(`data/${n}.json`, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${n}.json: ${r.status}`);
      return r.json();
    })));
    Object.keys(names).forEach((k, i) => { DATA[k] = loaded[i]; });
  } catch (err) {
    app.replaceChildren(h('div', { class: 'warn' }, 'Could not load the data files (' + err.message + '). Serve this folder over HTTP, e.g. ',
      h('code', {}, 'python3 -m http.server --directory site'), ', rather than opening the file directly.'));
    return;
  }
  const hash = location.hash.slice(1);
  if (ITEMS[hash] && CLICKABLE.has(hash)) selected = hash;
  app.replaceChildren(
    caption('Click a box for its detail. Greyed-out boxes are placeholders. Draft layout.'),
    buildArchitecture(), h('hr'), h('div', { id: 'detail' }));
  paintBoxes();
  document.getElementById('detail').replaceChildren(detailView(selected));
  const meta = DATA.snap.meta;
  document.getElementById('footer').replaceChildren(
    h('p', {}, `AMLTRIX ${meta.version} (${meta.url}), snapshot exported ${meta.exported}. ${meta.rights} `,
      h('a', { href: 'AMLTRIX_LICENSE.txt' }, 'License terms'), ' · ', h('a', { href: 'AMLTRIX_NOTICE.txt' }, 'Notice'), '.'),
    h('p', {}, 'A static export of the Semantic Layer tab of the AML Triage demo: nothing here calls a model or reads a database. The typology-to-technique mapping is a first draft that has not been reviewed by a domain expert. The sample alert and case are built from one transaction in the synthetic IBM AML data. ' +
      'The agent results are one saved run of one model on one alert and one case: an illustration, not a measurement.'));
}

main();
