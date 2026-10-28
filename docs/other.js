/* Investigation ontology, the three agent boxes and the three integration boxes.
   Mirrors portal/investigation_tab.py, agents_tab.py and integration_tab.py. */

/* ---------- Investigation ontology ---------- */
const INV_SECTIONS = ['Classes and graph', 'Properties', 'Validation rules', 'Examples'];
const INV = { section: INV_SECTIONS[0], node: 'inv:Alert', example: null };
const OWN_COLOR = '#4DB6AC', DICTIONARY_COLOR = '#B39DDB', INV_GRAPH_H = 460;

function invName(term) { return term.split(':').slice(1).join(':') || term; }

/* (from class, property, to class) for every property that points from one class to another */
function invLinks(snap) {
  const out = snap.rules.filter((r) => r.rule.includes('pointing to'))
    .map((r) => [r.class, r.property, r.rule.match(/pointing to (\S+)/)[1]]);
  out.push(['inv:ReportDraft', 'inv:paragraphs', 'inv:Paragraph']); // an ordered list, so the shapes have no class rule
  return out;
}

function invNodeDetails(snap, node) {
  const box = h('div');
  if (!node) { box.append(caption('Click a box in the graph to see what it is and which properties it carries.')); return box; }
  const own = Object.fromEntries(snap.classes.map((c) => [c.id, c]));
  if (!own[node]) {
    box.append(h('p', {}, h('strong', {}, node)),
      h('p', {}, 'Defined in AMLO / AMLTRIX, not in this ontology. Investigation records point into the dictionary with it, so a finding or a ' +
        'suggested check names a real technique, indicator or data source.'));
    const used = [...new Set(invLinks(snap).filter(([, , b]) => b === node).map(([a, p]) => `${invName(a)} → ${invName(p)}`))].sort();
    if (used.length) box.append(caption('Used by: ' + used.join(', ')));
    return box;
  }
  box.append(h('p', {}, h('strong', {}, own[node].label), ' ', h('code', {}, node)), h('p', {}, own[node].comment));
  const data = snap.properties.filter((p) => p.kind === 'Data' && p.domain === node);
  if (data.length) box.append(caption('Carries: ' + data.map((p) => `${invName(p.id)} (${invName(p.range)})`).join(', ')));
  const out = invLinks(snap).filter(([a]) => a === node);
  if (out.length) box.append(caption('Points to: ' + out.map(([, p, b]) => `${invName(p)} → ${invName(b)}`).join(', ')));
  const rules = snap.rules.filter((r) => r.class === node && r.property !== '(whole record)');
  if (rules.length) box.append(caption('Must have: ' + rules.map((r) => `${invName(r.property)} (${r.rule.split(',')[0]})`).join('; ')));
  return box;
}

function invGraph(snap) {
  const links = invLinks(snap);
  const own = Object.fromEntries(snap.classes.map((c) => [c.id, c]));
  const external = [...new Set(links.map(([, , b]) => b).filter((b) => !own[b]))].sort();
  const nodes = Object.values(own).map((c) => ({ id: c.id, label: c.label, color: nodeColor(OWN_COLOR), title: c.comment, font: { color: '#10211f', size: 18 } }));
  external.forEach((e) => nodes.push({ id: e, label: invName(e), color: nodeColor(DICTIONARY_COLOR), title: 'Defined in AMLO / AMLTRIX', font: { color: '#1d1740', size: 18 } }));
  const edges = links.map(([a, p, b]) => ({ from: a, to: b, label: invName(p), font: { size: 13, color: '#9AA0A6', strokeWidth: 0 } }));
  const detailEl = h('div', { class: 'scroll', style: { height: INV_GRAPH_H + 'px' } });
  const graphEl = h('div', { class: 'graph', style: { height: INV_GRAPH_H + 'px' } });
  const legendEl = h('div', { class: 'legend', style: { height: INV_GRAPH_H + 'px' } },
    h('b', {}, 'Legend'), h('div', { style: { height: '8px' } }),
    legendEntry(OWN_COLOR, 'Investigation class', `(${Object.keys(own).length})`, 'A kind of record this ontology adds: alert, case, finding and so on.'),
    legendEntry(DICTIONARY_COLOR, 'Dictionary term', `(${external.length})`, 'An AMLO / AMLTRIX term the records point into. Not defined here.'),
    caption('Arrows are properties, for example a finding points to the evidence that supports it.'));
  const paintDetail = () => detailEl.replaceChildren(invNodeDetails(snap, INV.node));
  paintDetail();
  whenConnected(graphEl, () => makeNet('inv', graphEl, nodes, edges,
    graphOptions({ nodeDistance: 110, centralGravity: 0.35, springLength: 120, springConstant: 0.05 }),
    (id) => { INV.node = id; paintDetail(); }));
  return h('div', { class: 'cols3 invg' }, detailEl, graphEl, legendEl);
}

function renderInvestigation(root) {
  const snap = DATA.inv, meta = snap.meta;
  root.append(h('p', {}, h('strong', {}, meta.title), ` · version ${meta.version}. ${meta.description}`),
    caption(`${meta.note} Snapshot of ${meta.source}, exported ${meta.exported}.`),
    h('div', { class: 'metrics' },
      [['Classes', snap.classes.length], ['Properties', snap.properties.length], ['Validation rules', snap.rules.length + snap.consistency.length]]
        .map(([l, v]) => h('div', { class: 'metric' }, h('div', { class: 'v' }, v), h('div', { class: 'l' }, l)))));
  const pillBox = h('div'), body = h('div');
  root.append(pillBox, body);
  function show() {
    dropNet('inv');
    pillBox.replaceChildren(pills(INV_SECTIONS.map((s) => [s, s]), INV.section, (s) => { INV.section = s; show(); }));
    if (INV.section === 'Classes and graph') body.replaceChildren(invGraph(snap));
    else if (INV.section === 'Properties') {
      body.replaceChildren(dataTable(['Property', 'Kind', 'From', 'To / type', 'Meaning'],
        snap.properties.map((p) => ({ key: p.id, cells: [p.id, p.kind, p.domain, p.range, p.comment || p.label] })), { maxHeight: 460 }));
    } else if (INV.section === 'Validation rules') {
      body.replaceChildren(
        h('p', {}, h('strong', {}, 'Shape rules'), ' (SHACL). Each record is checked against these before anyone relies on it.'),
        dataTable(['Class', 'Property', 'Rule', 'Message'], snap.rules.map((r, i) => ({ key: i, cells: [r.class, r.property, r.rule, r.message] })), { maxHeight: 360 }),
        h('p', { style: { marginTop: '12px' } }, h('strong', {}, 'Cross-record checks.'), ' These look across records and the dictionary, which a shape cannot do.'),
        h('ul', {}, snap.consistency.map((c) => h('li', {}, c[0].toUpperCase() + c.slice(1)))));
    } else {
      const names = Object.keys(snap.examples);
      INV.example = INV.example || names[0];
      body.replaceChildren(pills(names.map((n) => [n, n]), INV.example, (n) => { INV.example = n; show(); }),
        caption('The JSON-LD graph a business record becomes. The field-to-term mapping (the @context) is left out here.'),
        jsonBlock(snap.examples[INV.example], 460));
    }
  }
  show();
}

/* ---------- Agents ---------- */
const AG_SECTIONS = ['Scenario 1: investigation advice', 'Scenario 2: report narrative'];
const AG = { section: AG_SECTIONS[0], run: { s1: 'real', s2: 'real' }, doc: { s1: false, s2: false } };

function outcome(result) { return `Accepted ${result.accepted.length} · rejected ${result.rejected.length}`; }

function runChoice(key, onChange) {
  const meta = DATA.agent.meta;
  return pills([['real', `Real model run (${meta.provider}/${meta.model})`], ['canned', 'Canned example (hand-written, not a model)']], AG.run[key], onChange);
}

function adviceColumn(result, title) {
  const col = h('div', {}, h('strong', {}, title), caption(outcome(result)));
  for (const a of result.accepted) {
    col.append(h('div', { class: 'card tight' },
      h('div', {}, h('strong', {}, `${a.priority}. ${a.indicator}`), ` · look at ${a.data_source} ${a.data_source_name}`),
      caption(a.indicator_text), h('div', {}, a.reason)));
  }
  for (const r of result.rejected) {
    const s = r.suggestion && typeof r.suggestion === 'object' ? r.suggestion : {};
    col.append(h('div', { class: 'card tight' },
      h('div', {}, badge('red', 'rejected'), ' ', h('strong', {}, s.indicator || '?'), ` · ${s.data_source || '?'}`),
      r.problems.map((p) => caption(p))));
  }
  return col;
}

function reportColumn(result, title) {
  const col = h('div', {}, h('strong', {}, title), caption(outcome(result)));
  for (const p of result.accepted) col.append(h('div', { class: 'card tight' }, h('div', {}, p.text), caption('Based on ' + p.based_on.join(', '))));
  for (const r of result.rejected) {
    const para = r.paragraph && typeof r.paragraph === 'object' ? r.paragraph : {};
    col.append(h('div', { class: 'card tight' }, badge('red', 'rejected'), h('div', {}, para.text || '(no text)'), r.problems.map((p) => caption(p))));
  }
  return col;
}

function docToggle(key, label, doc, repaint) {
  if (!doc) return null;
  const box = h('input', { type: 'checkbox', checked: AG.doc[key], onchange: (e) => { AG.doc[key] = e.target.checked; repaint(); } });
  return h('div', {}, h('label', {}, box, ' ' + label), AG.doc[key] ? jsonBlock(doc, 360) : null);
}

function scenario1(root, repaint) {
  const s1 = DATA.agent.s1, d = s1.dictionary, alert = s1.alert, run = AG.run.s1;
  root.append(h('p', {}, 'When an alert comes in, the agent uses the AML typology and risk indicators to tell the investigator what to check first and where to look.'),
    h('div', { class: 'card' },
      h('div', {}, h('strong', {}, `Alert ${alert.alert_id}`), ` · suspected technique ${s1.technique.id} ${s1.technique.name}`),
      h('div', {}, alert.trigger_reason),
      caption(`The agent is asked where an investigator should look first. With the AML typology it also receives the ${d.indicators} indicators and ` +
        `${d.data_sources} data sources AMLTRIX lists for the technique. Without it, it receives only the technique's name. No transaction data is read.`)),
    runChoice('s1', (v) => { AG.run.s1 = v; repaint(); }),
    h('div', { class: 'cols2' }, adviceColumn(s1[run].with, 'With AML Typology'), adviceColumn(s1[run].without, 'Without AML Typology')),
    caption('Each suggestion is kept only if its indicator is real and belongs to the suspected technique, and its data source is one AMLTRIX lists for ' +
      'that technique. Passing shows the ids are sound, not that the reasoning fits the alert: read the reasons yourself.'),
    docToggle('s1', 'Show the validated JSON-LD of the accepted advice', s1[run].with.doc, repaint));
}

function scenario2(root, repaint) {
  const s2 = DATA.agent.s2, c = s2.case, run = AG.run.s2;
  root.append(h('p', {}, 'Once the findings are in, the agent drafts the report, and every paragraph points back to the finding it rests on.'),
    h('div', { class: 'card' },
      h('div', {}, h('strong', {}, `Case ${c.case_id}`), ` · investigating ${c.hypothesis.join(', ')} ${s2.technique.name || ''}`),
      h('div', { style: { margin: '8px 0' } }, dataTable(['Finding', 'Indicator', 'Status', 'Observation'],
        c.findings.map((f) => ({ key: f.finding_id, cells: [f.finding_id, f.indicator, f.status, f.observation] })), { maxHeight: 300 })),
      caption('The agent writes the findings section of a report from these findings. With the AML typology it also receives what the technique and ' +
        'indicators mean. Each paragraph must name the findings it rests on.')),
    runChoice('s2', (v) => { AG.run.s2 = v; repaint(); }),
    h('div', { class: 'cols2' }, reportColumn(s2[run].with, 'With AML Typology'), reportColumn(s2[run].without, 'Without AML Typology')),
    caption('A paragraph is kept only if it cites at least one real finding of this case and mentions only technique and indicator ids that belong to the ' +
      "findings it cites. Whether the wording is faithful to a finding is not checked, so the draft always needs the investigator's review."),
    docToggle('s2', 'Show the validated JSON-LD of the accepted draft', s2[run].with.doc, repaint));
}

function renderInvestigationAgent(root) {
  const meta = DATA.agent.meta;
  root.append(caption(`Saved run from ${meta.exported} against AMLTRIX ${meta.dictionary}: one alert and one case, one run of one model. ` +
    'An illustration, not a measurement. No model is called when you view this page.'));
  const pillBox = h('div'), body = h('div');
  root.append(pillBox, body);
  function show() {
    pillBox.replaceChildren(pills(AG_SECTIONS.map((s) => [s, s]), AG.section, (s) => { AG.section = s; show(); }));
    const inner = h('div');
    body.replaceChildren(inner);
    (AG.section === AG_SECTIONS[0] ? scenario1 : scenario2)(inner, show);
  }
  show();
}

function renderIdentificationAgent(root) {
  const steps = [
    ['Pick a typology', 'A technique from the AML typology, for example circular transactions.'],
    ['Take its indicators', 'The risk indicators AMLTRIX lists for that technique.'],
    ['Write the query', 'The agent turns the indicators into SQL, using a data dictionary of the transaction columns.'],
    ['Guard the query', 'Code rejects anything that is not a read-only query over allowed columns with a time range. The label column is never allowed in a query.'],
    ['Run it', 'The query runs on the transaction data and returns candidate transactions.'],
    ['Measure it', 'The candidates are compared with the known labels, on the test period only.'],
  ];
  root.append(h('p', {}, h('strong', {}, 'Scenario 3: typology-driven query')), caption('Design only: this scenario is not built yet.'),
    steps.map(([t, text], i) => h('div', { class: 'card tight' }, h('div', {}, h('strong', {}, `${i + 1}. ${t}`)), h('div', {}, text))),
    caption('The point to show: the typology and its indicators are what the agent writes the query from, and a guard and a measurement make the result ' +
      'checkable. The labels are used only to judge the query, never to write it.'));
}

/* ---------- Integration ---------- */
const INT_AREA = { int1: 'data', int2: 'alerts', int3: 'investigation' };
const INT_INTRO = {
  data: 'Source data such as accounts, parties and transactions has no mapping yet. AMLO describes laundering techniques and indicators, and has no party, ' +
    'account or transaction concepts. So this interface still has to be designed.',
  alerts: "How an alert from a detection system arrives. The fields keep the source system's own names; a JSON-LD context maps each one to a shared term, " +
    'and the suspected typology becomes a pointer into AMLTRIX.',
  investigation: 'How suggested checks, cases, findings and report drafts are written. The same shared terms let an agent read the records of any case system, ' +
    'and let code check them.',
};
const INT_SECTIONS = ['Field mapping', 'Source to JSON-LD'];
const INT_SCENARIOS = [['s1', 'Scenario 1: suggested checks'], ['s2', 'Scenario 2: case and report']];
const TYPE_NOTE = { extension: 'a term the Investigation Ontology adds', transform: 'converted to a pointer into AMLTRIX', 'direct reuse': 'an AMLTRIX term used as is', unresolved: 'no term yet' };
const INTS = { section: {}, scenario: 's1' };

function mappingView(area) {
  const rows = DATA.integ.mapping.filter((r) => r.Area === area);
  const counts = new Map();
  rows.forEach((r) => counts.set(r['Mapping type'], (counts.get(r['Mapping type']) || 0) + 1));
  const summary = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${k} (${TYPE_NOTE[k] || ''})`).join(' · ');
  return h('div', {}, caption(summary), dataTable(['Business concept', 'Source field', 'Ontology term', 'Type', 'Why'],
    rows.map((r, i) => ({ key: i, cells: [r['Business concept'], r['Source field'], r['Ontology term'], r['Mapping type'], r.Rationale] })), { maxHeight: 460 }));
}

function jsonKeys(value, found) {
  found = found || new Set();
  if (Array.isArray(value)) value.forEach((v) => jsonKeys(v, found));
  else if (value && typeof value === 'object') Object.entries(value).forEach(([k, v]) => { found.add(k); jsonKeys(v, found); });
  return found;
}

function termRows(context, source) {
  const keys = [...jsonKeys(source)].filter((k) => k in context).sort();
  return keys.map((field) => {
    const entry = context[field];
    const term = typeof entry === 'string' ? entry : entry['@id'] || '';
    const kind = typeof entry === 'string' ? '' : entry['@type'] || '';
    return { key: field, cells: [field, term, kind === '@id' ? 'an IRI (a pointer)' : kind] };
  });
}

function sourceView(source, graph, contextName) {
  const rows = termRows(DATA.integ.contexts[contextName], source);
  return h('div', { class: 'cols3 src' },
    h('div', {}, h('strong', {}, 'Source record'), caption("In the source system's own field names."), jsonBlock(source, 420)),
    h('div', {}, h('strong', {}, 'Mapping (JSON-LD context)'), caption('Each field to the term it means.'),
      dataTable(['Field', 'Term', 'Converted to'], rows, { maxHeight: 420 })),
    h('div', {}, h('strong', {}, 'JSON-LD'), caption('The record in shared terms, ready to check.'), jsonBlock({ '@graph': graph }, 420)));
}

function renderIntegration(root, id) {
  const snap = DATA.integ, area = INT_AREA[id];
  root.append(caption(INT_INTRO[area]));
  if (id === 'int1') {
    root.append(mappingView(area), caption('Nothing is mapped for this area, so there is no sample to show.'));
  } else {
    const pillBox = h('div'), body = h('div');
    root.append(pillBox, body);
    const show = () => {
      const section = INTS.section[id] || INT_SECTIONS[0];
      pillBox.replaceChildren(pills(INT_SECTIONS.map((s) => [s, s]), section, (s) => { INTS.section[id] = s; show(); }));
      if (section === INT_SECTIONS[0]) body.replaceChildren(mappingView(area));
      else if (id === 'int2') body.replaceChildren(sourceView(snap.alerts.source, snap.alerts.graph, 'alert'));
      else {
        const s = snap.investigation[INTS.scenario];
        body.replaceChildren(pills(INT_SCENARIOS, INTS.scenario, (v) => { INTS.scenario = v; show(); }), sourceView(s.source, s.graph, s.context));
      }
    };
    show();
  }
  root.append(caption(`From ${snap.meta.source}, exported ${snap.meta.exported}. The sample records are synthetic.`));
}
