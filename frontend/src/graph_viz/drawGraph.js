import * as d3 from 'd3';
import {
  edgeKey, hopRounds, isFlaggedEdge, riskiestCluster, roleLabel, summariseClusters,
} from './graphModel';
import { edgeStyle, nodeRadius, ringWidth, roleStyle, shapePath } from './graphStyle';
import { formatAmount } from '../utils/formatAmount';
import { computeHullPath, curvedEdgePath, pointOnEdge } from './graphGeometry';

const HOP_MS = 1100;
const DOT_MS = 850;
const FOCUS_DELAY_MS = 400;
const REPLAY_DELAY_MS = 1400;
const MAX_FIT_SCALE = 1.4;
const FIT_PADDING = 70;
const DIMMED = 0.06;
const RING_MIN_SCORE = 0.25;
const LABELLED_ROLES = new Set(['SOURCE']);
const HALO = { stroke: 'var(--bg-surface)', width: 3 };

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

const withHalo = text => text
  .attr('paint-order', 'stroke')
  .attr('stroke', HALO.stroke)
  .attr('stroke-width', HALO.width)
  .attr('stroke-linejoin', 'round');

function buildData(nodes, edges, width, height) {
  const nodeById = new Map(nodes.map(n => [n.account_id, n]));
  const graphNodes = nodes.map(n => ({ ...n, id: n.account_id, x: width / 2, y: height / 2 }));
  const nodeMap = new Map(graphNodes.map(n => [n.id, n]));
  const graphLinks = edges
    .filter(e => nodeMap.has(e.from_account) && nodeMap.has(e.to_account))
    .map(e => ({
      source: e.from_account,
      target: e.to_account,
      amount: e.total_amount || 0,
      timestamps: e.timestamps || [],
      flagged: isFlaggedEdge(e, nodeById),
      key: edgeKey(e),
    }));
  const neighbours = new Map(graphNodes.map(n => [n.id, new Set()]));
  graphLinks.forEach(l => {
    neighbours.get(l.source).add(l.target);
    neighbours.get(l.target).add(l.source);
  });
  return { graphNodes, nodeMap, graphLinks, neighbours };
}

/** Start each cluster on its own grid cell so the force layout separates them quickly. */
function seedPositions(clusters, nodeMap, width, height) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(clusters.length)));
  const rows = Math.ceil(clusters.length / cols);
  clusters.forEach(({ ids }, ci) => {
    const cx = (width / (cols + 1)) * ((ci % cols) + 1);
    const cy = (height / (rows + 1)) * (Math.floor(ci / cols) + 1);
    const spread = Math.sqrt(ids.length) * 18;
    ids.forEach((id, ni) => {
      const angle = (2 * Math.PI * ni) / ids.length;
      const n = nodeMap.get(id);
      n.x = cx + spread * Math.cos(angle);
      n.y = cy + spread * Math.sin(angle);
    });
  });
}

function addMarkers(svg, uid) {
  const defs = svg.append('defs');
  [['flagged', true], ['other', false]].forEach(([name, flagged]) => {
    defs.append('marker')
      .attr('id', `${uid}-${name}`)
      .attr('viewBox', '0 -4 8 8')
      .attr('refX', 8).attr('refY', 0)
      .attr('markerWidth', 5).attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-4L8,0L0,4')
      .attr('fill', edgeStyle(flagged).stroke);
  });
}

function makeTooltip(container) {
  const tip = d3.select(container).append('div').attr('class', 'graph-tooltip').attr('aria-hidden', 'true');
  return {
    show(d) {
      tip.selectAll('*').remove();
      tip.append('strong').text(`${roleLabel(d.role)} account`);
      tip.append('span').text(d.account_id);
      const place = [d.bank, d.city].filter(Boolean).join(', ');
      tip.append('span').text(`Risk ${Math.round((d.smurf_score || 0) * 100)}%${place ? `, ${place}` : ''}`);
      tip.classed('is-visible', true);
    },
    move(event) {
      const rect = container.getBoundingClientRect();
      tip.style('left', `${event.clientX - rect.left + 14}px`).style('top', `${event.clientY - rect.top - 24}px`);
    },
    hide() { tip.classed('is-visible', false); },
    remove() { tip.remove(); },
  };
}

function drawNodes(layer, graphNodes, simulation) {
  const sel = layer.selectAll('g').data(graphNodes).enter().append('g')
    .attr('class', 'graph-node')
    .attr('tabindex', 0)
    .attr('role', 'button')
    .attr('aria-label', d => `${roleLabel(d.role)} account ${d.account_id}, risk ${Math.round((d.smurf_score || 0) * 100)}%`)
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      }));

  sel.append('path')
    .attr('d', d => shapePath(roleStyle(d.role).shape, nodeRadius(d)))
    .attr('fill', d => roleStyle(d.role).color)
    .attr('fill-opacity', d => roleStyle(d.role).fill)
    .attr('stroke', d => roleStyle(d.role).color)
    .attr('stroke-width', 1.5);

  // Risk ring: one ink colour, longer and heavier as risk rises
  sel.filter(d => (d.smurf_score || 0) >= RING_MIN_SCORE).append('circle')
    .attr('r', d => nodeRadius(d) + 5)
    .attr('fill', 'none')
    .attr('stroke', 'var(--text-primary)')
    .attr('stroke-opacity', 0.85)
    .attr('stroke-width', d => ringWidth(d.smurf_score))
    .attr('stroke-linecap', 'round')
    .attr('stroke-dasharray', d => {
      const circ = 2 * Math.PI * (nodeRadius(d) + 5);
      return `${circ * d.smurf_score} ${circ}`;
    })
    .attr('transform', 'rotate(-90)');

  withHalo(sel.filter(d => LABELLED_ROLES.has(d.role)).append('text')
    .text(d => `···${d.account_id.slice(-4)}`)
    .attr('text-anchor', 'middle')
    .attr('y', d => nodeRadius(d) + 19)
    .attr('fill', 'var(--text-secondary)')
    .attr('font-size', 10)
    .attr('font-family', 'var(--font-sans)'));

  return sel;
}

function drawClusters(g, clusters) {
  const shown = clusters.length > 1 ? clusters : [];
  const hulls = g.append('g').selectAll('path').data(shown).enter().append('path')
    .attr('fill', 'var(--text-primary)')
    .attr('fill-opacity', 0.025)
    .attr('stroke', 'var(--border-strong)')
    .attr('stroke-dasharray', '4 4');
  const labelled = shown.filter(c => c.flaggedCount > 0 && c.ids.length >= 3);
  const labels = withHalo(g.append('g').selectAll('text').data(labelled).enter().append('text')
    .attr('text-anchor', 'middle')
    .attr('fill', 'var(--text-muted)')
    .attr('font-size', 11)
    .attr('font-family', 'var(--font-sans)')
    .text(c => `Cluster ${c.index + 1}: ${c.ids.length} accounts, ${formatAmount(c.flaggedAmount)} flagged`));
  return { hulls, labels };
}

// No amount labels on edges: fan-outs from one hub stack them on top of each other.
// Amounts live in the list view and the node panel instead.
function drawEdges(g, graphLinks, uid) {
  const maxAmount = Math.max(1, ...graphLinks.map(l => l.amount));
  const width = d3.scaleSqrt().domain([0, maxAmount]).range([1, 3]);
  return g.append('g').selectAll('path').data(graphLinks).enter().append('path')
    .attr('fill', 'none')
    .attr('stroke', l => edgeStyle(l.flagged).stroke)
    .attr('stroke-dasharray', l => edgeStyle(l.flagged).dash)
    .attr('stroke-width', l => width(l.amount))
    .attr('marker-end', l => `url(#${uid}-${l.flagged ? 'flagged' : 'other'})`);
}

/**
 * Draws the money-flow graph into svgEl and returns controls for the React shell.
 * onSelect(node) fires on click/Enter; onHop({ current, total } | null) narrates the replay.
 */
export function drawGraph({ svgEl, container, nodes, edges, onSelect, onHop }) {
  const width = container.clientWidth || 800;
  const large = nodes.length > 30;
  const height = Math.max(360, Math.min(width * 0.6, large ? 640 : 520));
  const uid = `mc${Math.random().toString(36).slice(2, 8)}`;
  const timers = [];
  let replayTimers = [];
  let range = null;
  let replaying = false;

  const { graphNodes, nodeMap, graphLinks, neighbours } = buildData(nodes, edges, width, height);
  const rounds = hopRounds(nodes, edges);
  const clusters = summariseClusters(nodes, edges);
  const focus = clusters.length > 1 ? riskiestCluster(clusters) : null;
  const radius = new Map(graphNodes.map(n => [n.id, nodeRadius(n)]));
  seedPositions(clusters, nodeMap, width, height);

  const svg = d3.select(svgEl);
  svg.selectAll('*').remove();
  svg.attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);
  const g = svg.append('g');
  // One finger scrolls the page on phones; pinch and two-finger drag move the graph.
  const zoom = d3.zoom()
    .extent([[0, 0], [width, height]])
    .scaleExtent([0.2, 5])
    .filter(event => !event.button && (event.type !== 'touchstart' || event.touches.length > 1))
    .on('zoom', event => g.attr('transform', event.transform));
  svg.call(zoom).style('touch-action', 'pan-y');
  addMarkers(svg, uid);

  const simulation = d3.forceSimulation(graphNodes)
    .force('link', d3.forceLink(graphLinks).id(d => d.id).distance(large ? 55 : 90).strength(0.5))
    .force('charge', d3.forceManyBody().strength(large ? -180 : -320))
    .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
    .force('collision', d3.forceCollide().radius(d => radius.get(d.id) + (large ? 8 : 16)))
    .force('x', d3.forceX(width / 2).strength(0.02))
    .force('y', d3.forceY(height / 2).strength(0.02))
    .alphaDecay(0.022);

  const cluster = drawClusters(g, clusters);
  const links = drawEdges(g, graphLinks, uid);
  const nodeSel = drawNodes(g.append('g'), graphNodes, simulation);
  const flowLayer = g.append('g');
  const tooltip = makeTooltip(container);

  const inRange = l => !range || l.timestamps.some(t => {
    const ms = new Date(t).getTime();
    return ms >= range.start && ms <= range.end;
  });
  const baseOpacity = l => (inRange(l) ? edgeStyle(l.flagged).opacity : DIMMED);
  links.attr('stroke-opacity', baseOpacity);

  const highlight = id => {
    nodeSel.attr('opacity', n => (!id || n.id === id || neighbours.get(id).has(n.id) ? 1 : 0.2));
    if (replaying) return;
    links.attr('stroke-opacity', l => {
      if (!id) return baseOpacity(l);
      return l.source.id === id || l.target.id === id ? 1 : DIMMED;
    });
  };

  nodeSel
    .on('mouseenter', (event, d) => { highlight(d.id); tooltip.show(d); tooltip.move(event); })
    .on('mousemove', event => tooltip.move(event))
    .on('mouseleave', () => { highlight(null); tooltip.hide(); })
    .on('click', (event, d) => onSelect(d))
    .on('keydown', (event, d) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      onSelect(d);
    });

  const fitTo = (ids, duration = 750) => {
    const pts = ids.map(id => nodeMap.get(id)).filter(n => Number.isFinite(n?.x));
    if (!pts.length) return;
    const [x0, x1] = d3.extent(pts, n => n.x);
    const [y0, y1] = d3.extent(pts, n => n.y);
    const scale = Math.min(width / (x1 - x0 + FIT_PADDING * 2), height / (y1 - y0 + FIT_PADDING * 2), MAX_FIT_SCALE);
    const t = d3.zoomIdentity
      .translate(width / 2 - ((x0 + x1) / 2) * scale, height / 2 - ((y0 + y1) / 2) * scale)
      .scale(scale);
    if (!duration) svg.call(zoom.transform, t);
    else svg.transition().duration(duration).ease(d3.easeCubicOut).call(zoom.transform, t);
  };
  const showAll = duration => fitTo(graphNodes.map(n => n.id), duration);
  const focusRiskiest = () => (focus ? fitTo(focus.ids) : showAll());

  const sendDot = l => {
    flowLayer.append('circle')
      .attr('r', 4)
      .attr('fill', 'var(--accent)')
      .transition().duration(DOT_MS).ease(d3.easeCubicInOut)
      .attrTween('transform', () => t => {
        const [x, y] = pointOnEdge(l, radius, t);
        return `translate(${x},${y})`;
      })
      .remove();
  };

  const finishReplay = () => {
    replaying = false;
    links.transition().duration(400)
      .attr('stroke', l => edgeStyle(l.flagged).stroke)
      .attr('stroke-opacity', baseOpacity);
    onHop(null);
  };

  const replay = () => {
    replayTimers.forEach(clearTimeout);
    flowLayer.selectAll('*').interrupt().remove();
    const total = rounds.size ? Math.max(...rounds.values()) + 1 : 0;
    if (!total) return;
    const reduced = prefersReducedMotion();
    replaying = true;
    links.interrupt()
      .attr('stroke', l => edgeStyle(l.flagged).stroke)
      .attr('stroke-opacity', l => (rounds.has(l.key) ? 0.1 : baseOpacity(l)));
    replayTimers = d3.range(total).map(r => setTimeout(() => {
      onHop({ current: r + 1, total });
      const hop = links.filter(l => rounds.get(l.key) === r);
      hop.transition().duration(reduced ? 0 : 400).attr('stroke', 'var(--accent)').attr('stroke-opacity', 1);
      if (!reduced) hop.each(sendDot);
    }, r * HOP_MS));
    replayTimers.push(setTimeout(finishReplay, total * HOP_MS + 600));
  };

  const render = () => {
    cluster.hulls.attr('d', c => computeHullPath(c.ids, nodeMap, large ? 30 : 40));
    cluster.labels.attr('transform', c => {
      const members = c.ids.map(id => nodeMap.get(id));
      const top = d3.min(members, n => n.y);
      return `translate(${d3.mean(members, n => n.x)},${top - (large ? 42 : 52)})`;
    });
    links.attr('d', l => curvedEdgePath(l, radius));
    nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
  };

  // Settle the layout before first paint so the fit and the replay use final positions.
  simulation.stop();
  const settleTicks = Math.ceil(Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay()));
  for (let i = 0; i < settleTicks; i += 1) simulation.tick();
  simulation.on('tick', render);
  render();

  showAll(0);
  timers.push(setTimeout(focusRiskiest, FOCUS_DELAY_MS));
  if (!prefersReducedMotion()) timers.push(setTimeout(replay, REPLAY_DELAY_MS));

  return {
    zoomBy: factor => svg.transition().duration(250).call(zoom.scaleBy, factor),
    showAll,
    focusRiskiest,
    replay,
    setTimeRange(next) {
      range = next;
      if (!replaying) links.attr('stroke-opacity', baseOpacity);
    },
    destroy() {
      timers.forEach(clearTimeout);
      replayTimers.forEach(clearTimeout);
      simulation.stop();
      svg.selectAll('*').interrupt();
      svg.on('.zoom', null);
      tooltip.remove();
    },
  };
}
