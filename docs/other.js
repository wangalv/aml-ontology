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
    caption(`${meta.note} Snapshot of ${meta.source}, exported ${meta.exported}.`));
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
const SAVED = 'Saved output of an earlier run, not a live call: nothing is run when you view this page.';
const ID_SECTION = 'Scenario 1: multi-system alert reasoning';
const AG_SECTIONS = ['Scenario 1: investigation suggestion', 'Scenario 2: investigation traceability', 'Scenario 3: typology-driven query'];
const AG = { section: AG_SECTIONS[0], doc: { s1: false, s2: false }, open: { s1: false, s2: false } };

function definitionBox(text) { return h('div', { class: 'ctx-box' }, text); }

function quote(text) { return h('div', { class: 'quote' }, h('span', { class: 'tag' }, 'From the AML typology'), text); }

function docToggle(key, label, doc, repaint) {
  if (!doc) return null;
  const box = h('input', { type: 'checkbox', checked: AG.doc[key], onchange: (e) => { AG.doc[key] = e.target.checked; repaint(); } });
  return h('div', {}, h('label', {}, box, ' ' + label), AG.doc[key] ? jsonBlock(doc, 360) : null);
}

/* The flow diagram of scenario 1 or 2: what the investigator has, the AML typology the LLM reads, what the LLM writes, what code checks. */
function flowCard(svgText) {
  const svg = document.importNode(new DOMParser().parseFromString(svgText, 'image/svg+xml').documentElement, true);
  return h('div', { class: 'card' }, h('div', { class: 'diagram s4' }, svg));
}

/* The trace of one suggestion: suggestion -> indicator -> technique -> data source. Each link is an id that the AML typology defines. */
function traceOfSuggestion(a, t) {
  const arrow = () => h('span', { class: 'trace-arrow' }, '→');
  return h('div', { class: 'trace' },
    h('span', { class: 'trace-chip' }, 'Suggestion ' + a.priority), arrow(),
    h('span', { class: 'trace-chip', title: a.indicator_text || '' }, h('code', {}, a.indicator)), arrow(),
    h('span', { class: 'trace-chip' }, h('code', {}, t.id), ' ', t.name), arrow(),
    h('span', { class: 'trace-chip' }, h('code', {}, a.data_source), ' ', a.data_source_name || ''));
}

function scenario1(root, repaint) {
  const s1 = DATA.agent.s1, alert = s1.alert, run = s1.real.with, bare = s1.real.without, t = s1.technique, ty = s1.typology;
  const when = String(alert.raised_at).replace('T', ' ').replace('Z', ' UTC');
  const items = run.accepted.map((a) => h('div', { class: 'llm-row' },
    h('div', {}, h('strong', {}, `${a.priority}. `), h('span', { class: 'tag' }, 'AML typology'), h('span', { title: a.indicator_text }, shorten(a.indicator_text, 85)), ' ', h('code', {}, a.indicator),
      '  → look in ', badge('gray', `${a.data_source} ${a.data_source_name}`)),
    h('div', { class: 'llm-reason' }, h('span', { class: 'tag llm' }, 'LLM'), a.reason),
    h('div', { class: 'llm-quote' }, 'Trace: where this suggestion comes from'),
    traceOfSuggestion(a, t)));
  const bareTotal = bare.accepted.length + bare.rejected.length;
  const invented = [...new Set(bare.rejected.map((r) => ((String((r.problems || [])[0] || '').match(/IND\d+/) || [])[0])).filter(Boolean))];
  root.append(h('p', {}, 'When an alert comes in, the LLM tells the investigator what to check first and where to look. The semantic layer gives it what the alert does not hold: what the AML typology says to look for. ' +
      'And every suggestion can be followed back to an indicator and a data source that the typology names.'),
    flowCard(s1.diagram),
    h('div', { class: 'card' },
      h('div', { class: 'big-label' }, '1  The alert the investigator receives'),
      h('div', {}, h('strong', {}, `Alert ${alert.alert_id}`), ` · raised ${when} · suspected technique `, badge('blue', `${t.id} ${t.name}`)),
      h('div', { class: 'alert-line' }, alert.trigger_reason),
      caption('What the monitoring systems attached to this transaction'),
      h('ul', { class: 'fact-list' }, (alert.facts || []).map((f) => h('li', {}, f))),
      caption('Facts from the rule engine, the ML model and the transaction graph. They say what was detected, not what to check or where to look.')),
    h('div', { class: 'flow-arrow' }, `▼  the LLM reads the alert and what the AML typology says about ${t.id}: its risk indicators and data sources`),
    h('div', { class: 'llm-box' },
      h('div', { class: 'big-label' }, '2  What the LLM suggests the investigator checks, with its trace'),
      caption('Every indicator and data source below is taken from the AML typology; the LLM adds why each one fits this alert. It sees only the alert, no other records.'),
      items,
      caption(`Checked by code: ${run.accepted.length} of ${run.accepted.length + run.rejected.length} suggestions name a real indicator of ${t.id} and a data source the AML typology lists for it, and the advice as JSON-LD passes the rules of the Investigation ontology. ` +
        'Not checked: whether a reason fits the alert. The investigator decides what to do.')),
    h('details', { class: 'card', open: AG.open.s1, ontoggle: (e) => { AG.open.s1 = e.target.open; } },
      h('summary', {}, 'What the LLM was given from the AML typology, and the JSON-LD of the advice'),
      caption(`With the typology text, ${run.accepted.length} of ${run.accepted.length + run.rejected.length} suggestions pass the checks. Without it, ${bare.accepted.length} of ${bareTotal} pass: the LLM does not know which indicators belong to ${t.id}, ` +
        `so it names ones that do not${invented.length ? ` (${invented.slice(0, 3).join(', ')}${invented.length > 3 ? ', …' : ''})` : ''}. One saved run, not a measurement.`),
      h('div', { class: 'ctx-title', style: { marginTop: '8px' } }, `What AML typology says about ${t.id} ${t.name}`),
      caption('Definition'), definitionBox(t.definition),
      docToggle('s1', 'Show the JSON-LD that code built from the accepted advice, after it passed the checks', run.doc, repaint)));
}

/* The trace of one finding: finding -> indicator -> technique -> evidence -> data source. Every link is an id that the AML typology defines. */
function traceOf(findingId, s2) {
  const c = s2.case, t = s2.technique, ds = DATA.snap.dimensions.dataSources;
  const f = c.findings.find((x) => x.finding_id === findingId);
  if (!f) return h('div', { class: 'trace' }, findingId);
  const arrow = () => h('span', { class: 'trace-arrow' }, '→');
  const chips = [h('span', { class: 'trace-chip' }, 'Finding ' + findingId.replace(/^F-/, '')), arrow(),
    h('span', { class: 'trace-chip', title: s2.indicator_text[f.indicator] || '' }, h('code', {}, f.indicator)), arrow(),
    h('span', { class: 'trace-chip' }, h('code', {}, f.technique), ' ', f.technique === t.id ? t.name : '')];
  const evidence = (f.supported_by || []).map((id) => c.evidence.find((e) => e.evidence_id === id)).filter(Boolean);
  if (evidence.length) {
    evidence.forEach((e) => chips.push(arrow(), h('span', { class: 'trace-chip' }, h('code', {}, e.evidence_id)), arrow(),
      h('span', { class: 'trace-chip' }, h('code', {}, e.record_type), ' ', (ds[e.record_type] || {}).name || '')));
  } else chips.push(arrow(), h('span', { class: 'trace-chip none' }, 'no evidence: not assessed'));
  return h('div', { class: 'trace' }, chips);
}

function scenario2(root, repaint) {
  const s2 = DATA.agent.s2, c = s2.case, run = s2.real.with, t = s2.technique, bare = s2.real.without, cov = s2.coverage[0];
  const findingName = (id) => 'Finding ' + id.replace(/^F-/, '');
  const STATUS = { supported: 'green', 'not-supported': 'red', inconclusive: 'orange', 'not-assessable': 'gray', 'not-looked-at': 'orange' };
  const findings = c.findings.map((f) => h('div', { class: 'llm-row' },
    h('div', {}, h('strong', {}, `${findingName(f.finding_id)}  `), badge(STATUS[f.status] || 'gray', f.status), ' ', h('code', {}, f.indicator)),
    h('div', { class: 'alert-line' }, f.observation)));
  const paragraphs = run.accepted.map((p) => h('div', { class: 'llm-row' },
    h('div', { class: 'llm-reason' }, h('span', { class: 'tag llm' }, 'LLM'), p.text),
    h('div', { class: 'llm-quote' }, 'Trace: where this paragraph comes from'),
    p.based_on.map((b) => traceOf(b, s2))));
  const states = (rep) => rep.accepted.some((p) => new RegExp(`\\b(${cov.total}|${['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'][cov.total] || cov.total})\\b`, 'i').test(p.text));
  root.append(h('p', {}, 'When the investigation is done, the LLM drafts the findings section of the report. The semantic layer gives it something the case does not hold: how much of the technique the findings cover. ' +
      'And every paragraph can be followed back through its finding and evidence to a data source that the AML typology names.'),
    flowCard(s2.diagram),
    h('div', { class: 'card' },
      h('div', { class: 'big-label' }, '1  What the investigator has: the findings of the case'),
      h('div', {}, h('strong', {}, `Case ${c.case_id}`), ' · investigating ', badge('blue', `${t.id} ${t.name || ''}`)),
      findings,
      caption('Written by code from the same transaction, as a stand-in for an investigator\'s notes. No report wording, and nothing says what the indicators mean.')),
    h('div', { class: 'flow-arrow' }, `▼  the LLM reads the findings, what the AML typology says about ${t.id}, and a count: the findings are about ${cov.looked_at} of its ${cov.total} indicators`),
    h('div', { class: 'llm-box' },
      h('div', { class: 'big-label' }, '2  What the LLM writes: the findings section of the report, with its trace'),
      caption('Under each paragraph: the chain from the finding it cites to the data source. Hover an indicator to read what the AML typology says about it.'),
      paragraphs,
      caption(`Checked by code: every paragraph cites a real finding of this case, names only technique and indicator ids that belong to the findings it cites, and a statement such as "3 of the ${cov.total} indicators" must match the count. ` +
        'The draft as JSON-LD must also pass the validation of the Investigation ontology: a supported finding has evidence, and a paragraph has a finding. ' +
        'Not checked: whether the wording is faithful to a finding. The investigator reviews every draft.')),
    h('details', { class: 'card', open: AG.open.s2, ontoggle: (e) => { AG.open.s2 = e.target.open; } },
      h('summary', {}, 'What the LLM was given from the AML typology, and the JSON-LD of the draft'),
      caption((states(run) ? `With the typology text and the count, the draft says how much of the technique the findings are about (it names the ${cov.total} indicators). ` : 'With the typology text and the count, the draft does not state the number of indicators. ') +
        (states(bare) ? 'Without them, the draft also gives a number. ' : `Without them, the draft cannot say it: nothing tells the LLM that the technique has ${cov.total} indicators. `) +
        `(${run.accepted.length} paragraphs with, ${bare.accepted.length} without; none rejected either way.)`),
      h('div', { class: 'ctx-title', style: { marginTop: '8px' } }, `What AML typology says about ${t.id} ${t.name}`),
      caption('Definition of the technique'), definitionBox(t.definition || ''),
      caption('What the indicators in these findings mean'),
      h('div', { class: 'ctx-box' }, Object.entries(s2.indicator_text).map(([id, text]) => h('div', { class: 'ctx-row' }, h('code', {}, id), text))),
      docToggle('s2', 'Show the JSON-LD that code built from the accepted draft, after it passed the checks', run.doc, repaint)));
}

function scenario3(root) {
  const s3 = DATA.agent.s3, sp = s3.sparql, rw = s3.rewrite, r = s3.result;
  const svg = document.importNode(new DOMParser().parseFromString(s3.diagram, 'image/svg+xml').documentElement, true);
  const attemptNote = (n, refused) => n > 1 ? ` It was accepted on attempt ${n}; the earlier attempt was refused: ${refused.map((x) => x.join(' ')).join(' ')}` : '';
  const pre = (text) => h('pre', { style: { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' } }, text);
  root.append(
    h('p', {}, 'An investigator wants to test a hypothesis: that funds are being round-tripped. The indicator in the AML typology speaks in business terms (funds revert to the same origin across multiple accounts), while the database speaks in columns. An ontology names the business terms and an R2RML mapping says which column each term is; here an LLM does what an OBDA engine such as Ontop would: it uses them to turn the indicator into SQL. In the saved run that SQL was run on the transactions table and returned the transactions that fit. The mapping is shown in Integration (investigation), Scenario 3.'),
    h('div', { class: 'card' }, h('div', { class: 'diagram s4' }, svg)),
    h('div', { class: 'card' },
      h('div', { class: 'big-label' }, '1  The task: find the transactions that fit one indicator'),
      h('p', {}, `The investigator picks one risk indicator of ${s3.technique.id} ${s3.technique.name} and wants the transactions in the database that fit the pattern it describes.`),
      h('div', {}, h('strong', {}, `${s3.indicator.id}`), ' · AML typology'),
      h('div', { class: 'alert-line' }, s3.indicator.text),
      caption('The database holds payments, not indicators, so the words of the indicator have to be turned into a query. Only the part the data can show is queried: the cycle of payments, not whether it lacks a business rationale.')),
    h('div', { class: 'flow-arrow' }, '▼  the LLM turns the indicator into a query over the ontology\'s business terms, then into SQL using the mapping'),
    h('div', { class: 'big-label', style: { marginTop: '8px' } }, '2  What the LLM writes: the SQL, and where each part comes from'),
    pre(rw.sql_pretty || rw.sql),
    dataTable(['Words of the indicator', 'The SQL it became', 'Ontology terms', 'Columns'],
      s3.trace.map((g, i) => ({ key: i, cells: [
        h('div', { class: 'quote' }, h('span', { class: 'tag' }, 'AML typology'), g.words, g.quote_found ? badge('green', 'found in the indicator') : badge('red', 'not in the indicator')),
        h('div', {}, g.sql.map((q) => h('div', {}, h('code', {}, q)))),
        h('div', {}, g.terms.map((t) => h('div', {}, h('code', {}, t)))),
        h('div', {}, g.columns.map((c) => h('div', {}, h('code', {}, c))))] })), { maxHeight: 420 }),
    caption('Checked by code before it ran: one read-only SELECT with a LIMIT; tried on a small made-up table, it had to flag the transactions of a loop and none of a straight chain; ' +
      'and it reads only the columns that the ontology terms stand for in the mapping. The laundering label is not in the table the LLM can query.'),
    h('div', { class: 'big-label', style: { marginTop: '8px' } }, '3  Result: what the SQL returned'),
    caption(`In the saved run the SQL returned ${r.n_rows} rows in ${r.seconds} s: ${r.distinct} different transactions (a transaction that sits in two loops appears twice). These are transactions that take part in a three-step ` +
      'chain which comes back to its first account, within the test period. They are what the indicator describes, not a finding that the money is laundered.'),
    dataTable(r.columns.map((c) => (c === 'amount_log' ? 'amount' : c)), r.rows.map((row, i) => ({ key: i, cells: row.map((v, k) => (r.columns[k] === 'amount_log' ? (Math.exp(Number(v)) - 1).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(v))) })), { maxHeight: 420 }),
    h('details', { class: 'card' }, h('summary', {}, 'Under the hood: the two steps, the SPARQL query and the mapping rules'),
      h('p', {}, 'The model works in two steps. First it reads the indicator and the data ontology and writes a query over the ontology terms (SPARQL); it never sees a column name. ' +
        'Then, standing in for an engine such as Ontop, it rewrites that query into the SQL above, using the R2RML mapping.'),
      h('h4', {}, 'Step 1: the SPARQL query over the ontology'), pre(sp.text),
      dataTable(['Part of the query', 'Words of the indicator the LLM says it comes from'],
        sp.patterns.map((c, i) => ({ key: i, cells: [h('code', {}, c.pattern), h('div', { class: 'quote' }, c.from_indicator, c.quote_found ? badge('green', 'found') : badge('red', 'not found'))] })), { maxHeight: 320 }),
      h('h4', {}, 'Step 2: the rewrite into SQL'),
      dataTable(['Part of the query', 'The SQL it became', 'Rule of the mapping it used'],
        rw.steps.map((c, i) => ({ key: i, cells: [h('code', {}, c.sparql), h('code', {}, c.sql), c.mapping] })), { maxHeight: 360 }),
      h('div', { class: 'callout' }, h('strong', {}, 'Checked by code. '),
        h('div', {}, `✓ The SPARQL parsed and used only terms the ontology defines (${sp.terms.join(', ')}).` + attemptNote(sp.attempts, sp.refused)),
        h('div', {}, '✓ The SQL passed the guard: one read-only SELECT over the listed columns, with a LIMIT, a tx_id column and the time column ts.' + attemptNote(rw.attempts, rw.refused)),
        h('div', {}, '✓ Because the indicator says the funds return to where they started, the SQL was tried on a small made-up table: it flagged the transactions of a loop and none of a straight chain.'),
        h('div', {}, `✓ The SQL reads ${rw.used_columns.join(', ')}: exactly the columns the mapping gives for the terms the SPARQL uses, and tx_id.`),
        h('div', { class: 'muted' }, 'Not checked: that every join of the SQL means what the SPARQL means, or that the SPARQL captures the indicator.'))));
}

function renderInvestigationAgent(root) {
  const pillBox = h('div'), body = h('div');
  root.append(pillBox, body);
  function show() {
    pillBox.replaceChildren(pills(AG_SECTIONS.map((s) => [s, s]), AG.section, (s) => { AG.section = s; show(); }));
    const inner = h('div');
    body.replaceChildren(caption(SAVED), inner);
    [scenario1, scenario2, scenario3][AG_SECTIONS.indexOf(AG.section)](inner, show);
  }
  show();
}

const money = (n) => Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const SYS_COLOR = { rule: 'blue', ml: 'orange', graph: 'green' };
const SYS_NAME = { rule: 'rule engine', ml: 'ML model', graph: 'transaction graph' };
const sysBadge = (k) => badge(SYS_COLOR[k], SYS_NAME[k]);

function renderIdentificationAgent(root) {
  const s4 = DATA.agent.s4, e = s4.examples[0], p = e.payment, snap = DATA.snap;
  const svg = document.importNode(new DOMParser().parseFromString(e.diagram, 'image/svg+xml').documentElement, true);
  const litRows = e.lamps.filter((r) => r.systems.length), agreeRows = litRows.filter((r) => r.systems.length > 1);
  const bySystems = (rows) => rows.map((r) => `${r.id} is supported by the ${r.systems.map((k) => SYS_NAME[k]).join(' and the ')}`).join(', ');
  const agreeLine = agreeRows.length ? `${bySystems(agreeRows)}.` : `no technique has that: ${bySystems(litRows)}.`;
  const dropped = ['rule', 'graph'].flatMap((k) => ((e.lanes[k] || {}).dropped || []).map((d) => ({ ...d, system: k })));
  const techBox = h('div');
  const total = e.techniques.reduce((a, t) => a + t.indicators.length, 0), evLabel = Object.fromEntries(e.evidence.map((x) => [x.id, x.flag || (x.kind === 'ml' ? 'ML score' : 'transaction details')]));
  const evById = Object.fromEntries(e.evidence.map((x) => [x.id, x]));
  const spell = (t) => String(t).replace(/\bE(\d)\b/g, (m) => (evLabel[m] ? `${m} (${evLabel[m]})` : m));  // E4 -> E4 (graph_roundtrip)
  const wordsOf = (r) => { const own = r.evidence.map((id) => evById[id]).filter((x) => x && x.kind === r.system); const ev = own[0] || evById[r.evidence[0]]; return ev ? ev.text : ''; };
  const systemColumn = (system, rows) => h('div', { class: 'sys-col' },
    h('div', {}, sysBadge(system), ' ', h('span', { class: 'muted' }, 'says, in its own words:')),
    h('div', { class: 'sys-words' }, shorten(wordsOf(rows[0]), 170)),
    ...rows.map((r) => h('div', { class: 'llm-row' },
      h('div', { class: 'muted' }, '↓ the LLM matches it to the AML typology indicator'),
      h('div', {}, h('code', {}, r.indicator), ` ${r.support === 'yes' ? 'supported' : 'partly supported'} `, r.pointed ? null : badge('orange', "read from the evidence, not the system's own flag")),
      h('div', { class: 'llm-quote' }, h('span', { class: 'tag' }, 'AML typology'), shorten(r.indicator_text, 110)),
      h('div', { class: 'llm-reason' }, h('strong', {}, 'LLM: '), spell(r.reason), ' ', h('span', { class: 'muted' }, `(evidence: ${r.evidence.map((id) => evLabel[id] || id).join(', ')})`)))));
  // the page follows the technique more than one system supports, and what the other systems add that the rule engine does not support
  const shown = agreeRows.length ? litRows.filter((r) => r === agreeRows[0] || !r.systems.includes('rule')) : litRows;
  const groups = shown.map((row) => {
    const rows = e.rows.filter((r) => r.technique === row.id), systems = [...new Set(rows.map((r) => r.system))];
    return h('div', { class: 'tech-group' + (systems.length > 1 ? ' agree' : '') },
      h('div', {}, h('strong', {}, `${row.id} ${(rows[0] || {}).technique_name || ''}`), ' ', systems.length > 1 ? badge('green', systems.map((k) => `${SYS_NAME[k]}: ${rows.some((r) => r.system === k && r.support === 'yes') ? 'supported' : 'partly'}`).join(' · ')) : badge('gray', '1 system')),
      caption(systems.map((k) => `${SYS_NAME[k]}: ` + (rows.some((r) => r.system === k && r.pointed) ? 'its own flag points here' : 'read by the LLM from the evidence')).join(' · ')),
      systems.length > 1 ? caption('The systems use different words. The AML typology gives them one shared vocabulary, so both can be read as pointing to this technique' + (systems.some((k) => !rows.some((r) => r.system === k && r.support === 'yes')) ? ', one of them only partly.' : '.')) : null,
      h('div', { class: systems.length > 1 ? 'cols2' : '' }, ...systems.map((k) => systemColumn(k, rows.filter((r) => r.system === k)))));
  });
  /* What Team A would be told: put together by code from the results below, not written by the model. */
  const tname = (id) => `${id} ${(e.rows.find((x) => x.technique === id) || {}).technique_name || ''}`.trim();
  const sysList = (ks) => ks.map((k) => `the ${SYS_NAME[k]}`).join(' and ');
  const ownRows = shown.filter((r) => r.systems.includes('rule')), addedRows = shown.filter((r) => !r.systems.includes('rule'));
  const cyc = p.cycle, ml = (e.mapping.systems.ml || {}).score;
  const told = [
    ...ownRows.map((r) => `Your system supports ${tname(r.id)}.` + r.systems.filter((k) => k !== 'rule').map((k) => ` ${sysList([k])[0].toUpperCase() + sysList([k]).slice(1)} also points to it${r.cells[k].state === 'partly' ? ', but only partly' : ''}.`).join('')),
    ...addedRows.map((r) => `${sysList(r.systems)[0].toUpperCase() + sysList(r.systems).slice(1)} adds ${tname(r.id)}` +
      (r.systems.includes('graph') && cyc ? `: a verified cycle of ${cyc.legs.length} payments that returns to the origin account ${cyc.accounts[0]} over ${cyc.span_days} days` : '') +
      (r.cells.rule.pointed ? '.' : ", which none of your system's flags point to.")),
    ml != null ? `The ML model gives a score of ${ml} and no reason, so it cannot be read.` : null].filter(Boolean);
  const teamBox = h('div', { class: 'card', style: { fontSize: '0.85em' } },
    h('div', {}, h('strong', {}, 'What Team A would be told')),
    h('div', {}, h('strong', {}, 'Team A asks: '), 'What do the other systems say about this payment?'),
    h('div', { style: { marginTop: '4px' } }, h('strong', {}, 'The answer: '), told.join(' ')),
    h('div', { class: 'caption', style: { fontSize: '0.75rem' } }, 'Put together by code from the results below, not written by the model.'));
  const llmBox = h('div', { class: 'llm-box' },
    h('div', {}, badge('violet', 'LLM'), ' ', h('strong', {}, 'What the LLM concluded')),
    caption(`Each system describes the transaction in its own terms. The LLM reads each one against the ${total} risk indicators of the AML typology (${e.techniques.length} techniques), which gives the systems one shared vocabulary. ` +
      'A team can then read another system\'s reasons in the terms it already knows. Where two systems land on the same technique, both read it as pointing to the same concern, though one may support it only partly. Code only checks the ids, the citations and the numbers.'),
    ...groups,
    dropped.length ? h('div', { class: 'dropped-box' },
      h('div', {}, badge('red', `Not accepted (${dropped.length})`), ' ', h('strong', {}, 'Removed by the code: the AML typology limits what the LLM can conclude')),
      caption('An indicator counts as supported only if the evidence says what the indicator says. The LLM listed these matches, but its reason claimed more than the evidence it cites, so they are not shown as support.'),
      ...dropped.map((d) => h('div', { class: 'llm-row' }, h('div', {}, sysBadge(d.system), ' → ', h('code', {}, d.indicator), ' ', h('span', { class: 'muted' }, 'removed')),
        h('div', { class: 'llm-reason' }, h('strong', {}, 'LLM: '), spell(d.reason)), h('div', { class: 'dropped-why' }, 'Why it was removed: ' + d.problems.join(' '))))) : '');

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
      parts.push(h('div', { class: 'card tight' }, h('strong', {}, `What lit ${row.id} for this transaction`),
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

  const flowSvg = document.importNode(new DOMParser().parseFromString(e.flow, 'image/svg+xml').documentElement, true);
  root.append(pills([[ID_SECTION, ID_SECTION]], ID_SECTION, () => {}), caption(SAVED),
    h('p', {}, 'Rules, a machine-learning model and a graph analysis monitor transactions in separate systems, with their own teams, data and business logic. ' +
      "Usually a team can see another system's alerts only if the data is merged or the applications are connected, and the other team's business logic is still hard to learn. " +
      "With a semantic layer, each system maps its business logic to shared terms once, and an agent helps a team read what the other systems say, with the data left where it is."),
    h('div', { class: 'card' }, h('strong', {}, 'Why a semantic layer'),
      h('div', { class: 'diagram s4', style: { maxWidth: '1245px' } }, flowSvg),
      h('div', { style: { marginTop: '8px' } }, h('button', { class: 'btn', type: 'button', onclick: () => select('int2') }, 'See the mapping in Integration (Risk identification)'))),
    h('div', { class: 'card' },
      h('div', {}, h('strong', {}, `Transaction ${p.tx_id}`), ' ', p.sources.map((k) => [sysBadge(k), ' '])),
      caption(`${p.ts.slice(0, 16)} · ${money(p.amount)} ${p.currency} by ${p.format} · from ${p.from} to ${p.to} · the first transaction, in a fixed random order (seed ${s4.seed}), that all three systems alerted on`),
      h('div', { class: 'diagram s4' }, svg)),
    teamBox,
    llmBox,
    techBox,
    caption('Checked by code: every indicator is one that was listed under the techniques the flags point to (strong and medium links; weak ones are not given to the model); every reason cites evidence that exists, and its numbers and amounts appear in it. ' +
      `A note that fails is sent back once (at most ${s4.limits.max_attempts} attempts). Not checked: whether a reason says only what the evidence says, so read the reasons. The technique mapping is a first draft. The ML model gives a score and no reason, so it is shown but not judged.`));
}

/* ---------- Integration ---------- */
const INT_AREA = { int1: 'data', int2: 'alerts', int3: 'investigation' };
const INT_INTRO = {
  data: 'Source data such as accounts, parties and transactions has no mapping yet. AMLO describes laundering techniques and indicators, and has no party, ' +
    'account or transaction concepts. So this interface still has to be designed.',
  alerts: "How an alert from a detection system arrives. The fields keep the source system's own names; a JSON-LD context maps each one to a shared term, " +
    'and the suspected typology becomes a pointer into AML typology.',
  investigation: '',
};
const INT_SCENARIOS = [['s1', 'Scenario 1: investigation suggestion'], ['s2', 'Scenario 2: investigation traceability'], ['s3', 'Scenario 3: typology-driven query']];
const TYPE_NOTE = { extension: 'a term the Investigation Ontology adds; the value is kept as it is', transform: 'the value is converted to another form, such as a pointer to an AML typology entry or to another record, or a date', unresolved: 'no term yet' };
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
  '- **Term in the ontology** is the shared term the field is mapped to, with the ontology it comes from: the Investigation ontology or AML typology. The same term is used whichever system the record comes from. In the JSON-LD the ontology is shortened to a prefix: `inv:` for the Investigation ontology and `amx:` for AML typology.',
  '- **Linked to in the AML ontology** shows what the field connects to in the semantic layer. Every mapped field links to its term in the Investigation ontology, with the definition. When the value is a pointer into AML typology, the cell also shows the entry it leads to and which part of the semantic layer it belongs to: a technique (AML typology), a risk indicator, or a data source. Risk scenarios are not defined yet, so no field links to one.',
  '- **The mapping:** the bold line is what the field\'s value becomes. The line under it is the mapping type: an extension is a term the Investigation ontology adds, with the value kept as it is, and a transform converts the value to another form, such as a pointer to an AML typology entry or to another record, or a date. The possible values are:',
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

const INT_WHY = '**Purpose.** Let agents and applications use data from any source in the semantic layer\'s shared terms, without learning every system\'s own field names (a source says `from_account`, an indicator says "the origin of the funds").\n\n**Business-case driven.** The semantic layer can cover the whole business, but the integration layer is built one business case at a time: for each agent or application use case, it connects the data that use case needs. The pages below follow the demo\'s scenarios.\n\nTechnology stack to consider:\n\n- **Core: link the source to the ontology** (built in this demo). JSON-LD for records (Scenarios 1 and 2); OBDA for databases (Scenario 3, a design). Agents and applications can use the core directly.\n- **Wrapper: optional** (not built or tested here). To give agents and applications a standard way to call the semantic layer, the integration layer can be wrapped in MCP, a Skill or an API; the core can be used without it.';

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
    h('details', { class: 'card', style: { marginTop: '12px' } }, h('summary', {}, 'How to read the table'), h('div', { style: { marginTop: '10px' } }, md(HOW_TO_READ))), outro);
}

const REC_INTRO = {
  s1: 'The suggested checks for an alert, as a case system would hold them, one check per indicator. The first two columns are the data at the case system; ' +
    'the next two columns link it to the AML ontology, and the last two show the mapping and why.',
  s2: 'A case with its findings, evidence and report draft, as the case system holds it. The links between the records (paragraph to finding, finding to evidence, evidence to data source) are what let a report be traced. ' +
    'The first two columns are the data at the case system; the next two columns link it to the AML ontology, and the last two show the mapping and why.',
};

function rawView(source, graph) {
  return h('details', { class: 'card', style: { marginTop: '12px' } },
    h('summary', {}, 'Show the record as JSON next to the resulting JSON-LD'),
    h('div', { style: { marginTop: '10px' } }, sourceView(source, graph)));
}

/* Scenario 3 in an OBDA design: the transaction table, the R2RML mapping (the integration layer), the data ontology terms, and the AML typology data source. */
function obdaView() {
  const ex = DATA.obda;
  const svg = document.importNode(new DOMParser().parseFromString(ex.svg, 'image/svg+xml').documentElement, true);
  return h('div', {},
    h('div', { class: 'card' },
      h('strong', {}, `How the transaction table maps onto the ontology (OBDA design)`),
      h('ol', { style: { margin: '6px 0 0', paddingLeft: '20px' } },
        h('li', {}, 'The indicator speaks in business terms ("funds revert to the same origin across multiple accounts"); the database speaks in columns (from_account, to_account, ts).'),
        h('li', {}, 'This layer sits between them. The ontology names the business terms (transaction, from account, to account, timestamp). An R2RML mapping says which column each term is, ' +
          'for example from account is the column from_account. Both are written once, as files, not described in prose to the model.'),
        h('li', {}, 'An OBDA engine such as Ontop uses them to turn a query on the terms into SQL on the table. No engine is installed here: in the Agent page an LLM does the rewrite, ' +
          'and code checks its SQL against this mapping.')),
      caption('Left: the columns of the table. Middle: the R2RML mapping. Right: the ontology terms the columns become. Far right: the AML typology entries the ontology points to.'),
      h('div', { class: 'diagram', style: { maxWidth: '1245px', margin: '0 auto' } }, svg)),
    h('h3', {}, `The mapping, term by term`),
    caption('Read from the R2RML file and the ontology by code. The meaning of each term is written in the ontology, where the terms are defined.'),
    dataTable(['Ontology term', 'Built from the column(s)', 'How', 'Meaning'], ex.mapping.map((r) => ({ key: r.term, cells: [h('code', {}, r.term), r.from, r.how, r.meaning] })), { maxHeight: 420 }),
    h('details', {}, h('summary', {}, 'The R2RML mapping'), h('pre', { style: { maxHeight: '420px' } }, ex.r2rml)),
    h('details', {}, h('summary', {}, 'The FinCrime data ontology'), h('pre', { style: { maxHeight: '420px' } }, ex.ontology)));
}

/* The alert tables of the three detection systems in an OBDA design: the columns the mapping reads, the R2RML mapping, the data ontology terms, and the AML typology techniques the flags point to. */
function obdaAlertsView() {
  const ex = DATA.obdaAlerts;
  const parse = (text) => document.importNode(new DOMParser().parseFromString(text, 'image/svg+xml').documentElement, true);
  const flow = parse(ex.flow_svg), flags = parse(ex.flags_svg);
  return h('div', {},
    h('div', { class: 'card' },
      h('strong', {}, 'How the alert tables map onto the ontology (OBDA design)'),
      h('ol', { style: { margin: '6px 0 0', paddingLeft: '20px' } },
        h('li', {}, 'The three detection systems alert for different reasons and say different things: the rule engine names the rules that fired, the ML model gives a score and no reason, the transaction graph says the transaction lies on a verified loop. Each keeps its alerts in its own table.'),
        h('li', {}, 'This layer gives every alert the same shape. The ontology names the terms (alert, the transaction it is about, the source system, the flag that fired, the ML score), and an R2RML mapping per table says which columns they are. Each table is mapped only for what its own system says. Each flag also points to the AML typology technique it relates to (a draft), so that alerts from different systems can be compared by the risk they point to.'),
        h('li', {}, 'A question on those terms, for example which techniques the flags of the systems point to for a transaction and whether they point to the same one, then needs no knowledge of the three tables. An OBDA engine such as Ontop would rewrite it into one SQL lookup per table. No engine is installed here: a small program applied the mapping to one transaction in the saved run of the identification agent, which is how the agent got its input. So the mapping is a design, run by code, not by an engine.')),
      caption(`Three systems raise alerts, each in its own table. One question about a transaction (here ${ex.example.tx_id}, the transaction of the identification agent) goes through the mapping to all three, and the answers come back in one shape.`),
      h('div', { class: 'diagram', style: { maxWidth: '1245px', margin: '0 auto' } }, flow),
      h('details', {}, h('summary', {}, 'The question as SPARQL, and the lookups the mapping gives'),
        caption('The question in the terms of the ontology. When the page was built it was run over the triples the mapping gives for the transaction, by a small program rather than an engine such as Ontop. Below it, the lookups that the mapping gives on the tables: one per TriplesMap, each restricted to the transaction.'),
        h('pre', {}, ex.question.sparql), h('pre', { style: { maxHeight: '320px' } }, ex.question.lookups.join('\n\n')))),
    h('h3', {}, 'What the flags point to'),
    h('div', { class: 'card' },
      caption('The diagram above shows the flags of one transaction. Here are all of them: what each detection system raises in its own terms, the ontology term the R2RML mapping turns it into (with its name as in the diagram above), and the AML typology techniques that term links to. ' +
        `The links are a first draft, not reviewed by a domain expert. The ontology holds ${ex.link_counts.strong} strong, ${ex.link_counts.medium} medium and ${ex.link_counts.weak} weak links; only the strong and medium ones are drawn and given to the model, the weak ones are context only.`),
      h('div', { class: 'diagram', style: { maxWidth: '1245px', margin: '0 auto' } }, flags)),
    h('h3', {}, 'The mapping, term by term'),
    caption('Read from the R2RML file and the ontology by code. The meaning of each term is written in the ontology, where the terms are defined. Not mapped: ' +
      ex.unmapped.map((u) => `${u.columns.join(', ')} (${u.why})`).join('; ') + '.'),
    dataTable(['Ontology term', 'Built from', 'How', 'Meaning'], ex.mapping.map((r, i) => ({ key: i, cells: [h('code', {}, r.term), r.from, r.how, r.meaning] })), { maxHeight: 420 }),
    h('details', {}, h('summary', {}, `What the mapping gives for transaction ${ex.example.tx_id}`),
      caption('The triples (subject, predicate, object) that the mapping produces for this transaction, computed by code from the three tables when the page was built. Nothing is stored: an engine would build them when a query needs them.'),
      dataTable(['Subject', 'Predicate', 'Object'], ex.example.triples.map((t, i) => ({ key: i, cells: [h('code', {}, t.s.replace('https://example.org/', '')), h('code', {}, t.p), h('code', {}, t.o.replace('https://example.org/', ''))] })), { maxHeight: 420 })),
    h('details', {}, h('summary', {}, 'The R2RML mapping'), h('pre', { style: { maxHeight: '420px' } }, ex.r2rml)),
    h('details', {}, h('summary', {}, 'The FinCrime data ontology'), h('pre', { style: { maxHeight: '420px' } }, ex.ontology)));
}

function renderIntegration(root, id) {
  const snap = DATA.integ, area = INT_AREA[id];
  const introCap = caption(INT_INTRO[area]), footCap = caption(`From ${snap.meta.source}, exported ${snap.meta.exported}. The sample records stand for what a detection system and a case system would send. The alert and the case are built from one transaction in the synthetic IBM AML data (the one the identification agent explains); the checklist, findings and report draft are written by code as stand-ins for a source system and an investigator.`);
  root.append(h('details', { class: 'card' }, h('summary', {}, 'Why this layer exists'), h('div', { class: 'why-cols' },
    h('div', { class: 'why-fig' }, document.importNode(new DOMParser().parseFromString(snap.why_diagram, 'image/svg+xml').documentElement, true)),
    h('div', {}, md(INT_WHY)))), introCap);
  if (id === 'int1') {
    root.append(mappingView(area), caption('Nothing is mapped for this area, so there is no sample to show.'));
  } else {
    const body = h('div');
    root.append(body);
    const show = () => {
      const s3 = id === 'int3' && INTS.scenario === 's3';  /* scenario 3 has no records and no sample: its own text explains it */
      const hide = s3 || id === 'int2';
      introCap.style.display = (hide || !INT_INTRO[area]) ? 'none' : '';
      footCap.style.display = hide ? 'none' : '';
      if (id === 'int2') {
        body.replaceChildren(obdaAlertsView(),
          h('div', { style: { marginTop: '8px' } }, h('button', { class: 'btn', type: 'button', onclick: () => select('ag2') }, 'See this in Risk identification agentic AI use cases')));
      } else if (INTS.scenario === 's3') {
        /* Scenario 3 has no record to map: the integration layer is the R2RML mapping of the table, in an OBDA design. */
        body.replaceChildren(pills(INT_SCENARIOS, INTS.scenario, (v) => { INTS.scenario = v; show(); }), obdaView(),
          h('div', { style: { marginTop: '8px' } }, h('button', { class: 'btn', type: 'button', onclick: () => select('ag3') }, 'See this in Investigation agentic AI use cases')));
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
  root.append(footCap);
}
