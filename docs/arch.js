/* The "Semantic Layer Architecture" tab: the six layers, drawn as HTML so it follows the page theme and wraps on a narrow screen. No data files; the text is written here. */
const ARCH_LAYERS = [
  { n: 1, color: '#6b7280', name: 'External Knowledge',
    what: 'Published typologies, techniques, indicators and data-source definitions. Reused as published, not edited.',
    code: 'amx:T0039   (Circular Transactions)\n  amlo:isIndicatedBy  amx:IND02191' },
  { n: 2, color: '#6b7280', name: 'AML Core Ontology',
    what: 'Canonical AML concepts and relationships, independent of any database or typology.',
    code: 'amd:originator\n  rdfs:domain amd:FundsTransfer ; rdfs:range amd:Account' },
  { n: 3, color: '#6b7280', name: 'Typology Requirements',
    what: 'What each indicator needs, expressed only in concepts of the AML core ontology.',
    code: 'amx:IND02191  align:needsTerm\n  amd:originator , amd:beneficiary , amd:transferTime' },
  { n: 4, color: '#6b7280', name: 'Data Semantics & Alignment',
    what: 'The vocabulary of the source data, and how each source term corresponds to an AML concept.',
    code: 'fcd:fromAccount\n  rdfs:subPropertyOf  amd:originator' },
  { n: 5, color: '#6b7280', name: 'OBDA Mapping',
    what: 'Maps source tables and columns to the source vocabulary. The only layer that knows the physical schema.',
    code: 'fcd:fromAccount  ←  column tx.from_account\n  (R2RML triples map over table tx_features)' },
  { n: 6, color: '#6b7280', name: 'Validation & Execution',
    what: 'Builds evidence, applies explicit rules (SHACL + code), returns a verdict and what could not be checked.',
    code: '[consecutive_legs_connect]\n  Consecutive legs must connect' },
];

function archCard(l, row) {
  const card = h('div', { class: 'arch-layer', style: row ? { gridRow: String(row), gridColumn: '2' } : {} },
    h('div', { class: 'num' }, String(l.n)),
    h('div', { class: 'body' }, h('div', { class: 'name' }, l.name), h('p', {}, l.what)),
    h('div', { class: 'ex' }, h('div', { class: 'ex-tag' }, 'Example'), h('pre', {}, l.code)));
  card.style.setProperty('--c', l.color); // a custom property cannot be set through Object.assign on style
  return card;
}

function archView() {
  const five = ARCH_LAYERS.slice(0, 5);
  const layers = h('div', { class: 'arch-layers' },
    five.map((l, i) => archCard(l, i + 1)),
    h('div', { class: 'arch-bracket', style: { gridRow: '2 / span 4' } }, h('span', {}, 'Semantic and data-access layers')));
  return h('div', {},
    h('div', { class: 'note' }, 'This is an example, not a prescribed design. It is here to highlight the considerations in building a semantic layer.'),
    h('div', { class: 'arch-grid' },
      h('div', { class: 'arch-llm' }, h('b', {}, 'LLM'), h('span', {}, 'interprets the request and explains the result · never writes SQL, never sees a table or column')),
      h('div', { class: 'arch-obda' },
        h('div', { class: 'arch-obda-head' }, h('b', {}, 'OBDA'), h('span', {}, 'layers 1 to 5 are read together as one virtual knowledge graph · a question in business concepts is rewritten to SQL on the source')),
        layers),
      h('div', { class: 'arch-six' }, h('div', { class: 'arch-down' }, '↓'), archCard(ARCH_LAYERS[5])),
      h('div', { class: 'arch-foot' }, 'The model interprets · the semantic layer defines meaning and access · explicit rules decide')));
}
