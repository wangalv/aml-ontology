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

/* A picture for each model, drawn here in the page's colours: how a business case reaches the data. The two viewBoxes are in the same ratio as the two cards
   (1 : 1.7), so both pictures come out the same height. */
function S(tag, attrs, ...kids) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  kids.flat().forEach((c) => e.append(c));
  return e;
}
const txt = (x, y, t, cls, anchor) => S('text', { x, y, class: 'o-text' + (cls ? ' ' + cls : ''), 'text-anchor': anchor || 'middle', 'dominant-baseline': 'central' }, t);
const rect = (x, y, w, h, cls, rx) => S('rect', { x, y, width: w, height: h, rx: rx || 6, class: 'o-box' + (cls ? ' ' + cls : '') });
const link = (id, x1, y1, x2, y2, cls) => S('line', { x1, y1, x2, y2, class: 'o-line' + (cls ? ' ' + cls : ''), 'marker-end': `url(#${id})` });
const ROWS = [70, 128, 186];

function personIcon(cx, cy, cls) {
  return [S('circle', { cx, cy: cy - 8, r: 6, class: 'o-box ' + (cls || '') }), S('path', { d: `M${cx - 11} ${cy + 13}A11 11 0 0 1 ${cx + 11} ${cy + 13}Z`, class: 'o-box ' + (cls || '') })];
}

function dataStore(cx, cy, rx) {
  const x = cx - rx, top = cy - 14;
  return [S('path', { d: `M${x} ${top}V${cy + 14}A${rx} 8 0 0 0 ${x + 2 * rx} ${cy + 14}V${top}`, class: 'o-box' }), S('ellipse', { cx, cy: top, rx, ry: 8, class: 'o-box' }), txt(cx, cy + 4, 'Data')];
}

function pill(cx, cy, w, t) {
  return [S('rect', { x: cx - w / 2, y: cy - 12, width: w, height: 24, rx: 12, class: 'o-pill' }), txt(cx, cy, t)];
}

function opic(kind) {
  const app = kind === 'app', id = 'arr-' + kind, W = app ? 430 : 731;
  const svg = S('svg', { viewBox: `0 0 ${W} 276`, class: 'opic ' + kind, role: 'img', preserveAspectRatio: 'xMidYMid meet',
    'aria-label': app ? 'Each business case needs a person and a function of the application to reach the data'
      : 'Agents reach the data through one shared semantic layer of concepts and relationships; people handle judgment and exceptions' },
    S('defs', {}, S('marker', { id, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto' }, S('path', { d: 'M0 0L8 4L0 8z', class: 'o-head' }))));
  if (app) {
    svg.append(rect(190, 24, 140, 212, 'frame'), txt(260, 40, 'Application', 'o-title'));
    ROWS.forEach((y) => svg.append(rect(0, y - 16, 100, 32), txt(50, y, 'Business case'), link(id, 100, y, 122, y), ...personIcon(146, y - 1),
      link(id, 172, y, 203, y), rect(204, y - 15, 112, 30), txt(260, y, 'Function'), link(id, 316, y, 362, y), ...dataStore(392, y, 28)));
    return svg;
  }
  svg.append(rect(204, 24, 376, 212, 'frame sem'), S('rect', { x: 205, y: 25, width: 374, height: 26, rx: 5, class: 'o-band' }), txt(392, 38, 'Semantic layer (ontology)', 'o-title'));
  const edges = [[[392, 82], [392, 110], 'initiates', 400, 96, 'start'], [[298, 122], [360, 122], 'involves', 329, 112], [[424, 122], [486, 122], 'relates to', 455, 112],
    [[372, 134], [320, 162], 'has risk', 330, 148, 'end'], [[412, 134], [464, 162], 'triggered by', 454, 148, 'start']];
  edges.forEach(([[x1, y1], [x2, y2]]) => svg.append(link(id, x1, y1, x2, y2, 'rel')));
  edges.forEach(([, , t, x, y, a]) => svg.append(txt(x, y, t, 'o-edge', a)));
  svg.append(...pill(392, 68, 100, 'Investigation'), ...pill(268, 122, 60, 'AML'), ...pill(392, 122, 64, 'Alert'), ...pill(530, 122, 88, 'Transaction'), ...pill(302, 172, 60, 'Risk'), ...pill(482, 172, 60, 'Rule'));
  svg.append(S('rect', { x: 205, y: 196, width: 374, height: 39, rx: 5, class: 'o-strip' }));
  ['Domain model', 'Vocabulary', 'Relationships', 'Knowledge'].forEach((t, i) => {
    const cx = 205 + 374 * (i + 0.5) / 4;
    if (i) svg.append(S('line', { x1: 205 + 374 * i / 4, y1: 204, x2: 205 + 374 * i / 4, y2: 227, class: 'o-div' }));
    svg.append(txt(cx, 215, t, 'o-cell'));
  });
  ROWS.forEach((y) => svg.append(rect(0, y - 16, 100, 32), txt(50, y, 'Business case'), link(id, 100, y, 124, y),
    S('circle', { cx: 150, cy: y, r: 24, class: 'o-box' }), txt(150, y, 'agent'), link(id, 174, y, 203, y)));
  ROWS.forEach((y) => svg.append(link(id, 580, y, 634, y), ...dataStore(664, y, 30)));
  svg.append(...personIcon(150, 252, 'dash'), txt(172, 254, 'People: judgment and exceptions', 'o-note', 'start'),
    link(id, 150, 238, 150, 212, 'dash'));
  return svg;
}

const MODES = [
  {
    tone: 'a',
    pic: 'app',
    lead: 'Built for one business case at a time. Each case needs its own person, working through its own function of the application, and the logic and the data are tightly coupled.',
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
    pic: 'sem',
    lead: 'One shared semantic layer gives every agent the same domain knowledge, so solutions are composable and consistent. People step in for judgment and exceptions.',
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

function stageBox(s) {
  return h('div', { class: 'stage' + (s.parts ? ' foundation' : '') },
    h('div', { class: 'who' }, s.who),
    s.parts && h('div', { class: 'parts' }, s.parts.map(([name, what]) => h('div', { class: 'part' }, h('div', { class: 'part-name' }, name), h('div', { class: 'part-what' }, what)))),
    h('p', { class: 'what' }, s.what));
}

function modeCard(m) {
  /* The semantic foundation is a shared asset, not a step in the hand-over, so it sits in its own column to the right of the steps. */
  const steps = [];
  m.stages.filter((s) => !s.parts).forEach((s, i) => {
    if (i) steps.push(h('div', { class: 'down', 'aria-hidden': 'true' }, '↓'));
    steps.push(stageBox(s));
  });
  const foundation = m.stages.find((s) => s.parts);
  const outcome = [];
  m.outcome.forEach(([ic, label], i) => {
    if (i) outcome.push(h('div', { class: 'right', 'aria-hidden': 'true' }, '→'));
    outcome.push(h('div', { class: 'out-box' }, icon(ic), h('div', {}, label)));
  });
  return h('section', { class: 'mode ' + m.tone + (foundation ? ' wide' : '') },
    h('h2', {}, m.title),
    h('div', { class: 'pic' }, opic(m.pic), h('p', { class: 'what' }, m.lead)),
    h('div', { class: 'stages' + (foundation ? ' two' : '') },
      h('div', { class: 'steps' }, steps),
      foundation && h('div', { class: 'side' }, stageBox(foundation))),
    h('div', { class: 'outcome' }, h('div', { class: 'who' }, 'Typical delivery outcome'), h('div', { class: 'out-row' }, outcome), h('p', { class: 'what' }, m.note)));
}

function modesView() {
  return h('div', {},
    caption('Two operating models for delivering the same business capability. Application-driven development builds each solution case by case, around one business need at a time. Semantic-driven agent development captures business knowledge once as a shared semantic foundation, which every agent then reuses.'),
    h('div', { class: 'modes' }, MODES.map(modeCard)),
    h('div', { class: 'shift' },
      h('div', { class: 'who' }, 'The operating model each approach leads to'),
      h('div', { class: 'shift-row' },
        h('div', { class: 'shift-box from' }, 'People operate applications to complete the process.'),
        h('div', { class: 'shift-box to' }, 'Agents carry out the process within a controlled scope. People make the judgments and handle the exceptions.'))));
}
