/* "The graph" tab: one graph of the definition files (.ttl) of the demo, each node coloured by the semantic layer it belongs to.
   Reads data/graph_snapshot.json, which ontology/build_graph_snapshot.py makes from the .ttl files. Layers 2 and 3 have no .ttl file in this demo. */
const TTL_GRAPH_H = Math.max(560, Math.min(860, Math.round(window.innerHeight * 0.74)));   // as tall as the window allows; the panel with the Turtle text sits under it
const GRAPH = { off: new Set(), node: null, center: 'amlo:Technique' };

/* Star layout: the centre node in the middle, the nodes one arrow away on the first ring, two arrows away on the second, and so on.
   The rings are only the starting positions; the physics then lets the nodes settle and they can be dragged. */
const GRAPH_ORDER = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'INV'];
function graphRings(g, v) {
  const nb = {};
  v.nodes.forEach((n) => { nb[n.id] = []; });
  v.edges.forEach(([e]) => { nb[e.from].push(e.to); nb[e.to].push(e.from); });
  const hop = { [GRAPH.center]: 0 };
  const queue = [GRAPH.center];
  while (queue.length) { const x = queue.shift(); (nb[x] || []).forEach((y) => { if (!(y in hop)) { hop[y] = hop[x] + 1; queue.push(y); } }); }
  const far = Math.max(0, ...Object.values(hop)) + 1;
  const rings = {};
  v.nodes.forEach((n) => { const k = Math.min(n.id in hop ? hop[n.id] : far, 3); (rings[k] = rings[k] || []).push(n); }); // three or more arrows away share the outer rings
  const pos = {};
  let radius = 0;
  Object.keys(rings).map(Number).sort((p, q) => p - q).forEach((k) => {
    const list = rings[k];
    if (k === 0) { list.forEach((n) => { pos[n.id] = { x: 0, y: 0 }; }); return; }
    list.sort((p, q) => GRAPH_ORDER.indexOf(p.layer) - GRAPH_ORDER.indexOf(q.layer) || p.id.localeCompare(q.id));
    // a ring with many nodes is split over several tracks, so that the labels do not run into each other
    let rest = list.slice(), track = 0;
    radius += 170;
    while (rest.length) {
      const room = Math.max(6, Math.floor((2 * Math.PI * radius) / 120));
      const take = rest.splice(0, room);
      take.forEach((n, i) => { const a = (2 * Math.PI * i) / take.length + (k + track) * 0.5; pos[n.id] = { x: radius * Math.cos(a), y: radius * Math.sin(a) }; });
      track++;
      if (rest.length) radius += 105;
    }
  });
  return pos;
}

/* Every node is a rectangle with square corners; the kind of node shows in the border: solid and thick = class, solid thin = flag or mapping,
   long dashes = table, short dashes = AML typology technique, dots = shape. */
function graphNodeOptions(n, color, pos) {
  const base = { id: n.id, label: n.label, title: n.label.replace('\n', ' ') + (n.comment ? '\n\n' + n.comment : ''),
    shape: 'box', shapeProperties: { borderRadius: 0 }, borderWidth: 1, color: nodeColor(color), font: { color: '#10211f', size: 14 }, margin: 8 };
  if (pos && pos[n.id]) { base.x = pos[n.id].x; base.y = pos[n.id].y; }
  const dashed = (d, w) => ({ ...base, borderWidth: w, shapeProperties: { borderRadius: 0, borderDashes: d } });
  if (n.id === GRAPH.center) return { ...base, borderWidth: 4, font: { color: '#10211f', size: 20 }, margin: 12 };
  if (n.kind === 'table') return dashed([8, 3], 2);
  if (n.kind === 'technique') return { ...dashed([4, 3], 1), font: { color: '#10211f', size: 13 } };
  if (n.kind === 'shape') return { ...dashed([2, 3], 1), font: { color: '#10211f', size: 13 } };
  if (n.kind === 'mapping' || n.kind === 'property') return { ...base, font: { color: '#10211f', size: 12 } };
  if (n.kind === 'flag' || n.kind === 'requirement') return base;
  return { ...base, borderWidth: 3 };
}

const GRAPH_EDGE = {
  plain: { color: '#78909C', width: 1.6, dashes: false, label: true },
  sub: { color: '#B0BEC5', width: 1, dashes: false },
  strong: { color: '#D85A30', width: 3.2, dashes: false },
  medium: { color: '#D85A30', width: 1.6, dashes: false },
  weak: { color: '#D85A30', width: 1, dashes: [3, 4] },
  map: { color: '#FF8A65', width: 1.2, dashes: false },
  check: { color: '#BA68C8', width: 1.2, dashes: [5, 4] },
  need: { color: '#F9A825', width: 1.2, dashes: false },
  align: { color: '#42A5F5', width: 2, dashes: [6, 3] },
};

function graphEdgeOptions(e, i) {
  const o = GRAPH_EDGE[e.kind] || GRAPH_EDGE.plain;
  return { id: 'e' + i, from: e.from, to: e.to, title: e.label, label: o.label ? e.label : undefined,
    color: { color: o.color, opacity: e.kind === 'sub' ? 0.7 : 1 }, width: o.width, dashes: o.dashes,
    font: { size: 11, color: '#78909C', strokeWidth: 0, align: 'middle' }, arrows: { to: { enabled: true, scaleFactor: 0.5 } } };
}

function graphVisible(g) {
  const layerOf = Object.fromEntries(g.nodes.map((n) => [n.id, n.layer]));
  const nodes = g.nodes.filter((n) => !GRAPH.off.has(n.layer));
  const ids = new Set(nodes.map((n) => n.id));
  const edges = g.edges.map((e, i) => [e, i]).filter(([e]) => ids.has(e.from) && ids.has(e.to));
  return { nodes, edges, layerOf };
}

function graphOptionsStar() {
  return {
    autoResize: true,
    // The nodes start on the rings of graphRings and float apart; the springs of the arrows and the repulsion of the nodes pull them into place,
    // and the movement dies down slowly until the graph is at rest. Dragging a node wakes it up again.
    physics: { enabled: true, solver: 'forceAtlas2Based', maxVelocity: 18, minVelocity: 0.2,
      forceAtlas2Based: { gravitationalConstant: -95, centralGravity: 0.012, springLength: 165, springConstant: 0.05, damping: 0.62, avoidOverlap: 0.5 },
      stabilization: false },
    interaction: { hover: true, zoomView: true, dragNodes: true, tooltipDelay: 150 },
    edges: { smooth: { type: 'continuous' } },
    nodes: { margin: 8 },
  };
}

/* The panel under the graph: what the node is on one line, then its Turtle text on the left and what it points to on the right. */
function graphDetails(g, id) {
  const wrap = h('div', {});
  const n = id && g.nodes.find((x) => x.id === id);
  if (!n) {
    wrap.append(h('b', {}, 'Click a node'), ' ', h('span', { class: 'muted' }, 'Its Turtle (.ttl) text, the file it comes from, and what it points to appear here. The graph floats and then comes to rest: drag a node and the ones linked to it follow. Scroll to zoom; double-click a node to put it in the centre.'));
    return wrap;
  }
  const L = g.layers.find((l) => l.id === n.layer);
  const kindName = { class: 'Class', property: 'Property', requirement: 'Indicator and what it needs', technique: 'AML typology technique', flag: 'Flag', mapping: 'R2RML mapping', table: 'Table', shape: 'SHACL shape' }[n.kind] || n.kind;
  wrap.append(h('div', { class: 'ttl-head' }, h('span', { class: 'title' }, n.label.replace('\n', ' ')), ' ',
    h('span', { class: 'badge', style: { background: L.color, color: '#10211f' } }, L.n ? `Layer ${L.n}` : 'Investigation'), ' ',
    h('span', { class: 'muted' }, `${kindName} · ${L.name}` + (n.ttl ? ` · ${n.file}, line ${n.line}` : ''))));
  const src = n.ttl ? h('pre', { class: 'ttl' }, n.ttl)
    : h('p', { class: 'muted' }, n.kind === 'table' ? 'A table of the database, not a term in a .ttl file. The mappings that read it point to it.' : 'No Turtle block for this node.');
  const out = g.edges.filter((e) => e.from === id), inn = g.edges.filter((e) => e.to === id);
  const label = (x) => (g.nodes.find((m) => m.id === x) || { label: x }).label.replace('\n', ' ');
  const row = (e, other, arrow) => h('li', {}, arrow + ' ', h('i', {}, e.label), ' ', h('a', { href: '#', onclick: (ev) => { ev.preventDefault(); graphSelect(other); } }, label(other)));
  const links = h('div', {});
  if (out.length) links.append(h('b', {}, 'Points to'), h('ul', { class: 'compact' }, out.map((e) => row(e, e.to, '→'))));
  if (inn.length) links.append(h('b', {}, 'Pointed to by'), h('ul', { class: 'compact' }, inn.map((e) => row(e, e.from, '←'))));
  wrap.append(h('div', { class: 'ttl-body' }, src, links));
  return wrap;
}

let graphNet = null, graphData = null, glideTimer = null;
const FLOAT = { on: true };
const GLIDE_START = 18;

/* Let the nodes float, then bring them to rest slowly: the top speed is cut a little every half second until they stop. */
function graphGlide() {
  clearInterval(glideTimer);
  if (!graphNet || !FLOAT.on) return;
  let speed = GLIDE_START;
  graphNet.setOptions({ physics: { enabled: true, maxVelocity: speed } });
  graphNet.startSimulation();
  glideTimer = setInterval(() => {
    if (!graphNet) { clearInterval(glideTimer); return; }
    speed *= 0.86;
    if (speed < 1.5) { clearInterval(glideTimer); graphNet.setOptions({ physics: { enabled: false } }); graphNet.fit({ animation: true }); return; }
    graphNet.setOptions({ physics: { maxVelocity: speed } });
  }, 500);
}

function graphSelect(id) {
  GRAPH.node = id;
  if (graphNet && graphData.nodes.some((n) => n.id === id)) { graphNet.selectNodes([id]); graphNet.focus(id, { scale: 1, animation: true }); }
  graphData.paint();
}

function graphView() {
  const g = DATA.graph;
  const color = Object.fromEntries(g.layers.map((l) => [l.id, l.color]));
  const detailEl = h('div', { class: 'scroll ttl-panel' });
  const graphEl = h('div', { class: 'graph', style: { height: TTL_GRAPH_H + 'px' } });
  const legendEl = h('div', { class: 'legend', style: { height: TTL_GRAPH_H + 'px' } });
  const count = (l) => g.nodes.filter((n) => n.layer === l).length;

  const paintLegend = () => {
    const items = g.layers.map((l) => {
      const n = count(l.id), empty = n === 0, off = GRAPH.off.has(l.id);
      const sw = h('span', { class: 'sw', style: { background: empty ? 'transparent' : l.color, borderStyle: empty ? 'dashed' : 'solid', opacity: off ? 0.3 : 1 } });
      const body = h('div', {}, h('b', {}, l.n ? `${l.n}. ${l.name}` : l.name), ' ', h('span', { class: 'muted' }, empty ? '(no .ttl file)' : `(${n})`), h('br'),
        h('span', { class: 'tx' }, empty ? 'Not drawn: this demo has no file for this layer.' : l.tag));
      const el = h('div', { class: 'legend-item', style: { cursor: empty ? 'default' : 'pointer', opacity: empty ? 0.55 : off ? 0.45 : 1 }, title: empty ? '' : 'Click to show or hide this layer' }, sw, body);
      if (!empty) el.addEventListener('click', () => { GRAPH.off.has(l.id) ? GRAPH.off.delete(l.id) : GRAPH.off.add(l.id); paintLegend(); redraw(); });
      return el;
    });
    legendEl.replaceChildren(h('b', {}, 'Layers'), caption('Click a layer to show or hide it.'), h('div', { style: { height: '4px' } }), ...items,
      h('hr'), h('b', {}, 'Arrows'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#78909C' } }, '━ '), 'a property between classes'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#D85A30' } }, '━ ┅ '), 'a flag points to a technique: thick = strong, thin = medium, dotted = weak'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#FF8A65' } }, '━ '), 'a mapping reads a table and creates a class or flag'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#BA68C8' } }, '┅ '), 'a shape checks a class'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#F9A825' } }, '━ '), 'an indicator needs an AML concept'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#42A5F5' } }, '┅ '), 'our data term is a kind of AML concept'),
      h('div', { class: 'tx' }, h('span', { style: { color: '#B0BEC5' } }, '━ '), 'is a (subclass or individual), has (property)'),
      h('hr'), h('b', {}, 'Node shapes'),
      h('div', { class: 'tx' }, 'All nodes are rectangles. The border tells the kind: thick = class, thin = flag, mapping, property or indicator, long dashes = table, short dashes = AML typology technique, dots = shape.'));
  };

  const redraw = () => {
    const v = graphVisible(g);
    graphData.nodes = v.nodes;
    if (!v.nodes.some((n) => n.id === GRAPH.center)) GRAPH.center = v.nodes[0].id;
    const pos = graphRings(g, v);
    const nodes = v.nodes.map((n) => graphNodeOptions(n, color[n.layer], pos));
    const edges = v.edges.map(([e, i]) => graphEdgeOptions(e, i));
    if (graphNet) { setNet(graphNet, nodes, edges); setTimeout(() => graphNet && graphNet.fit({ animation: true }), 1200); graphGlide(); }
    else whenConnected(graphEl, () => {
      graphNet = makeNet('graph', graphEl, nodes, edges, graphOptionsStar(), (id) => { GRAPH.node = id; detailEl.replaceChildren(graphDetails(g, id)); detailEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); });   // the panel is under the graph: bring it into view
      setTimeout(() => graphNet && graphNet.fit({ animation: true }), 1500);
      graphNet.on('dragStart', () => { clearInterval(glideTimer); if (FLOAT.on) { graphNet.setOptions({ physics: { enabled: true, maxVelocity: GLIDE_START } }); } });
      graphNet.on('dragEnd', () => graphGlide());
      graphGlide();
      graphNet.on('doubleClick', (p) => { if (p.nodes.length) { GRAPH.center = p.nodes[0]; GRAPH.node = p.nodes[0]; redraw(); detailEl.replaceChildren(graphDetails(g, GRAPH.node)); } });
    });
  };
  graphData = { nodes: g.nodes, paint: () => detailEl.replaceChildren(graphDetails(g, GRAPH.node)) };
  graphNet = null;
  paintLegend();
  detailEl.replaceChildren(graphDetails(g, GRAPH.node));
  redraw();

  return h('div', {},
    caption('This is the data used in this demo: its ontology, mapping and shapes files, coloured by semantic layer. In a real setting the picture is far more complex, and the relationships between the layers need to follow a metamodel.'),
    caption('Each box is a term defined in one of the .ttl files: a class, a property, a flag, an indicator, a mapping or a shape. Each arrow is a relationship written in those files, for example a flag pointing to an AML typology technique, an indicator needing an AML concept, or a mapping that creates a class from a table. Read it from the AML typology (layer 1), which says what to look for, through the AML concepts and our data terms (layers 2 to 4), which say what that means in the data, to the mappings and tables (layer 5), which tie it to the database; the shapes (layer 6) check the result. Click a box to see its Turtle text; drag a box and the ones linked to it follow.'),
    h('div', { class: 'ttlg2' }, graphEl, legendEl),
    detailEl,
    caption('Left out: ' + g.omitted + ' Of the AML typology, only T0039 and the techniques the flags point to are drawn.'));
}
