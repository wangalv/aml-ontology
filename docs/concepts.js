/* The "AML concepts and requirements" box: the AML vocabulary the indicators talk about, and what each indicator needs from it.
   Written here, not read from a data file. The terms and the Turtle come from the AML OBDA demo (ontology/core/aml_core.ttl and
   ontology/application/typology_requirements.ttl), a draft that no domain expert has reviewed. */

/* [term, kind, meaning, can the data answer it?] The data answers a term when the mapping below this box has something under it. */
const AML_TERMS = [
  ['FundsTransfer', 'Class', 'A transfer of funds from one account to another.', true],
  ['Account', 'Class', 'An account that takes part in a transfer.', true],
  ['transferId', 'Property', 'Identifier of the transfer.', true],
  ['transferTime', 'Property', 'When the transfer happened.', true],
  ['originator', 'Property', 'The account the funds leave (the paying account).', true],
  ['beneficiary', 'Property', 'The account the funds arrive at (the receiving account).', true],
  ['sameInstitution', 'Property', 'True when both accounts are at the same bank; false means between banks. Between banks is not cross-border: the data has no country.', true],
  ['Jurisdiction', 'Class', 'The country or legal territory a transfer or an entity belongs to. The data has no country.', false],
  ['CompanyGroup', 'Class', 'A group of companies under common control.', false],
  ['SupportingDocument', 'Class', 'A document that supports a transfer or a claim.', false],
  ['Invoice', 'Class', 'An invoice.', false],
  ['Shipment', 'Class', 'A shipment of goods.', false],
  ['LegalEntity', 'Class', 'A legal entity.', false],
  ['BeneficialOwnerChange', 'Class', 'A change of beneficial owner of an entity.', false],
  ['DeclaredBusinessActivity', 'Class', 'The business activity an entity declares.', false],
  ['amountRaw', 'Property', 'The raw amount of a transfer. The data has only a logarithm of it.', false],
  ['LogisticsEvidence', 'Class', 'Evidence that goods or services were delivered.', false],
  ['EntityLifecycleEvent', 'Class', 'The founding, change or dissolution of an entity.', false],
];

/* What each indicator of the technique Circular Transactions (T0039) needs, in AML terms. */
const T0039_NEEDS = [
  ['IND02191', ['FundsTransfer', 'originator', 'beneficiary', 'transferTime']],
  ['IND02192', ['CompanyGroup', 'SupportingDocument']],
  ['IND02193', ['Invoice', 'Shipment']],
  ['IND02194', ['LegalEntity', 'BeneficialOwnerChange']],
  ['IND02195', ['FundsTransfer', 'sameInstitution', 'Jurisdiction']],
  ['IND02196', ['DeclaredBusinessActivity', 'amountRaw']],
  ['IND02197', ['Shipment', 'Invoice']],
  ['IND02198', ['LegalEntity', 'EntityLifecycleEvent']],
  ['IND02199', ['Shipment', 'LogisticsEvidence']],
];

const TTL_CONCEPTS = `@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix amd:  <https://example.org/aml-data#> .

# A concept the data can speak about
amd:FundsTransfer a owl:Class ;
    rdfs:comment "A transfer of funds from one account to another." .

amd:originator a owl:ObjectProperty ;
    rdfs:domain amd:FundsTransfer ; rdfs:range amd:Account ;
    rdfs:comment "The account the funds leave (the paying account)." .

# A concept the indicators talk about but this data cannot speak about.
# It is declared, and nothing is mapped under it.
amd:Jurisdiction a owl:Class ;
    rdfs:comment "The country or legal territory a transfer or an entity belongs to. The data has no country." .`;

const TTL_REQUIREMENTS = `@prefix amd:   <https://example.org/aml-data#> .
@prefix fcd:   <https://example.org/fincrime-data#> .
@prefix align: <https://example.org/align#> .
@prefix amx:   <https://example.org/amltrix/> .   # entries of the AML typology

# What each indicator needs, written in AML concepts and not in columns
amx:IND02191 align:needsTerm amd:FundsTransfer , amd:originator , amd:beneficiary , amd:transferTime .
amx:IND02195 align:needsTerm amd:FundsTransfer , amd:sameInstitution , amd:Jurisdiction .

# Where each concept is recorded: a data source of the typology
amd:originator   align:recordedIn amx:DS0019 .   # DS0019 Transaction Logs
amd:Jurisdiction align:recordedIn amx:DS0047 .   # DS0047 Correspondent and Cross-Border Transaction Data

# Context shown to the investigator for a technique. It is not evidence for any indicator.
amx:T0039 align:backgroundTerm fcd:customerType , fcd:industry , fcd:onboardingTenureDays , fcd:pepFlag , fcd:riskRating .`;

const CONCEPT_SECTIONS = ['AML concepts', 'Requirements'];
const CONCEPTS = { section: CONCEPT_SECTIONS[0] };

function answerable() { return new Set(AML_TERMS.filter((t) => t[3]).map((t) => t[0])); }

/* "Can check" when the data answers every concept an indicator needs, "Partly" when it answers some, "Cannot check" when it answers none. */
function checkable(needs) {
  const ok = answerable();
  const n = needs.filter((t) => ok.has(t)).length;
  if (n === needs.length) return ['green', 'Can check'];
  return n ? ['orange', 'Partly'] : ['gray', 'Cannot check here'];
}

function ttlBlock(title, text) {
  return h('div', { style: { marginTop: '12px' } }, caption(title), h('pre', { style: { maxHeight: '420px' } }, text));
}

function conceptsSection() {
  const yes = AML_TERMS.filter((t) => t[3]).length;
  return h('div', {},
    h('p', {}, 'The vocabulary the indicators talk about, written in AML words: it names no database and no typology. ' +
      `There are ${AML_TERMS.length} concepts here. The data can speak about ${yes} of them; the other ${AML_TERMS.length - yes} are concepts the indicators ` +
      'need but this data does not hold. They are declared all the same, because an indicator that needs them should be answered with "cannot check", not left out.'),
    dataTable(['Concept', 'Kind', 'Meaning', 'The data can answer it'],
      AML_TERMS.map(([term, kind, meaning, ok]) => ({ key: term, cells: [h('code', {}, 'amd:' + term), kind, meaning, ok ? badge('green', 'Yes') : badge('gray', 'No')] })),
      { maxHeight: 460 }),
    ttlBlock('Example in Turtle: three of the concepts (excerpt)', TTL_CONCEPTS));
}

function requirementsSection() {
  const texts = (DATA.snap && DATA.snap.indicators) || {};
  const rows = T0039_NEEDS.map(([id, needs]) => {
    const [color, label] = checkable(needs);
    return { key: id, cells: [id, shorten(texts[id], 150), needs.map((t) => h('code', { style: { marginRight: '6px' } }, t)), badge(color, label)] };
  });
  const counts = { 'Can check': 0, 'Partly': 0, 'Cannot check here': 0 };
  T0039_NEEDS.forEach(([, needs]) => { counts[checkable(needs)[1]] += 1; });
  return h('div', {},
    h('p', {}, 'For each indicator, the AML concepts it needs, and where in the typology\'s data sources each concept would be recorded. ' +
      'A requirement names concepts and not columns, so one requirement serves every data source: a different database changes the mapping underneath, not this.'),
    caption('Example: the nine indicators of the technique Circular Transactions (T0039).'),
    dataTable(['Indicator', 'What the typology says', 'Needs', 'With this data'], rows, { maxHeight: 460 }),
    h('p', { style: { marginTop: '10px' } }, `Of the nine, ${counts['Can check']} can be checked, ${counts['Partly']} partly, and ${counts['Cannot check here']} not at all. ` +
      'This is worked out from the table above and from which concepts the data can answer, not typed in by hand. ' +
      'The indicators that cannot be checked are reported as such: the missing concepts are named, and nothing is guessed.'),
    ttlBlock('Example in Turtle: requirements, sources and background (excerpt)', TTL_REQUIREMENTS));
}

function renderConcepts(root) {
  const pillBox = h('div'), body = h('div');
  root.append(
    h('p', {}, 'Two things sit in this box, both in AML words and neither tied to a database. ',
      h('strong', {}, 'AML concepts'), ' are the common vocabulary of funds transfers and accounts that the indicators talk about. ',
      h('strong', {}, 'Requirements'), ' say which of those concepts each indicator needs.'),
    caption('A draft written for the demo and not reviewed by a domain expert. The typology gives one sentence per indicator and does not say which concepts it needs, ' +
      'so the concepts and the requirements are our reading of those sentences. The namespace is a placeholder.'),
    pillBox, body);
  function show() {
    pillBox.replaceChildren(pills(CONCEPT_SECTIONS.map((s) => [s, s]), CONCEPTS.section, (s) => { CONCEPTS.section = s; show(); }));
    body.replaceChildren(CONCEPTS.section === 'AML concepts' ? conceptsSection() : requirementsSection());
  }
  show();
}
