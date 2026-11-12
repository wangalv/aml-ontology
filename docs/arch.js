/* The "Semantic Layer Architecture" tab: the six layers, drawn as HTML so it follows the page theme and wraps on a narrow screen. No data files; the text is written here. */
const ARCH_LAYERS = [
  { n: 1, color: '#6b7280', name: 'External Knowledge',
    tech: [['RDF / Turtle', 'the published typology as linked data'], ['SKOS', 'techniques and indicators as concepts'], ['OWL', 'the ontology the published typology comes with']],
    what: 'Published typologies, techniques, indicators and data-source definitions. Reused as published, not edited.',
    code: 'amx:T0039   (Circular Transactions)\n  amlo:isIndicatedBy  [[amx:IND02191]]' },
  { n: 2, color: '#6b7280', name: 'AML Core Ontology',
    tech: [['OWL', 'classes and properties'], ['RDFS', 'domain and range']],
    what: 'Canonical AML concepts and relationships, independent of any database or typology.',
    code: '[[amd:originator]]\n  rdfs:domain amd:FundsTransfer ; rdfs:range amd:Account' },
  { n: 3, color: '#6b7280', name: 'AML Typology Requirements',
    tech: [['OWL', 'the property that links an indicator to the concepts it needs'], ['RDF / Turtle', 'requirements written as triples']],
    what: 'What each indicator of the AML typology needs from the data, written only in AML concepts. This is our reading of each indicator\'s sentence, a draft.',
    code: '[[amx:IND02191]]  align:needsTerm\n  amd:FundsTransfer , [[amd:originator]] , amd:beneficiary , amd:transferTime' },
  { n: 4, color: '#6b7280', name: 'Data Semantics & Alignment',
    tech: [['RDFS', 'subPropertyOf and subClassOf tie source terms to AML concepts'], ['OWL', 'the source vocabulary written as an ontology']],
    what: 'The vocabulary of the source data, and how each source term corresponds to an AML concept.',
    code: '[[fcd:fromAccount]]\n  rdfs:subPropertyOf  [[amd:originator]]' },
  { n: 5, color: '#6b7280', name: 'OBDA Mapping',
    tech: [['R2RML', 'W3C language that maps relational tables to RDF'], ['Ontop', 'an OBDA engine that rewrites SPARQL into SQL; in the scenarios of this site a small program applies the mapping instead'], ['SPARQL', 'the query language, asked in business concepts'], ['SQL views', 'shape the tables before they are mapped']],
    what: 'Maps source tables and columns to the source vocabulary. The only layer that knows the physical schema.',
    code: '[[fcd:fromAccount]]  ←  column [[tx.from_account]]\n  (R2RML triples map over table tx_features)' },
  { n: 6, color: '#6b7280', name: 'Validation & Execution',
    tech: [['SHACL', 'checks graph structure and constraints'], ['SPARQL', 'cross-record checks'], ['Application rules', 'indicator-specific code']],
    what: 'Builds evidence, applies explicit rules (SHACL + code), returns a verdict and what could not be checked.',
    code: '[consecutive_legs_connect]\n  Consecutive legs must connect: the originator\n  of a leg is the beneficiary of the one before' },
];

function archCard(l, row, final) {
  const card = h('div', { class: 'arch-layer' + (final ? ' final' : ''), style: row ? { gridRow: String(row), gridColumn: '2' } : {} },
    h('div', { class: 'num' }, String(l.n)),
    h('div', { class: 'body' }, h('div', { class: 'name' }, l.name), h('p', {}, l.what),
      h('div', { class: 'techs' }, h('span', { class: 'techs-label' }, 'Technology'), l.tech.map(([t, does]) => h('span', { class: 'arch-tech', title: does }, t)))),
    h('div', { class: 'ex' }, h('div', { class: 'ex-tag' }, 'Example'), h('pre', {}, ...l.code.split(/\[\[(.+?)\]\]/).map((t, i) => (i % 2 ? h('mark', { class: 'hl' }, t) : t)))));
  card.style.setProperty('--c', l.color); // a custom property cannot be set through Object.assign on style
  return card;
}

function archView() {
  const layers = h('div', { class: 'arch-layers' },
    ARCH_LAYERS.map((l, i) => archCard(l, i + 1, i === ARCH_LAYERS.length - 1)),
    h('div', { class: 'arch-bracket', style: { gridRow: '2 / span 4' } }, h('span', {}, 'Semantic and data-access layers')));
  return h('div', {},
    h('div', { class: 'note' }, 'This is an example, not a prescribed design. It is here to highlight the considerations in building a semantic layer.'),
    h('div', { class: 'note' }, h('b', {}, 'Follow the red. '), 'One thread is highlighted through the layers: the indicator ', h('code', {}, 'IND02191'), ' (layer 1) needs an originator (layers 2 and 3; layer 3 is where the two meet), the data term ',
      h('code', {}, 'fromAccount'), ' is declared to be a kind of originator (layer 4), the mapping ties ', h('code', {}, 'fromAccount'), ' to the column ', h('code', {}, 'from_account'), ' (layer 5), and the check in layer 6 uses the originator to test that the legs connect.'),
    h('div', { class: 'arch-grid' },
      h('div', { class: 'arch-obda' },
        h('div', { class: 'arch-obda-head' }, h('b', {}, 'Ontology-Based Data Access (OBDA)'), h('span', {}, 'layers 1 to 5 are read together as one virtual knowledge graph · a question in business concepts is rewritten to SQL on the source')),
        layers)));
}
