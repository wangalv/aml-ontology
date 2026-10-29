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
      h('p', {}, 'Defined in AMLO / AML typology, not in this ontology. Investigation records point into the dictionary with it, so a finding or a ' +
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
  external.forEach((e) => nodes.push({ id: e, label: invName(e), color: nodeColor(DICTIONARY_COLOR), title: 'Defined in AMLO / AML typology', font: { color: '#1d1740', size: 18 } }));
  const edges = links.map(([a, p, b]) => ({ from: a, to: b, label: invName(p), font: { size: 13, color: '#9AA0A6', strokeWidth: 0 } }));
  const detailEl = h('div', { class: 'scroll', style: { height: INV_GRAPH_H + 'px' } });
  const graphEl = h('div', { class: 'graph', style: { height: INV_GRAPH_H + 'px' } });
  const legendEl = h('div', { class: 'legend', style: { height: INV_GRAPH_H + 'px' } },
    h('b', {}, 'Legend'), h('div', { style: { height: '8px' } }),
    legendEntry(OWN_COLOR, 'Investigation class', `(${Object.keys(own).length})`, 'A kind of record this ontology adds: alert, case, finding and so on.'),
    legendEntry(DICTIONARY_COLOR, 'Dictionary term', `(${external.length})`, 'An AMLO / AML typology term the records point into. Not defined here.'),
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
const AG_SECTIONS = ['Scenario 1: investigation advice', 'Scenario 2: report narrative', 'Scenario 3: typology-driven query'];
const AG = { section: AG_SECTIONS[0], doc: { s1: false, s2: false }, open: { s1: false, s2: false } };

function definitionBox(text) { return h('div', { class: 'ctx-box' }, text); }

function quote(text) { return h('div', { class: 'quote' }, h('span', { class: 'tag' }, 'From the AML typology'), text); }

function docToggle(key, label, doc, repaint) {
  if (!doc) return null;
  const box = h('input', { type: 'checkbox', checked: AG.doc[key], onchange: (e) => { AG.doc[key] = e.target.checked; repaint(); } });
  return h('div', {}, h('label', {}, box, ' ' + label), AG.doc[key] ? jsonBlock(doc, 360) : null);
}

function scenario1(root, repaint) {
  const s1 = DATA.agent.s1, alert = s1.alert, run = s1.real.with, t = s1.technique, ty = s1.typology;
  const usedInd = new Set(run.accepted.map((a) => a.indicator)), usedDs = new Set(run.accepted.map((a) => a.data_source));
  const when = String(alert.raised_at).replace('T', ' ').replace('Z', ' UTC');
  const items = run.accepted.map((a) => h('div', { class: 'llm-row' },
    h('div', {}, h('strong', {}, `${a.priority}. `), h('span', { class: 'tag' }, 'AML typology'), h('span', { title: a.indicator_text }, shorten(a.indicator_text, 85)), ' ', h('code', {}, a.indicator),
      '  → look in ', badge('gray', `${a.data_source} ${a.data_source_name}`)),
    h('div', { class: 'llm-reason' }, h('span', { class: 'tag llm' }, 'LLM'), a.reason)));
  const detailsOpen = AG.open.s1;
  root.append(h('p', {}, 'When an alert comes in, the LLM uses the AML typology to tell the investigator what to check first and where to look.'),
    h('div', { class: 'card' },
      h('div', { class: 'big-label' }, '1  The alert the investigator receives'),
      h('div', {}, h('strong', {}, `Alert ${alert.alert_id}`), ` · raised ${when} · suspected technique `, badge('blue', `${t.id} ${t.name}`)),
      h('div', { class: 'alert-line' }, alert.trigger_reason),
      caption('What the monitoring systems attached to this payment'),
      h('ul', { class: 'fact-list' }, (alert.facts || []).map((f) => h('li', {}, f))),
      caption('Facts from the rule engine, the ML model and the transaction graph. They say what was detected, not what to check or where to look.')),
    h('div', { class: 'flow-arrow' }, `▼  the LLM reads what the AML typology says about ${t.id}: its definition, ${ty.indicators.length} risk indicators and ${ty.data_sources.length} data sources`),
    h('div', { class: 'llm-box' },
      h('div', { class: 'big-label' }, '2  What the LLM suggests the investigator checks'),
      caption(`Every indicator and data source below is taken from the AML typology; the LLM adds why each one fits this alert. It sees only the alert, no other records.`),
      items,
      caption(`Checked by code: ${run.accepted.length} of ${run.accepted.length + run.rejected.length} suggestions name a real indicator of ${t.id} and a data source the AML typology lists for it. Not checked: whether a reason fits the alert.`)),
    h('details', { class: 'card', open: detailsOpen, ontoggle: (e) => { AG.open.s1 = e.target.open; } },
      h('summary', {}, 'What the LLM was given from the AML typology, and the JSON-LD of the advice'),
      h('div', { class: 'ctx-title', style: { marginTop: '8px' } }, `What AML typology says about ${t.id} ${t.name}`),
      caption('Definition'), definitionBox(t.definition),
      caption(`${ty.indicators.length} risk indicators. Green: the LLM used it above.`),
      h('div', { class: 'ctx-box' }, ty.indicators.map((i) => h('div', { class: 'ctx-row' + (usedInd.has(i.id) ? ' used' : '') }, h('code', {}, i.id), i.text))),
      caption(`${ty.data_sources.length} data sources where evidence can be found`),
      h('div', { class: 'chip-row' }, ty.data_sources.map((d) => h('span', { class: usedDs.has(d.id) ? 'used' : '', title: d.note }, `${d.id} ${d.name}`))),
      docToggle('s1', 'Show the validated JSON-LD of the accepted advice', run.doc, repaint)));
}

function scenario2(root, repaint) {
  const s2 = DATA.agent.s2, c = s2.case, run = s2.real.with, t = s2.technique;
  const grams = ngramSet([t.definition || '', ...Object.values(s2.indicator_text)], GRAM);
  const reused = run.accepted.filter((p) => highlight(p.text, grams).hit).length;
  const STATUS = { supported: 'green', 'not-supported': 'red', inconclusive: 'orange', 'not-assessable': 'gray' };
  const findings = c.findings.map((f) => h('div', { class: 'llm-row' },
    h('div', {}, h('strong', {}, `${f.finding_id}  `), badge(STATUS[f.status] || 'gray', f.status), ' ', h('code', {}, f.indicator)),
    h('div', { class: 'alert-line' }, f.observation)));
  const paragraphs = run.accepted.map((p) => h('div', { class: 'llm-row' },
    h('div', { class: 'llm-reason' }, h('span', { class: 'tag llm' }, 'LLM'), highlight(p.text, grams).nodes),
    h('div', { class: 'llm-quote' }, 'Based on ', p.based_on.map((b) => badge('gray', b)))));
  root.append(h('p', {}, 'When the investigation is done, the LLM drafts the findings section of the report, using the AML typology to say what each finding means.'),
    h('div', { class: 'card' },
      h('div', { class: 'big-label' }, '1  What the investigator has: the findings of the case'),
      h('div', {}, h('strong', {}, `Case ${c.case_id}`), ' · investigating ', badge('blue', `${t.id} ${t.name || ''}`)),
      findings,
      caption('Written by code from the same payment, as a stand-in for an investigator\'s notes. No report wording, and nothing says what the indicators mean.')),
    h('div', { class: 'flow-arrow' }, `▼  the LLM reads what the AML typology says about ${t.id} and the ${Object.keys(s2.indicator_text).length} indicators in these findings`),
    h('div', { class: 'llm-box' },
      h('div', { class: 'big-label' }, '2  What the LLM writes: the findings section of the report'),
      caption('Each paragraph says which finding it rests on. Yellow: wording that also appears in the AML typology text.'),
      paragraphs,
      caption(`${reused} of ${run.accepted.length} paragraphs reuse AML typology wording (${GRAM} or more words in a row): a rough sign that the typology was used, not proof that a paragraph is right. ` +
        'Checked by code: every paragraph cites a real finding of this case and names only technique and indicator ids that belong to it. Not checked: whether the wording is faithful to a finding.')),
    h('details', { class: 'card', open: AG.open.s2, ontoggle: (e) => { AG.open.s2 = e.target.open; } },
      h('summary', {}, 'What the LLM was given from the AML typology, and the JSON-LD of the draft'),
      h('div', { class: 'ctx-title', style: { marginTop: '8px' } }, `What AML typology says about ${t.id} ${t.name}`),
      caption('Definition of the technique'), definitionBox(t.definition || ''),
      caption('What the indicators in these findings mean'),
      h('div', { class: 'ctx-box' }, Object.entries(s2.indicator_text).map(([id, text]) => h('div', { class: 'ctx-row' }, h('code', {}, id), text))),
      docToggle('s2', 'Show the validated JSON-LD of the accepted draft', run.doc, repaint)));
}

function scenario3(root) {
  const s3 = DATA.agent.s3, r = s3.result, meaning = Object.fromEntries(s3.dictionary.columns.map((c) => [c.name, c.meaning]));
  const svg = document.importNode(new DOMParser().parseFromString(s3.diagram, 'image/svg+xml').documentElement, true);
  root.append(caption(`Saved run from ${s3.exported}: one technique, one run of one model (${s3.provider}/${s3.model}), on the synthetic IBM AML data, test period only. ` +
      'An illustration, not a measurement. No model or database is used when you view this page.'),
    h('p', {}, 'An investigator wants to test a hypothesis, here that funds are being round-tripped. The LLM turns the indicator in the AML typology into SQL. ' +
      "The data dictionary, which people write, is the link between the indicator's words and the columns of the table."),
    h('div', { class: 'card' }, h('div', { class: 'diagram s4' }, svg)),
    h('h3', {}, 'The SQL it wrote, and how each part links back'),
    h('pre', { style: { maxHeight: '300px' } }, s3.query.sql),
    dataTable(['Part of the SQL', 'Words of the indicator the LLM says it comes from', 'Columns it uses, as the data dictionary describes them'],
      s3.conditions.map((c, i) => ({ key: i, cells: [h('code', {}, c.sql),
        h('div', {}, h('div', { class: 'quote' }, h('span', { class: 'tag' }, 'AML typology'), c.quote), c.quote_found ? badge('green', 'found in the indicator') : badge('red', 'not in the indicator')),
        h('div', {}, c.columns.map((n) => h('div', {}, h('code', {}, n), ` ${meaning[n]}`)))] })), { maxHeight: 420 }),
    h('div', { class: 'callout' }, `The query ran in ${s3.query.seconds} s and flagged ${fmt(r.flagged)} payments (the most the guard allows), and ${pct(r.laundering, r.flagged)} of them are laundering, ` +
      `the same as for any payment in the period (${pct(r.period_laundering, r.period_payments)}). It follows chains of three or more payments without checking that the money returns to where it started, ` +
      `and it found none of the ${fmt(r.verified_cycle_payments)} payments on verified round trips: a query that runs and is safe is not yet a query that is right.`),
    caption('Checked by code: the SQL is one read-only SELECT over the listed columns, with a LIMIT, a tx_id column and the time column ts, and the words the LLM quotes from the indicator must be in it. ' +
      'The laundering label was used only afterwards, to judge the result; the LLM never saw it. Queries the guard refused are not shown.'));
}

function renderInvestigationAgent(root) {
  const meta = DATA.agent.meta;
  root.append(caption(`Saved run from ${meta.exported} against AML typology ${meta.dictionary}: one alert and one case, one run of one model (${meta.provider}/${meta.model}). ` +
    'An illustration, not a measurement. No model is called when you view this page.'));
  const pillBox = h('div'), body = h('div');
  root.append(pillBox, body);
  function show() {
    pillBox.replaceChildren(pills(AG_SECTIONS.map((s) => [s, s]), AG.section, (s) => { AG.section = s; show(); }));
    const inner = h('div');
    body.replaceChildren(inner);
    [scenario1, scenario2, scenario3][AG_SECTIONS.indexOf(AG.section)](inner, show);
  }
  show();
}

const fmt = (n) => Number(n).toLocaleString('en-US');
const pct = (a, b) => (b ? (100 * a / b).toFixed(2) + '%' : '–');
const money = (n) => Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const SYS_COLOR = { rule: 'blue', ml: 'orange', graph: 'green' };
const SYS_NAME = { rule: 'rule engine', ml: 'ML model', graph: 'transaction graph' };
const sysBadge = (k) => badge(SYS_COLOR[k], SYS_NAME[k]);
const joinNames = (list) => list.map((k) => SYS_NAME[k]).join(' and the ');

function renderIdentificationAgent(root) {
  const s4 = DATA.agent.s4, e = s4.examples[0], p = e.payment, snap = DATA.snap;
  const tiers = s4.payments_by_sources, three = tiers.find((t) => t.sources === 3), one = tiers.find((t) => t.sources === 1);
  const svg = document.importNode(new DOMParser().parseFromString(e.diagram, 'image/svg+xml').documentElement, true);
  const agree = e.lamps.filter((r) => r.systems.length > 1);
  const verdict = agree.length
    ? agree.map((r) => {
      const own = r.systems.filter((k) => r.cells[k].pointed), read = r.systems.filter((k) => !r.cells[k].pointed);
      return `${r.id} ${r.name} is lit by the ${joinNames(r.systems)}: independent systems agree. ` +
        (read.length ? `Only the ${joinNames(own)}'s own flag points to it; for the ${joinNames(read)} it is the model's reading of the evidence.` : "Each system's own flag points to it.");
    }).join(' ')
    : 'No technique is lit by more than one system for this payment.';
  const techBox = h('div');
  const total = e.techniques.reduce((a, t) => a + t.indicators.length, 0), evLabel = Object.fromEntries(e.evidence.map((x) => [x.id, x.flag || (x.kind === 'ml' ? 'ML score' : 'payment details')]));
  const llmBox = h('div', { class: 'llm-box' },
    h('div', {}, badge('violet', 'LLM'), ' ', h('strong', {}, 'What the LLM concluded')),
    caption(`Given ${total} risk indicators written as free text, from ${e.techniques.length} techniques, and each system's evidence on its own, it picked the ${e.rows.length} indicators below as supported, ` +
      'with a reason and the evidence it relies on. Code only checks the ids, the citations and the numbers.'),
    ...e.rows.map((r) => h('div', { class: 'llm-row' },
      h('div', {}, sysBadge(r.system), ' → ', h('code', {}, r.technique || '–'), ` ${r.technique_name} → `, h('code', {}, r.indicator), ` ${r.support === 'yes' ? 'supported' : 'partly supported'} `,
        r.pointed ? null : badge('orange', "read from the evidence, not the system's own flag")),
      h('div', { class: 'llm-reason' }, h('strong', {}, 'LLM: '), r.reason, ' ', h('span', { class: 'muted' }, `(evidence: ${r.evidence.map((id) => evLabel[id] || id).join(', ')})`)),
      h('div', { class: 'llm-quote' }, h('span', { class: 'tag' }, 'AML typology'), shorten(r.indicator_text, 125)))));

  /* Click a technique at the top of the diagram: where it sits in the AML typology, with the same detail and relationship graph as the AML typology box. */
  function showTech() {
    dropNet('rel');
    svg.querySelectorAll('.tech-head').forEach((g) => g.classList.toggle('sel', g.dataset.tech === O.sel));
    if (!O.sel) { techBox.replaceChildren(caption('Click a technique at the top of the diagram to see where it sits in the AML typology. Rest on a lamp to read the model\'s reason.')); return; }
    const focus = O.focus || O.sel, parts = [], row = e.lamps.find((r) => r.id === O.sel);
    if (focus !== O.sel) {
      const origin = snap.techniques[O.sel];
      parts.push(h('button', { class: 'btn', type: 'button', onclick: () => { O.focus = null; O.expanded = []; O.node = null; O.section = 'rel'; showTech(); } }, `← Back to ${origin.id} · ${origin.name}`));
    } else if (row) {
      const lit = e.rows.filter((r) => r.technique === row.id);
      parts.push(h('div', { class: 'card tight' }, h('strong', {}, `What lit ${row.id} for this payment`),
        lit.length ? lit.map((r) => h('div', { class: 'ctx-row' }, sysBadge(r.system), ' ', h('code', {}, r.indicator), ` ${r.support}: ${r.reason} `,
          r.pointed ? caption("The system's own flag points to this technique.") : badge('orange', "not the system's own flag: the model read it from the evidence")))
          : caption('No system\'s evidence supports an indicator of this technique.')));
    }
    parts.push(techDetail(focus));
    techBox.replaceChildren(...parts);
  }
  refreshDetail = showTech;
  svg.querySelectorAll('.tech-head').forEach((g) => g.addEventListener('click', () => {
    O.sel = g.dataset.tech; O.focus = null; O.expanded = []; O.node = null; O.section = 'rel'; showTech();
  }));
  O.sel = null; O.focus = null;
  showTech();

  root.append(caption(`Saved run from ${s4.exported}: one example payment, one run of one model (${s4.provider}/${s4.model}), on the synthetic IBM AML data, test period only. ` +
      'An illustration, not a measurement. No model or database is used when you view this page.'),
    h('p', {}, 'Transaction monitoring already runs by itself. When several systems alert on the same payment, each gives its reason in its own terms. ' +
      "The agent judges each system's evidence against AML typology risk indicators, and a technique that more than one system supports is a strong, linked signal. The investigator decides."),
    h('div', { class: 'card' },
      h('div', {}, h('strong', {}, `Payment ${p.tx_id}`), ' ', p.sources.map((k) => [sysBadge(k), ' '])),
      caption(`${p.ts.slice(0, 16)} · ${money(p.amount)} ${p.currency} by ${p.format} · from ${p.from} to ${p.to} · the first payment, in a fixed random order (seed ${s4.seed}), that all three systems alerted on`),
      h('div', { class: 'diagram s4' }, svg)),
    llmBox,
    h('div', { class: 'callout' }, verdict, caption(`Afterwards, with the label (the model never saw it): this payment ${e.laundering ? 'is' : 'is not'} laundering. ` +
      `Of the ${fmt(three.payments)} payments alerted on by all three systems, ${pct(three.laundering, three.payments)} are laundering, against ${pct(one.laundering, one.payments)} of those only one system alerted on (computed by code).`)),
    techBox,
    caption('Checked by code: every indicator is one that was listed under the techniques the flags point to; every reason cites evidence that exists, and its numbers and amounts appear in it. ' +
      `A note that fails is sent back once (at most ${s4.limits.max_attempts} attempts). Not checked: whether a reason says only what the evidence says, so read the reasons. The technique mapping is a first draft. The ML model gives a score and no reason, so it is shown but not judged.`));
}

/* ---------- Integration ---------- */
const INT_AREA = { int1: 'data', int2: 'alerts', int3: 'investigation' };
const INT_INTRO = {
  data: 'Source data such as accounts, parties and transactions has no mapping yet. AMLO describes laundering techniques and indicators, and has no party, ' +
    'account or transaction concepts. So this interface still has to be designed.',
  alerts: "How an alert from a detection system arrives. The fields keep the source system's own names; a JSON-LD context maps each one to a shared term, " +
    'and the suspected typology becomes a pointer into AML typology.',
  investigation: 'How suggested checks, cases, findings and report drafts are written. The same shared terms let an agent read the records of any case system, ' +
    'and let code check them.',
};
const INT_SCENARIOS = [['s1', 'Scenario 1: suggested checks'], ['s2', 'Scenario 2: case and report'], ['s3', 'Scenario 3: typology-driven query']];
const TYPE_NOTE = { extension: 'a term the Investigation Ontology adds', transform: 'the value is converted to another form, such as a pointer into AML typology or a date', 'direct reuse': 'an AML typology term used as is', unresolved: 'no term yet' };
const INTS = { scenario: 's1' };

/* Spell out the prefixes in the tables; the JSON-LD blocks keep the short form. */
function longTerm(text) { return String(text).replace(/\binv:/g, 'Investigation ontology: ').replace(/\bamx:/g, 'AML typology: '); }

function mappingView(area) {
  const rows = DATA.integ.mapping.filter((r) => r.Area === area);
  const counts = new Map();
  rows.forEach((r) => counts.set(r['Mapping type'], (counts.get(r['Mapping type']) || 0) + 1));
  const summary = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${k} (${TYPE_NOTE[k] || ''})`).join(' · ');
  return h('div', {}, caption(summary), dataTable(['Business concept', 'Source field', 'Ontology term', 'Type', 'Why'],
    rows.map((r, i) => ({ key: i, cells: [r['Business concept'], r['Source field'], longTerm(r['Ontology term']), r['Mapping type'], r['Why (plain)']] })), { maxHeight: 460 }));
}

const CONVERTED = { '@id': 'a pointer (IRI)', 'xsd:dateTime': 'a date and time', 'xsd:integer': 'a whole number' };
const HOW_TO_READ = [
  '**How to read the table**',
  '',
  '- **Term in the ontology** is the shared term the field is mapped to, with the ontology it comes from: the Investigation ontology or AML typology. The same term is used whichever system the record comes from. In the JSON-LD the ontology is shortened to a prefix: `inv:` for the Investigation ontology and `amx:` for AML typology.',
  '- **Linked to in the AML ontology** shows what the field connects to in the semantic layer. Every mapped field links to its term in the Investigation ontology, with the definition. When the value is a pointer into AML typology, the cell also shows the entry it leads to and which part of the semantic layer it belongs to: a technique (AML typology), a risk indicator, or a data source. Risk scenarios are not defined yet, so no field links to one.',
  '- **The mapping:** the bold line is what the field\'s value becomes. The line under it is the mapping type, which says where the term comes from: an extension is a term the Investigation ontology adds, a direct reuse is an AML typology term used as is, and a transform converts the value to another form, such as a pointer into AML typology or a date. The possible values are:',
  '- **a pointer (IRI):** the value stops being plain text and becomes a link to another record or to an AML typology entry. For example `T0039` in `suspected_technique` becomes `amx:T0039`, which points to the technique Circular Transactions. This is what lets code check the value and lets records from different systems connect.',
  '- **a date and time, a whole number:** the value is kept, and marked with its type so that it is read as a date or a number rather than as text.',
  '- **kept as text:** the value stays as it is; only the field name is replaced by the shared term.',
  '- **Why** is the reason the field is mapped this way. A dash means the field has no row of its own in the mapping.',
].join('\n');

function sourceView(source, graph) {
  return h('div', { class: 'cols2' },
    h('div', {}, h('strong', {}, 'Source record'), caption("In the source system's own field names."), jsonBlock(source, 420)),
    h('div', {}, h('strong', {}, 'JSON-LD'), caption('The same record in shared terms, ready to check.'), jsonBlock({ '@graph': graph }, 420)));
}

const INT_WHY = '**Why this layer exists**\n\nThis layer is where a use case meets the semantic layer. A record from the use case is written as **JSON-LD**, a form of linked data: its fields keep the source system\'s names, and a mapping turns each one into a shared term that points into the semantic layer, for example a technique or an indicator in AML typology.\n\n- **One mapping per system, not one per pair.** Without it, every system and every agent is wired to the ontology by hand. With it, a system is mapped once and any agent can read it.\n- **The same word means the same thing everywhere.** An alert\'s suspected technique and an investigator\'s finding both point to the same technique, so they can be joined and compared.\n- **Records can be checked.** The values are pointers into the dictionary, so code can test them (does the indicator exist, does it belong to the technique) before anyone relies on the record.\n- **Agents get one contract.** Through an API or an MCP tool, an agent reads and writes records in these shared terms, whichever system holds them.';

/* A record field by field: its value, the ontology term it is mapped to, and what a pointer leads to in AML typology. */
function flatten(value, path, leaf, out) {
  if (Array.isArray(value)) value.forEach((v, i) => flatten(v, `${path}[${i}]`, leaf, out));
  else if (value && typeof value === 'object') Object.entries(value).forEach(([k, v]) => flatten(v, path ? `${path}.${k}` : k, k, out));
  else out.push({ path, leaf, value });
}

function linkedTo(value) {
  const snap = DATA.snap, v = String(value);
  if (/^T\d{4}(\.\d{3})?$/.test(v) && snap.techniques[v]) {
    const t = snap.techniques[v];
    return { part: 'AML typology', label: `AML typology ${t.id} ${t.name}`, detail: `${tacticNames(t).join(', ')} · ${t.indicators.length} risk indicators · ${t.dataSources.length} data sources` };
  }
  if (/^DS\d+$/.test(v) && snap.dimensions.dataSources[v]) {
    const d = snap.dimensions.dataSources[v];
    return { part: 'AML typology · data source', label: `AML typology ${d.id} ${d.name}`, detail: 'A data source listed for techniques: a record where evidence can be found' };
  }
  if (/^IND\d+$/.test(v) && snap.indicators[v]) return { part: 'Risk indicators', label: `AML typology risk indicator ${v}`, detail: shorten(snap.indicators[v], 130) };
  return null;
}

/* The mapping row for each source field name in an area. A row such as "a / b" covers several fields; a row for one field wins. */
function mappingByField(area) {
  const by = new Map();
  DATA.integ.mapping.filter((r) => r.Area === area).forEach((r) => r['Source field'].split(' / ').forEach((f) => {
    if (!by.has(f) || r['Source field'] === f) by.set(f, r);
  }));
  return by;
}

/* The diagram is an SVG string built by ontology/mapping_diagram.py, so parse it as an SVG document rather than as HTML. */
function mappingDiagram(scenario) {
  const d = DATA.integ.diagram[scenario];
  const doc = new DOMParser().parseFromString(d.svg, 'image/svg+xml');
  const svg = document.importNode(doc.documentElement, true);
  return h('div', { class: 'card' },
    h('strong', {}, 'How the investigation data schema maps onto the ontology'),
    caption('Left: the records of the case system, with their own field names. Right: the ontology they are mapped to. Middle: what the integration layer ' +
      'does to each record. Each record sits on the same row as its ontology class. The mapping is defined by people and applied by code; no model is involved.'),
    h('div', { class: 'diagram', style: { maxWidth: '1245px', margin: '0 auto' } }, svg),
    h('p', {}, d.records), h('p', {}, d.checks));
}

/* How the identification side's alerts meet AML typology: the flags of the three monitoring systems, the mapping table, the techniques. */
function identificationDiagram() {
  const d = DATA.integ.diagram_identification;
  const svg = document.importNode(new DOMParser().parseFromString(d.svg, 'image/svg+xml').documentElement, true);
  return h('div', { class: 'card' },
    h('strong', {}, 'How the alerts of the monitoring systems meet the ontology'),
    caption('Left: what the three monitoring systems raise, each in its own terms. Middle: the integration layer, a mapping table that says which AML typology techniques a flag points to. ' +
      'Right: those techniques, each with its risk indicators. The mapping is defined by people and applied by code; no model is involved. It maps concepts (flag to technique), ' +
      'not fields: the three alert formats have no JSON-LD context in this demo.'),
    h('div', { class: 'diagram s4', style: { maxWidth: '1245px' } }, svg),
    h('ol', {}, d.steps.map((t) => h('li', {}, t))),
    d.example ? h('div', {}, h('button', { class: 'btn', type: 'button', onclick: () => select('ag2') }, `See payment ${d.example} in Agent (Risk identification)`)) : null);
}

/* The Investigation ontology entry (class or property) behind a term such as inv:alertId. */
function investigationTerm(term) {
  const inv = DATA.inv, cls = inv.classes.find((c) => c.id === term);
  if (cls) return { label: cls.label, detail: cls.comment || 'A class of the Investigation ontology.' };
  const prop = inv.properties.find((q) => q.id === term);
  if (!prop) return null;
  const domain = inv.classes.find((c) => c.id === prop.domain);
  return { label: prop.label, detail: prop.comment || `A property of ${domain ? domain.label : prop.domain}.` };
}

function linkEntry(part, title, detail) {
  return h('div', { class: 'ba-target' }, h('div', { class: 'part' }, part), h('strong', {}, title), h('div', { class: 'muted' }, detail));
}

function recordView(source, contextName, area, intro, outro, held) {
  const ctx = DATA.integ.contexts[contextName], items = [], mapped = mappingByField(area);
  flatten(source, '', '', items);
  const rows = items.filter((r) => r.leaf in ctx).map((r, i) => {
    const entry = ctx[r.leaf];
    const term = typeof entry === 'string' ? entry : entry['@id'] || '';
    const kind = typeof entry === 'string' ? '' : entry['@type'] || '';
    const link = kind === '@id' ? linkedTo(r.value) : null;
    const info = investigationTerm(term);
    const target = h('div', {},
      info ? linkEntry('Investigation ontology', info.label, info.detail) : null,
      link ? linkEntry(link.part, link.label, link.detail) : null,
      kind === '@id' && !link ? h('div', { class: 'muted' }, 'The value points to another record in the same data.') : null,
      !info && !link && kind !== '@id' ? h('span', { class: 'muted' }, '–') : null);
    const m = mapped.get(r.leaf);
    const becomes = h('div', {}, h('strong', {}, CONVERTED[kind] || 'kept as text'),
      m ? h('div', { class: 'muted' }, `${m['Mapping type']}: ${TYPE_NOTE[m['Mapping type']] || ''}`) : null);
    const why = m ? m['Why (plain)'] : h('span', { class: 'muted' }, '–');
    return { key: i, cells: [h('code', {}, r.path), String(r.value), longTerm(term), target, becomes, why] };
  });
  return h('div', {}, caption(intro),
    dataTable([`Field in the ${held.noun}`, `Value in the ${held.noun}`, 'Term in the ontology', 'Linked to in the AML ontology', 'The mapping', 'Why'], rows,
      { maxHeight: 520, colClass: ['recv', 'recv', 'link', 'link', 'link', 'link'],
        groups: [[held.group, 2, 'recv'], ['Mapping to the AML ontology', 2, 'link'], ['Why the mapping is this way', 2, 'link']] }),
    h('div', { class: 'card', style: { marginTop: '12px' } }, md(HOW_TO_READ)), outro);
}

const REC_INTRO = {
  int2: "The alert the investigator receives from the detection system. The first two columns are the data in the alert, exactly as it arrives: the " +
    "system's own field names and values. The next two columns link each field to the AML ontology: the term it is mapped to, and what that term and the value " +
    'lead to in the semantic layer. The last two show the mapping itself, meaning what the value becomes and what kind of term it is, and why the field is mapped this way.',
  s1: 'The suggested checks for an alert, as a case system would hold them, one check per indicator. The first two columns are the data at the case system; ' +
    'the next two columns link it to the AML ontology, and the last two show the mapping and why.',
  s2: 'A case with its findings and report draft, as the case system holds it. The first two columns are the data at the case system; the next two ' +
    'columns link it to the AML ontology, and the last two show the mapping and why.',
};

function rawView(source, graph) {
  return h('details', { class: 'card', style: { marginTop: '12px' } },
    h('summary', {}, 'Show the record as JSON next to the resulting JSON-LD'),
    h('div', { style: { marginTop: '10px' } }, sourceView(source, graph)));
}

function renderIntegration(root, id) {
  const snap = DATA.integ, area = INT_AREA[id];
  root.append(h('div', { class: 'card' }, md(INT_WHY),
    caption('In this demo the mapping and the checks are real. There is no API or MCP server behind them yet.')), caption(INT_INTRO[area]));
  if (id === 'int1') {
    root.append(mappingView(area), caption('Nothing is mapped for this area, so there is no sample to show.'));
  } else {
    const body = h('div');
    root.append(body);
    const show = () => {
      if (id === 'int2') {
        const t = DATA.agent.s1.technique, ty = DATA.agent.s1.typology;
        const outro = h('div', { class: 'callout' },
          `The detection system said only "${snap.alerts.source.suspected_technique}". As a pointer into AML typology it lets the investigator's agent take the ${ty.indicators.length} risk indicators and ` +
          `${ty.data_sources.length} data sources listed for ${t.name}, and suggest what to check first.`,
          h('div', { style: { marginTop: '6px' } }, h('button', { class: 'btn', type: 'button', onclick: () => select('ag3') }, 'See this in Agent (investigation)')));
        body.replaceChildren(identificationDiagram(), recordView(snap.alerts.source, 'alert', 'alerts', REC_INTRO.int2, outro, { noun: 'alert', group: 'Received in the alert' }), rawView(snap.alerts.source, snap.alerts.graph));
      } else if (INTS.scenario === 's3') {
        /* Scenario 3 has no record to map: the integration layer is the data dictionary of the table. */
        const dic = snap.dictionary;
        body.replaceChildren(pills(INT_SCENARIOS, INTS.scenario, (v) => { INTS.scenario = v; show(); }), mappingDiagram('s3'),
          h('h3', {}, `The data dictionary of the table ${dic.table}`),
          caption('What the LLM is given about the table: for each column its type and what it means in words. Written by people.'),
          dataTable(['Column', 'Type', 'Meaning'], dic.columns.map((c) => ({ key: c.name, cells: [h('code', {}, c.name), c.type, c.meaning] })), { maxHeight: 420 }),
          h('div', { style: { marginTop: '8px' } }, h('button', { class: 'btn', type: 'button', onclick: () => select('ag3') }, 'See this in Agent (investigation)')));
      } else {
        const sc = snap.investigation[INTS.scenario];
        const outro = h('div', { class: 'callout' }, 'Every indicator, technique and data source is a pointer into AML typology, so code can check each one before anyone relies on the record: ' +
          'does it exist, and does it belong to the suspected technique?');
        body.replaceChildren(pills(INT_SCENARIOS, INTS.scenario, (v) => { INTS.scenario = v; show(); }), mappingDiagram(INTS.scenario),
          recordView(sc.source, sc.context, 'investigation', REC_INTRO[INTS.scenario], outro, { noun: 'record', group: 'Data at the case system' }), rawView(sc.source, sc.graph));
      }
    };
    show();
  }
  root.append(caption(`From ${snap.meta.source}, exported ${snap.meta.exported}. The sample records stand for what a detection system and a case system would send. The alert and the case are built from one payment in the synthetic IBM AML data (the one in scenario 4); the checklist, findings and report draft are written by code as stand-ins for a source system and an investigator.`));
}
