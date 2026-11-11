/* The "Operating model" tab: the same business delivered two ways, as two cards side by side. No data files; the text is written here. */
const SVG_NS = 'http://www.w3.org/2000/svg';
const ICONS = {
  database: [['ellipse', { cx: 12, cy: 5, rx: 7, ry: 3 }], ['path', { d: 'M5 5v14c0 1.7 3.1 3 7 3s7-1.3 7-3V5' }], ['path', { d: 'M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3' }]],
  code: [['path', { d: 'M8 7l-5 5 5 5' }], ['path', { d: 'M16 7l5 5-5 5' }], ['path', { d: 'M14 4l-4 16' }]],
  product: [['rect', { x: 3, y: 4, width: 18, height: 12, rx: 2 }], ['path', { d: 'M8 20h8M12 16v4' }]],
  semantics: [['circle', { cx: 12, cy: 5, r: 2.5 }], ['circle', { cx: 5, cy: 18, r: 2.5 }], ['circle', { cx: 19, cy: 18, r: 2.5 }], ['path', { d: 'M11 7.3L6 15.8M13 7.3l5 8.5' }]],
  agent: [['rect', { x: 4, y: 8, width: 16, height: 11, rx: 3 }], ['circle', { cx: 9, cy: 13.5, r: 1 }], ['circle', { cx: 15, cy: 13.5, r: 1 }], ['path', { d: 'M12 8V4M10 4h4' }]],
  people: [['circle', { cx: 9, cy: 8, r: 3 }], ['path', { d: 'M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6' }], ['circle', { cx: 17, cy: 9, r: 2.5 }], ['path', { d: 'M16 14.2c2.8.3 5 2.6 5 5.8' }]],
};

function icon(name) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  for (const [k, v] of Object.entries({ viewBox: '0 0 24 24', width: 24, height: 24, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) svg.setAttribute(k, v);
  for (const [tag, attrs] of ICONS[name]) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    svg.append(el);
  }
  return svg;
}

const MODES = [
  {
    tone: 'a',
    title: 'Application-driven development',
    stages: [
      { who: 'Business', what: 'Raises business requirements, describes business processes, and provides business rules and acceptance criteria.' },
      { who: 'Product', what: 'Analyses requirements, designs the product and user experience, sets feature priorities and coordinates delivery.' },
      { who: 'IT / Engineering', what: 'Builds data integration, APIs, data models, application logic and rule engines, and handles system integration and deployment.' },
    ],
    outcome: [['database', 'Data'], ['code', 'Application'], ['product', 'Product']],
    note: 'Business knowledge ends up scattered across requirement documents, application code, data models and rule implementations.',
  },
  {
    tone: 'b',
    title: 'Semantic-driven agent development',
    stages: [
      { who: 'Business', what: 'Defines business concepts, relationships, rules, decision criteria and acceptance outcomes, and takes part in confirming and governing semantic knowledge.' },
      {
        who: 'Semantic foundation',
        parts: [
          ['External knowledge', 'AML typology: techniques, indicators and their data sources'],
          ['AML concepts and requirements', 'Canonical AML concepts, and the concepts each indicator needs'],
          ['Data alignment and mapping', 'Source vocabulary aligned to the AML concepts, mapped to tables and columns (R2RML)'],
        ],
        what: 'IT is responsible for the technology platform, the implementation of the semantic model, data mapping, integration, security, performance and operational governance. Business experts take part in defining and validating the knowledge.',
      },
      { who: 'Product', what: 'Designs agent products on top of the shared business capabilities: user interaction, business scenarios, workflows and product experience.' },
      { who: 'IT / AI engineering', what: 'Provides the agent runtime, MCP / API, model integration, access control, evaluation, monitoring and deployment.' },
    ],
    outcome: [['semantics', 'Shared semantics'], ['agent', 'Reusable agents'], ['people', 'Business outcomes']],
    note: 'Business knowledge settles into a shared asset that many agents can reuse, instead of being re-understood and re-implemented in every project.',
  },
];

function modeCard(m) {
  const stages = [];
  m.stages.forEach((s, i) => {
    if (i) stages.push(h('div', { class: 'down', 'aria-hidden': 'true' }, '↓'));
    stages.push(h('div', { class: 'stage' + (s.parts ? ' foundation' : '') },
      h('div', { class: 'who' }, s.who),
      s.parts && h('div', { class: 'parts' }, s.parts.map(([name, what]) => h('div', { class: 'part' }, h('div', { class: 'part-name' }, name), h('div', { class: 'part-what' }, what)))),
      h('p', { class: 'what' }, s.what)));
  });
  const outcome = [];
  m.outcome.forEach(([ic, label], i) => {
    if (i) outcome.push(h('div', { class: 'right', 'aria-hidden': 'true' }, '→'));
    outcome.push(h('div', { class: 'out-box' }, icon(ic), h('div', {}, label)));
  });
  return h('section', { class: 'mode ' + m.tone },
    h('h2', {}, m.title),
    h('div', { class: 'stages' }, stages),
    h('div', { class: 'outcome' }, h('div', { class: 'who' }, 'Typical delivery outcome'), h('div', { class: 'out-row' }, outcome), h('p', { class: 'what' }, m.note)));
}

function modesView() {
  return h('div', {},
    caption('The same business, delivered two ways. The difference is where the business knowledge lives.'),
    h('div', { class: 'modes' }, MODES.map(modeCard)));
}
