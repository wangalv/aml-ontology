/* The boxes of the architecture map. Mirrors ITEMS in portal/semantic_tab.py. */
const SEMANTIC = {
  typ: 'AML typology', ind: 'Risk indicators', scn: 'Risk scenarios', inv: 'Investigation ontology', kmg: 'Knowledge management',
};
const BADGE = { 'Live data': 'green', 'Sample': 'blue', 'Design only': 'gray', 'Placeholder': 'orange' };
const DEFAULT_ITEM = 'ml';

/* id: name, kind, relies on, preview title, preview text, without a semantic layer, with a semantic layer */
function item(name, kind, relies, preview, text, without, withSL) {
  return { name, kind, relies, preview, text, without, with: withSL };
}

const ITEMS = {
  acct: item('Account', 'Placeholder', ['inv'], 'Source rows',
    "Raw account records, shown with the source system's own field names.",
    'Each system names the same thing differently.', 'A JSON-LD interface maps the fields to one shared term.'),
  party: item('Party', 'Placeholder', ['inv'], 'Source rows',
    'Customer records with KYC fields as the source holds them.',
    'Customer risk fields differ by system.', 'One shared customer term across systems.'),
  tx: item('Transaction', 'Placeholder', ['inv'], 'Source rows',
    'A handful of transactions in their original columns.',
    'Columns are tied to one platform.', 'Mapped once, reusable by every consumer.'),
  other: item('Other data', 'Design only', ['inv'], 'Note',
    'Where further data sources would plug in.',
    'Every new source is a new integration project.', 'A new source needs only its own JSON-LD interface.'),
  er: item('Entity resolution', 'Sample', ['inv'], 'Before and after',
    'Two records for the same party in two systems, linked into one entity.',
    'Links live inside one tool and cannot be explained.', 'The link is a stated assertion with method and confidence.'),
  fs: item('Feature store', 'Placeholder', ['ind'], 'Table',
    'The model features, each tagged with the risk indicator it expresses.',
    'A feature name says little about the risk.', 'Features trace back to named indicators.'),
  lm: item('List management', 'Placeholder', ['scn', 'kmg'], 'Table',
    'PEP, high-risk industry and high-risk country lists.',
    'Lists are flat and unexplained.', 'Each list ties to a scenario and a policy.'),
  ml: item('ML based detection', 'Placeholder', ['typ', 'ind'], 'Alert, side by side',
    'One ML alert in its native format, next to the same alert as JSON-LD.',
    'The alert carries a score and column names only.', 'The alert names a typology and indicators others can read.'),
  rule: item('Rule based detection', 'Placeholder', ['typ', 'ind', 'scn'], 'Alert, side by side',
    'One rule alert in its native format, next to the same alert as JSON-LD.',
    'A rule id and a threshold.', 'The rule is linked to the typology and scenario it covers.'),
  graph: item('Graph based detection', 'Placeholder', ['typ', 'ind'], 'Alert, side by side',
    'A cycle alert in its native format, next to the same alert as JSON-LD.',
    'A list of account ids in a loop.', 'The loop is tied to the circular transactions typology.'),
  osol: item('Other FinCrime solutions', 'Sample', ['typ', 'ind'], 'Alert, side by side',
    'An alert from a different vendor format, mapped to the same terms.',
    'Each vendor needs its own reader.', 'New solutions join by adding one interface.'),
  ucm: item('Case Management', 'Sample', ['inv', 'kmg'], 'Case record',
    'A case with findings, evidence and a draft report, as JSON-LD.',
    'Case notes are free text.', 'Findings are structured and each report paragraph cites one.'),
  ag1: item('Agent (data management)', 'Design only', ['inv'], 'Note',
    'An agent that proposes entity links and list matches.',
    'It guesses without shared meaning.', 'It works from the shared terms and records why.'),
  ag2: item('Agent (identification)', 'Design only', ['typ', 'ind'], 'Note',
    'Scenario 3: turns a typology and its indicators into a detection query, and measures it against labels.',
    'Detection logic is written by hand for each typology.',
    "The agent writes the query from the typology's indicators, and a guard checks it."),
  ag3: item('Agent (investigation)', 'Sample', ['typ', 'ind', 'inv', 'kmg'], 'Advice and report draft',
    'Scenarios 1 and 2: suggested next checks for an alert, then a report draft that cites findings.',
    'The agent invents ids and cannot be checked.', 'Every suggestion and citation is checked by code.'),
  int1: item('Integration (data management)', 'Design only', ['inv'], 'Mapping table',
    'How source data (accounts, parties, transactions) reaches the semantic layer: one JSON-LD interface per source, ' +
    'exposed through an API or an MCP tool.',
    'Every source is wired to every consumer by hand.', 'Each source is mapped once to shared terms and reused.'),
  int2: item('Integration (identification)', 'Live data', ['typ', 'ind', 'scn'], 'Mapping table',
    'How detection systems send alerts in, and ask the semantic layer for typologies and indicators.',
    'Each detection system speaks its own alert format.', 'Alerts and typologies meet through one shared set of terms.'),
  int3: item('Integration (investigation)', 'Live data', ['typ', 'ind', 'inv', 'kmg'], 'Mapping table',
    'How the investigation agent reads alerts and cases as JSON-LD and looks up indicators, data sources, policies ' +
    'and past cases.',
    'The agent is wired to each case system separately.', 'One contract lets any agent read any case system.'),
  typ: item('AML typology', 'Live data', [], 'Technique table and graph',
    'The list of laundering techniques and how they relate.',
    'Each team keeps its own typology list.', 'One reference list, versioned.'),
  ind: item('Risk indicators', 'Live data', [], 'Indicator list',
    'The indicators for a chosen technique, with data sources.',
    'Indicators sit in policy documents.', 'Indicators are identifiable and linkable.'),
  scn: item('Risk scenarios', 'Placeholder', [], 'Note',
    'To be defined: how typologies combine with country, product or customer type.',
    'Scenarios live in spreadsheets.', 'Scenarios link to typologies and indicators.'),
  inv: item('Investigation ontology', 'Live data', [], 'Classes and shapes',
    'Alerts, cases, findings and reports, and the rules for a valid record.',
    'Case data has no agreed shape.', 'Records can be checked before anyone relies on them.'),
  ent: item('Enterprise semantic layer', 'Design only', [], 'Note',
    "The bank's central, shared definitions of terms such as customer, account, product and jurisdiction, owned " +
    'outside financial crime. The FinCrime semantic layer would build on them and add only what is specific to ' +
    'financial crime. This is also where party, account and transaction would come from: AMLO has none of them, ' +
    'which is the gap shown under Integration (data management).',
    'Each domain defines customer and account for itself, so the same word means different things.',
    'Domains share one definition and add only their own terms.'),
  kmg: item('Knowledge management', 'Placeholder', [], 'Policies and cases',
    'Policies and past cases the agents can draw on.',
    'Knowledge is searched by keyword.', 'Knowledge is linked to typologies and indicators.'),
};
