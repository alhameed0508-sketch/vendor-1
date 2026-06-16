import React, { useEffect, useRef, useMemo } from 'react';
import * as d3 from 'd3';

/* ═══════════════════════════════════════════════════════════════════
   NetworkGraph — Aesthetic, Explainable Mule Network Visualization
   Features: cluster hulls, risk-gradient nodes, curved edges,
             cluster summaries, insights panel, hub annotations,
             SYNTHETIC FALLBACK when no props provided.
   ═══════════════════════════════════════════════════════════════════ */

/* ── Synthetic demo data (mirrors DEMO_ALERTS in alert_service.py) ── */

export const DEMO_GRAPH = {
  nodes: [
    // Cluster 1 — Chennai smurfing ring (ALT-0001)
    { account_id: 'AC001', role: 'SOURCE',     smurf_score: 0.93, betweenness: 0.62, pagerank: 0.18, bank: 'IOB',  city: 'Chennai',    account_age_days: 3,   kyc_status: 'PARTIAL'  },
    { account_id: 'AC002', role: 'AGGREGATOR', smurf_score: 0.88, betweenness: 0.78, pagerank: 0.21, bank: 'IOB',  city: 'Chennai',    account_age_days: 5,   kyc_status: 'PARTIAL'  },
    { account_id: 'AC003', role: 'MULE',       smurf_score: 0.76, betweenness: 0.31, pagerank: 0.09, bank: 'SBI',  city: 'Coimbatore', account_age_days: 12,  kyc_status: 'PENDING'  },
    { account_id: 'AC004', role: 'MULE',       smurf_score: 0.71, betweenness: 0.22, pagerank: 0.08, bank: 'SBI',  city: 'Madurai',    account_age_days: 8,   kyc_status: 'PENDING'  },
    { account_id: 'AC005', role: 'MULE',       smurf_score: 0.68, betweenness: 0.18, pagerank: 0.07, bank: 'BOI',  city: 'Trichy',     account_age_days: 6,   kyc_status: 'PENDING'  },
    { account_id: 'AC006', role: 'LEGITIMATE', smurf_score: 0.12, betweenness: 0.05, pagerank: 0.04, bank: 'IOB',  city: 'Chennai',    account_age_days: 420, kyc_status: 'COMPLETE' },
    // Cluster 2 — Bangalore consolidation ring (ALT-0002)
    { account_id: 'AC010', role: 'SOURCE',     smurf_score: 0.77, betweenness: 0.55, pagerank: 0.14, bank: 'IOB',  city: 'Bangalore',  account_age_days: 14,  kyc_status: 'PARTIAL'  },
    { account_id: 'AC011', role: 'MULE',       smurf_score: 0.65, betweenness: 0.33, pagerank: 0.10, bank: 'HDFC', city: 'Bangalore',  account_age_days: 21,  kyc_status: 'PENDING'  },
    { account_id: 'AC012', role: 'MULE',       smurf_score: 0.59, betweenness: 0.28, pagerank: 0.09, bank: 'HDFC', city: 'Mysore',     account_age_days: 18,  kyc_status: 'PENDING'  },
    { account_id: 'AC013', role: 'LEGITIMATE', smurf_score: 0.08, betweenness: 0.04, pagerank: 0.03, bank: 'IOB',  city: 'Bangalore',  account_age_days: 730, kyc_status: 'COMPLETE' },
    // Cluster 3 — Mumbai device-overlap pair (ALT-0003)
    { account_id: 'AC020', role: 'SOURCE',     smurf_score: 0.54, betweenness: 0.40, pagerank: 0.11, bank: 'IOB',  city: 'Mumbai',     account_age_days: 30,  kyc_status: 'COMPLETE' },
    { account_id: 'AC021', role: 'MULE',       smurf_score: 0.48, betweenness: 0.22, pagerank: 0.07, bank: 'PNB',  city: 'Pune',       account_age_days: 45,  kyc_status: 'PARTIAL'  },
    { account_id: 'AC022', role: 'MULE',       smurf_score: 0.44, betweenness: 0.18, pagerank: 0.06, bank: 'PNB',  city: 'Nagpur',     account_age_days: 60,  kyc_status: 'PARTIAL'  },
  ],
  edges: [
    // Cluster 1 edges
    { from_account: 'AC001', to_account: 'AC002', total_amount: 750000, txn_count: 8,  pattern: 'SMURFING',      timestamps: ['2025-05-01T02:14:00', '2025-05-01T02:38:00'] },
    { from_account: 'AC001', to_account: 'AC003', total_amount: 450000, txn_count: 5,  pattern: 'SMURFING',      timestamps: ['2025-05-01T03:10:00'] },
    { from_account: 'AC002', to_account: 'AC004', total_amount: 380000, txn_count: 6,  pattern: 'CONSOLIDATION', timestamps: ['2025-05-02T14:22:00'] },
    { from_account: 'AC002', to_account: 'AC005', total_amount: 270000, txn_count: 5,  pattern: 'SMURFING',      timestamps: ['2025-05-02T15:00:00'] },
    { from_account: 'AC003', to_account: 'AC006', total_amount: 120000, txn_count: 3,  pattern: 'NORMAL',        timestamps: ['2025-05-03T09:00:00'] },
    { from_account: 'AC004', to_account: 'AC006', total_amount:  80000, txn_count: 2,  pattern: 'NORMAL',        timestamps: ['2025-05-03T10:00:00'] },
    // Cluster 2 edges
    { from_account: 'AC010', to_account: 'AC011', total_amount: 320000, txn_count: 6,  pattern: 'SMURFING',      timestamps: ['2025-05-04T11:00:00'] },
    { from_account: 'AC010', to_account: 'AC012', total_amount: 300000, txn_count: 5,  pattern: 'SMURFING',      timestamps: ['2025-05-04T11:45:00'] },
    { from_account: 'AC011', to_account: 'AC013', total_amount: 180000, txn_count: 3,  pattern: 'NORMAL',        timestamps: ['2025-05-05T09:00:00'] },
    // Cluster 3 edges
    { from_account: 'AC020', to_account: 'AC021', total_amount: 120000, txn_count: 4,  pattern: 'CONSOLIDATION', timestamps: ['2025-05-06T16:00:00'] },
    { from_account: 'AC020', to_account: 'AC022', total_amount:  90000, txn_count: 3,  pattern: 'CONSOLIDATION', timestamps: ['2025-05-06T16:30:00'] },
  ],
};

/* ── Constants ──────────────────────────────────────────────────── */

const ROLE_COLORS = {
  SOURCE:      '#FF5C7A',
  AGGREGATOR:  '#FFB020',
  MULE:        '#FFB020',
  LEGITIMATE:  '#38BDF8',
  UNKNOWN:     '#7D8CA3',
};

const ROLE_LABELS = {
  SOURCE: 'SRC', AGGREGATOR: 'AGG', MULE: 'MUL',
  LEGITIMATE: 'LEG', UNKNOWN: '?',
};

const BASE_RADIUS = {
  SOURCE: 18, AGGREGATOR: 16, MULE: 13,
  LEGITIMATE: 11, UNKNOWN: 10,
};

const CLUSTER_PALETTE = [
  { fill: 'rgba(62,231,255,0.045)',  stroke: 'rgba(62,231,255,0.14)',  text: 'rgba(62,231,255,0.7)' },
  { fill: 'rgba(255,92,122,0.045)',  stroke: 'rgba(255,92,122,0.14)',  text: 'rgba(255,92,122,0.7)' },
  { fill: 'rgba(255,176,32,0.045)',  stroke: 'rgba(255,176,32,0.14)',  text: 'rgba(255,176,32,0.7)' },
  { fill: 'rgba(16,185,129,0.045)',  stroke: 'rgba(16,185,129,0.14)',  text: 'rgba(16,185,129,0.7)' },
  { fill: 'rgba(168,85,247,0.045)',  stroke: 'rgba(168,85,247,0.14)',  text: 'rgba(168,85,247,0.7)' },
  { fill: 'rgba(251,146,60,0.045)',  stroke: 'rgba(251,146,60,0.14)',  text: 'rgba(251,146,60,0.7)' },
];

const PATTERN_COLORS = {
  SMURFING:      { edge: '#FF5C7A', particle: '#FF5C7A', opacity: 0.5 },
  CONSOLIDATION: { edge: '#FFB020', particle: '#FFB020', opacity: 0.4 },
  NORMAL:        { edge: '#3A4F70', particle: '#3EE7FF', opacity: 0.2 },
};

/* ── Helpers ─────────────────────────────────────────────────────── */

function riskColor(score) {
  if (score < 0.25) return '#10B981';
  if (score < 0.45) return '#FBBF24';
  if (score < 0.65) return '#F97316';
  return '#EF4444';
}

function formatAmount(amount) {
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
  if (amount >= 100000)   return `₹${(amount / 100000).toFixed(1)}L`;
  if (amount >= 1000)     return `₹${(amount / 1000).toFixed(0)}K`;
  return `₹${Math.round(amount)}`;
}

function nodeRadius(node) {
  const base = BASE_RADIUS[node.role] || 10;
  const riskBoost = (node.smurf_score || 0) * 5;
  return base + riskBoost;
}

/** BFS connected-component cluster detection */
function detectClusters(graphNodes, graphLinks) {
  const adj = new Map();
  graphNodes.forEach(n => adj.set(n.id, []));
  graphLinks.forEach(l => {
    const s = typeof l.source === 'object' ? l.source.id : l.source;
    const t = typeof l.target === 'object' ? l.target.id : l.target;
    if (adj.has(s)) adj.get(s).push(t);
    if (adj.has(t)) adj.get(t).push(s);
  });
  const visited = new Set();
  const clusters = [];
  for (const node of graphNodes) {
    if (visited.has(node.id)) continue;
    const cluster = [];
    const queue = [node.id];
    while (queue.length) {
      const id = queue.shift();
      if (visited.has(id)) continue;
      visited.add(id);
      cluster.push(id);
      for (const nb of (adj.get(id) || [])) {
        if (!visited.has(nb)) queue.push(nb);
      }
    }
    if (cluster.length > 0) clusters.push(cluster);
  }
  clusters.sort((a, b) => b.length - a.length);
  return clusters;
}

/** Expand convex hull outward from centroid */
function expandHull(hull, padding) {
  const cx = d3.mean(hull, p => p[0]);
  const cy = d3.mean(hull, p => p[1]);
  return hull.map(([x, y]) => {
    const dx = x - cx, dy = y - cy;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    return [cx + dx * (dist + padding) / dist, cy + dy * (dist + padding) / dist];
  });
}

/** Compute smooth hull path for a set of node IDs */
function computeHullPath(nodeIds, nodeMap, padding) {
  const pts = nodeIds.map(id => {
    const n = nodeMap.get(id);
    return n && isFinite(n.x) && isFinite(n.y) ? [n.x, n.y] : null;
  }).filter(Boolean);

  if (pts.length === 0) return '';

  if (pts.length === 1) {
    const [cx, cy] = pts[0];
    const r = padding;
    return `M${cx - r},${cy}A${r},${r} 0 1,0 ${cx + r},${cy}A${r},${r} 0 1,0 ${cx - r},${cy}Z`;
  }

  let hullPts;
  if (pts.length === 2) {
    const [p1, p2] = pts;
    const dx = p2[0] - p1[0], dy = p2[1] - p1[1];
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const nx = -dy / dist, ny = dx / dist;
    const ex = dx / dist * padding * 0.6, ey = dy / dist * padding * 0.6;
    hullPts = [
      [p1[0] - ex + nx * padding, p1[1] - ey + ny * padding],
      [p2[0] + ex + nx * padding, p2[1] + ey + ny * padding],
      [p2[0] + ex - nx * padding, p2[1] + ey - ny * padding],
      [p1[0] - ex - nx * padding, p1[1] - ey - ny * padding],
    ];
  } else {
    const hull = d3.polygonHull(pts);
    if (!hull) return '';
    hullPts = expandHull(hull, padding);
  }

  return d3.line().x(d => d[0]).y(d => d[1])
    .curve(d3.curveCatmullRomClosed.alpha(0.7))(hullPts);
}

/** Curved edge path (quadratic bezier) shortened to stop at target edge */
function curvedEdgePath(d, nodeRadiusMap) {
  const sx = d.source.x, sy = d.source.y;
  const tx = d.target.x, ty = d.target.y;
  const dx = tx - sx, dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const tgtR = nodeRadiusMap.get(d.target.id) || 12;
  const shortenRatio = (tgtR + 6) / dist;
  const endX = tx - dx * shortenRatio;
  const endY = ty - dy * shortenRatio;
  const curvature = 0.12;
  const mx = (sx + endX) / 2 + dy * curvature;
  const my = (sy + endY) / 2 - dx * curvature;
  return `M${sx},${sy}Q${mx},${my},${endX},${endY}`;
}

/* ── Component ───────────────────────────────────────────────────── */

export default function NetworkGraph({
  nodes: propNodes,
  edges: propEdges,
  timeRange = null,
  useDemoData = false,
}) {
  // Fall back to DEMO_GRAPH when no data is provided
  const rawNodes = (!propNodes || propNodes.length === 0 || useDemoData) ? DEMO_GRAPH.nodes : propNodes;
  const rawEdges = (!propEdges || propEdges.length === 0 || useDemoData) ? DEMO_GRAPH.edges : propEdges;

  // Normalise field names (backend may send betweenness_centrality, demo uses betweenness)
  const nodes = rawNodes.map(n => ({
    ...n,
    betweenness: n.betweenness ?? n.betweenness_centrality ?? 0,
  }));
  const edges = rawEdges.map(e => ({
    ...e,
    from_account: e.from_account ?? e.source,
    to_account:   e.to_account   ?? e.target,
  }));

  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const zoomRef = useRef(null);
  const linkSelRef = useRef(null);

  /* ── Compute graph-level insights for the overlay panel ── */
  const insights = useMemo(() => {
    if (!nodes.length) return null;
    const suspiciousEdges = edges.filter(e => e.pattern === 'SMURFING' || e.pattern === 'CONSOLIDATION');
    const totalSuspicious = suspiciousEdges.reduce((s, e) => s + (e.total_amount || 0), 0);
    const avgRisk = d3.mean(nodes, n => n.smurf_score || 0) || 0;
    const hubCount = nodes.filter(n => (n.betweenness || 0) > 0.04).length;
    const patternCounts = {};
    edges.forEach(e => { patternCounts[e.pattern] = (patternCounts[e.pattern] || 0) + 1; });
    const dominant = Object.entries(patternCounts).sort((a, b) => b[1] - a[1])[0];
    // Compute cluster count using same BFS as the D3 render
    const tempNodes = nodes.map(n => ({ id: n.account_id }));
    const tempLinks = edges.map(e => ({ source: e.from_account, target: e.to_account }))
      .filter(e => tempNodes.some(n => n.id === e.source) && tempNodes.some(n => n.id === e.target));
    const clusterCount = detectClusters(tempNodes, tempLinks).length;
    return {
      clusterCount,
      totalSuspicious,
      avgRisk,
      hubCount,
      dominantPattern: dominant ? dominant[0] : 'NORMAL',
      dominantPct: dominant ? Math.round((dominant[1] / edges.length) * 100) : 0,
    };
  }, [nodes, edges]);

  /* ── Main D3 rendering ── */
  useEffect(() => {
    if (!nodes.length) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const maxH = nodes.length > 30 ? 680 : 500;
    const height = Math.max(360, Math.min(container.clientWidth * 0.55, maxH));

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g');
    const zoom = d3.zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);
    zoomRef.current = { zoom, svg, g, fitToView: null };

    /* ── Defs: markers, filters ── */
    const defs = svg.append('defs');

    // Pattern-specific arrowheads
    ['SMURFING', 'CONSOLIDATION', 'NORMAL'].forEach(p => {
      defs.append('marker')
        .attr('id', `arrow-${p}`)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 8).attr('refY', 0)
        .attr('markerWidth', 5).attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', PATTERN_COLORS[p].edge)
        .attr('opacity', 0.7);
    });

    // Glow filter for high-risk nodes
    const glow = defs.append('filter')
      .attr('id', 'nodeGlow')
      .attr('x', '-50%').attr('y', '-50%')
      .attr('width', '200%').attr('height', '200%');
    glow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur');
    const glowMerge = glow.append('feMerge');
    glowMerge.append('feMergeNode').attr('in', 'blur');
    glowMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Subtle hull blur
    const hullBlur = defs.append('filter')
      .attr('id', 'hullBlur')
      .attr('x', '-10%').attr('y', '-10%')
      .attr('width', '120%').attr('height', '120%');
    hullBlur.append('feGaussianBlur').attr('stdDeviation', '8');

    /* ── Build graph data ── */
    const nodeMap = new Map();
    const graphNodes = nodes.map(n => {
      const gn = { ...n, id: n.account_id, x: width / 2, y: height / 2 };
      nodeMap.set(gn.id, gn);
      return gn;
    });

    const nodeRadiusMap = new Map(graphNodes.map(n => [n.id, nodeRadius(n)]));

    const graphLinks = edges.map(e => ({
      source: e.from_account, target: e.to_account,
      amount: e.total_amount, count: e.txn_count,
      pattern: e.pattern, timestamps: e.timestamps || [],
    })).filter(e => nodeMap.has(e.source) && nodeMap.has(e.target));

    /* ── Detect clusters & compute stats ── */
    const clusters = detectClusters(graphNodes, graphLinks);
    const isLargeGraph = nodes.length > 30;

    const clusterStats = clusters.map((ids, ci) => {
      const idSet = new Set(ids);
      const cEdges = graphLinks.filter(l => {
        const s = typeof l.source === 'object' ? l.source.id : l.source;
        const t = typeof l.target === 'object' ? l.target.id : l.target;
        return idSet.has(s) && idSet.has(t);
      });
      const totalAmt = cEdges.reduce((s, e) => s + (e.amount || 0), 0);
      const pCounts = {};
      cEdges.forEach(e => { pCounts[e.pattern] = (pCounts[e.pattern] || 0) + 1; });
      const dom = Object.entries(pCounts).sort((a, b) => b[1] - a[1])[0];
      const cNodes = ids.map(id => nodeMap.get(id)).filter(Boolean);
      const maxRisk = Math.max(...cNodes.map(n => n.smurf_score || 0));
      const hub = cNodes.reduce((best, n) =>
        (n.betweenness || 0) > (best.betweenness || 0) ? n : best, cNodes[0]);
      return { index: ci, ids, nodeCount: ids.length, edgeCount: cEdges.length,
        totalAmount: totalAmt, dominantPattern: dom ? dom[0] : 'NORMAL',
        maxRisk, hub };
    });

    /* ── Initial positioning: cluster grid ── */
    const cols = Math.max(1, Math.ceil(Math.sqrt(clusters.length)));
    const rows = Math.ceil(clusters.length / cols);
    const cellW = width / (cols + 1);
    const cellH = height / (rows + 1);

    clusters.forEach((ids, ci) => {
      const col = ci % cols;
      const row = Math.floor(ci / cols);
      const cx = cellW * (col + 1);
      const cy = cellH * (row + 1);
      const spread = Math.sqrt(ids.length) * 18;
      ids.forEach((id, ni) => {
        const angle = (2 * Math.PI * ni) / ids.length;
        const n = nodeMap.get(id);
        if (n) { n.x = cx + spread * Math.cos(angle); n.y = cy + spread * Math.sin(angle); }
      });
    });

    /* ── Force simulation ── */
    const simulation = d3.forceSimulation(graphNodes)
      .force('link', d3.forceLink(graphLinks).id(d => d.id)
        .distance(isLargeGraph ? 55 : 90).strength(0.5))
      .force('charge', d3.forceManyBody()
        .strength(isLargeGraph ? -180 : -320))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
      .force('collision', d3.forceCollide()
        .radius(d => nodeRadius(d) + (isLargeGraph ? 6 : 14)))
      .force('x', d3.forceX(width / 2).strength(0.02))
      .force('y', d3.forceY(height / 2).strength(0.02))
      .alpha(1)
      .alphaDecay(0.022);

    /* ── Auto-fit after stabilisation ── */
    let hasFitted = false;
    const fitToView = () => {
      if (hasFitted) return;
      hasFitted = true;
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      graphNodes.forEach(d => {
        if (d.x < x0) x0 = d.x; if (d.x > x1) x1 = d.x;
        if (d.y < y0) y0 = d.y; if (d.y > y1) y1 = d.y;
      });
      const pad = 90;
      const bw = (x1 - x0) + pad * 2;
      const bh = (y1 - y0) + pad * 2;
      if (bw <= 0 || bh <= 0) return;
      const scale = Math.min(width / bw, height / bh, 2.0);
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      const tx = width / 2 - cx * scale, ty = height / 2 - cy * scale;
      svg.transition().duration(1000).ease(d3.easeCubicOut)
        .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    };
    simulation.on('end', fitToView);
    const fitTimer = setTimeout(fitToView, 3500);
    if (zoomRef.current) zoomRef.current.fitToView = () => { hasFitted = false; fitToView(); };

    /* ── Layer 1: Cluster hulls ── */
    const hullGroup = g.append('g').attr('class', 'cluster-hulls');

    // Soft glow layer behind hulls
    const hullGlowPaths = hullGroup.selectAll('.hull-glow')
      .data(clusterStats).enter().append('path')
      .attr('class', 'hull-glow')
      .attr('fill', (d) => CLUSTER_PALETTE[d.index % CLUSTER_PALETTE.length].fill)
      .attr('stroke', 'none')
      .attr('filter', 'url(#hullBlur)')
      .attr('opacity', 0);

    // Main hull outlines
    const hullPaths = hullGroup.selectAll('.hull-outline')
      .data(clusterStats).enter().append('path')
      .attr('class', 'hull-outline')
      .attr('fill', (d) => CLUSTER_PALETTE[d.index % CLUSTER_PALETTE.length].fill)
      .attr('stroke', (d) => CLUSTER_PALETTE[d.index % CLUSTER_PALETTE.length].stroke)
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '6,4')
      .attr('opacity', 0);

    // Animate hulls in
    hullGlowPaths.transition().delay(600).duration(800).attr('opacity', 0.6);
    hullPaths.transition().delay(600).duration(800).attr('opacity', 1);

    /* ── Layer 2: Cluster labels ── */
    const clusterLabelGroup = g.append('g').attr('class', 'cluster-labels');
    const clusterLabelEls = clusterLabelGroup.selectAll('.cl-label')
      .data(clusterStats).enter().append('g')
      .attr('class', 'cl-label')
      .attr('opacity', 0);

    // Background pill
    clusterLabelEls.append('rect')
      .attr('rx', 4).attr('ry', 4)
      .attr('fill', 'var(--bg-card)')
      .attr('stroke', d => CLUSTER_PALETTE[d.index % CLUSTER_PALETTE.length].stroke)
      .attr('stroke-width', 0.5);

    // Label text
    clusterLabelEls.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', 9)
      .attr('font-weight', 600)
      .attr('letter-spacing', '0.5px')
      .attr('fill', d => CLUSTER_PALETTE[d.index % CLUSTER_PALETTE.length].text)
      .text(d => {
        const patLabel = d.dominantPattern === 'NORMAL' ? '' : ` · ${d.dominantPattern}`;
        return `Cluster ${d.index + 1}  ·  ${d.nodeCount} accts  ·  ${formatAmount(d.totalAmount)}${patLabel}`;
      });

    // Animate labels in
    clusterLabelEls.transition().delay(1200).duration(600).attr('opacity', 1);

    // Measure and size background rects after text renders
    setTimeout(() => {
      clusterLabelEls.each(function() {
        const textEl = d3.select(this).select('text');
        const bbox = textEl.node()?.getBBox();
        if (!bbox) return;
        d3.select(this).select('rect')
          .attr('x', bbox.x - 8).attr('y', bbox.y - 4)
          .attr('width', bbox.width + 16).attr('height', bbox.height + 8);
      });
    }, 50);

    /* ── Layer 3: Edges (curved paths) ── */
    const edgeGroup = g.append('g').attr('class', 'edges');
    const maxAmount = Math.max(...graphLinks.map(l => l.amount), 1);
    const edgeWidthScale = d3.scaleLinear().domain([0, maxAmount]).range([1, 3.5]);

    const linkPaths = edgeGroup.selectAll('path')
      .data(graphLinks).enter().append('path')
      .attr('fill', 'none')
      .attr('stroke', d => (PATTERN_COLORS[d.pattern] || PATTERN_COLORS.NORMAL).edge)
      .attr('stroke-opacity', d => (PATTERN_COLORS[d.pattern] || PATTERN_COLORS.NORMAL).opacity)
      .attr('stroke-width', d => edgeWidthScale(d.amount))
      .attr('marker-end', d => `url(#arrow-${d.pattern || 'NORMAL'})`)
      .attr('stroke-dasharray', '1200')
      .attr('stroke-dashoffset', '1200');

    linkSelRef.current = linkPaths;

    // Edge draw-in animation
    const edgeStagger = isLargeGraph ? Math.min(10, 1400 / graphLinks.length) : 60;
    linkPaths.transition()
      .delay((d, i) => 300 + i * edgeStagger)
      .duration(isLargeGraph ? 300 : 600)
      .ease(d3.easeCubicOut)
      .attr('stroke-dashoffset', '0');

    // Edge amount labels — only for notable amounts on smaller graphs
    const amountLabelData = isLargeGraph
      ? graphLinks.filter(l => l.amount > maxAmount * 0.4).slice(0, 15)
      : graphLinks.filter(l => l.amount > 10000);
    const edgeLabels = edgeGroup.selectAll('.edge-label')
      .data(amountLabelData).enter().append('text')
      .attr('class', 'edge-label')
      .attr('fill', 'var(--text-muted)')
      .attr('font-size', 8)
      .attr('font-family', 'var(--font-mono)')
      .attr('text-anchor', 'middle')
      .attr('opacity', 0);

    edgeLabels.transition().delay(1600).duration(400).attr('opacity', 0.7);

    /* ── Layer 4: Nodes ── */
    const nodeGroup = g.append('g').attr('class', 'nodes').selectAll('g')
      .data(graphNodes).enter().append('g')
      .style('cursor', 'pointer')
      .attr('opacity', 0)
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    // Stagger node appearance
    const nodeStagger = isLargeGraph ? Math.min(14, 1400 / graphNodes.length) : 80;
    nodeGroup.transition()
      .delay((d, i) => 120 + i * nodeStagger)
      .duration(isLargeGraph ? 300 : 500)
      .ease(d3.easeBackOut.overshoot(1.2))
      .attr('opacity', 1)
      .attrTween('transform', function(d) {
        const s = d3.interpolate(0.2, 1);
        return t => `translate(${d.x},${d.y}) scale(${s(t)})`;
      });

    // (a) Pulsing glow ring for high-risk nodes
    nodeGroup.filter(d => (d.smurf_score || 0) > 0.5)
      .append('circle')
      .attr('r', d => nodeRadius(d) + 8)
      .attr('fill', 'none')
      .attr('stroke', d => riskColor(d.smurf_score))
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '4,3')
      .attr('opacity', 0.4)
      .attr('filter', 'url(#nodeGlow)');

    // (b) Risk-colored outer ring — green/yellow/orange/red by smurf_score
    nodeGroup.append('circle')
      .attr('r', d => nodeRadius(d))
      .attr('fill', 'none')
      .attr('stroke', d => riskColor(d.smurf_score || 0))
      .attr('stroke-width', 2.5)
      .attr('opacity', 0.8);

    // (c) Role-colored inner fill
    nodeGroup.append('circle')
      .attr('r', d => nodeRadius(d) - 2)
      .attr('fill', d => ROLE_COLORS[d.role] + '18')
      .attr('stroke', d => ROLE_COLORS[d.role])
      .attr('stroke-width', 1);

    // (d) Score arc — partial ring showing smurf score %
    nodeGroup.append('circle')
      .attr('r', d => nodeRadius(d))
      .attr('fill', 'none')
      .attr('stroke', d => riskColor(d.smurf_score || 0))
      .attr('stroke-width', 2.5)
      .attr('stroke-dasharray', d => {
        const circ = 2 * Math.PI * nodeRadius(d);
        return `${circ * (d.smurf_score || 0)} ${circ}`;
      })
      .attr('stroke-linecap', 'round')
      .attr('opacity', 0.9);

    // (e) Role abbreviation
    nodeGroup.append('text')
      .text(d => ROLE_LABELS[d.role] || '?')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('fill', d => ROLE_COLORS[d.role])
      .attr('font-size', d => nodeRadius(d) > 15 ? 9 : 7)
      .attr('font-family', 'var(--font-mono)')
      .attr('font-weight', 600);

    // (f) Account ID label
    nodeGroup.append('text')
      .text(d => '···' + d.account_id.slice(-4))
      .attr('text-anchor', 'middle')
      .attr('dy', d => nodeRadius(d) + 12)
      .attr('fill', 'var(--text-muted)')
      .attr('font-size', isLargeGraph ? 7 : 9)
      .attr('font-family', 'var(--font-mono)');

    // (g) Risk % badge for high-risk nodes
    nodeGroup.filter(d => (d.smurf_score || 0) > 0.5)
      .append('text')
      .text(d => `${Math.round(d.smurf_score * 100)}%`)
      .attr('text-anchor', 'middle')
      .attr('dy', d => nodeRadius(d) + 22)
      .attr('fill', d => riskColor(d.smurf_score))
      .attr('font-size', 7)
      .attr('font-family', 'var(--font-mono)')
      .attr('font-weight', 700);

    /* ── Layer 5: Hub node annotations ── */
    const hubAnnotGroup = g.append('g').attr('class', 'hub-annotations');
    const hubNodes = clusterStats
      .filter(cs => cs.hub && (cs.hub.betweenness || 0) > 0.02 && cs.nodeCount > 2)
      .map(cs => cs.hub);

    const hubAnnotEls = hubAnnotGroup.selectAll('g')
      .data(hubNodes).enter().append('g')
      .attr('opacity', 0);

    hubAnnotEls.append('line')
      .attr('stroke', 'rgba(62,231,255,0.3)')
      .attr('stroke-width', 0.5)
      .attr('stroke-dasharray', '3,2');

    hubAnnotEls.append('rect')
      .attr('rx', 3).attr('ry', 3)
      .attr('fill', 'var(--bg-card)')
      .attr('stroke', 'rgba(62,231,255,0.2)')
      .attr('stroke-width', 0.5);

    hubAnnotEls.append('text')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', 8)
      .attr('fill', 'rgba(62,231,255,0.8)')
      .attr('font-weight', 600)
      .text(d => `HUB ···${d.account_id.slice(-4)}`);

    hubAnnotEls.transition().delay(2000).duration(600).attr('opacity', 1);

    /* ── Layer 6: Particle flow (simplified) ── */
    const flowGroup = g.append('g').attr('class', 'flow-particles');
    const activeTimers = [];

    const particleLinks = isLargeGraph
      ? graphLinks.filter(l => l.pattern === 'SMURFING' || l.pattern === 'CONSOLIDATION').slice(0, 20)
      : graphLinks.filter(l => l.pattern !== 'NORMAL').slice(0, 40);

    const particleR = d3.scaleLinear().domain([0, maxAmount]).range([1.2, 3]).clamp(true);
    const particleDur = d3.scaleLinear().domain([0, maxAmount]).range([2600, 1600]).clamp(true);

    const resolveNode = (ref) => typeof ref === 'object' ? ref : graphNodes.find(n => n.id === ref);

    particleLinks.forEach((ld, i) => {
      const color = (PATTERN_COLORS[ld.pattern] || PATTERN_COLORS.NORMAL).particle;
      const r = particleR(ld.amount);
      const dur = particleDur(ld.amount);

      const dot = flowGroup.append('circle')
        .attr('r', r).attr('fill', color).attr('opacity', 0);

      const animate = () => {
        const src = resolveNode(ld.source);
        const tgt = resolveNode(ld.target);
        if (!src || !tgt) return;
        dot.attr('cx', src.x).attr('cy', src.y).attr('opacity', 0.7);
        dot.transition().duration(dur).ease(d3.easeLinear)
          .attrTween('cx', () => t => src.x + (tgt.x - src.x) * t)
          .attrTween('cy', () => t => src.y + (tgt.y - src.y) * t)
          .attrTween('opacity', () => t => {
            if (t < 0.1) return t / 0.1 * 0.7;
            if (t > 0.85) return (1 - t) / 0.15 * 0.7;
            return 0.7;
          })
          .on('end', animate);
      };

      const delay = isLargeGraph ? 1200 + i * 60 : 1800 + i * 150;
      activeTimers.push(setTimeout(animate, delay));
    });

    /* ── Hover interactions ── */
    const tooltip = d3.select(container).append('div')
      .style('position', 'absolute')
      .style('background', 'var(--bg-card)')
      .style('border', '1px solid var(--border)')
      .style('border-radius', '8px')
      .style('padding', '12px 16px')
      .style('font-family', 'var(--font-mono)')
      .style('font-size', '11px')
      .style('color', 'var(--text-primary)')
      .style('pointer-events', 'none')
      .style('opacity', 0)
      .style('z-index', 10)
      .style('max-width', '240px')
      .style('backdrop-filter', 'blur(12px)')
      .style('box-shadow', '0 8px 32px rgba(0,0,0,0.3)');

    nodeGroup
      .on('mouseover', (event, d) => {
        linkPaths.attr('stroke-opacity', 0.06);
        linkPaths.filter(l => l.source.id === d.id || l.target.id === d.id)
          .attr('stroke-opacity', 0.8)
          .attr('stroke-width', l => edgeWidthScale(l.amount) + 1.5);
        nodeGroup.attr('opacity', n => {
          if (n.id === d.id) return 1;
          return graphLinks.some(l =>
            (l.source.id === d.id && l.target.id === n.id) ||
            (l.target.id === d.id && l.source.id === n.id)
          ) ? 1 : 0.2;
        });
        const rc = riskColor(d.smurf_score || 0);
        tooltip.transition().duration(120).style('opacity', 1);
        tooltip.html(`
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <div style="width:8px;height:8px;border-radius:50%;background:${ROLE_COLORS[d.role]}"></div>
            <span style="color:${ROLE_COLORS[d.role]};font-weight:700;font-size:12px">${d.role}</span>
          </div>
          <div style="color:var(--text-muted);font-size:10px;margin-bottom:8px">${d.account_id}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:10px">
            <span style="color:var(--text-faint)">Bank</span><span>${d.bank || '—'}</span>
            <span style="color:var(--text-faint)">City</span><span>${d.city || '—'}</span>
            <span style="color:var(--text-faint)">Age</span><span>${d.account_age_days || 0}d</span>
            <span style="color:var(--text-faint)">KYC</span><span>${d.kyc_status || '—'}</span>
          </div>
          <div style="border-top:1px solid var(--border-subtle);margin:8px 0;padding-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:10px">
            <span style="color:var(--text-faint)">Risk</span>
            <span style="color:${rc};font-weight:700">${Math.round((d.smurf_score || 0) * 100)}%</span>
            ${(d.betweenness || 0) > 0.01 ? `<span style="color:var(--text-faint)">Betweenness</span><span style="color:var(--accent-cyan)">${(d.betweenness * 100).toFixed(1)}%</span>` : ''}
            ${(d.pagerank || 0) > 0.01 ? `<span style="color:var(--text-faint)">PageRank</span><span style="color:var(--accent-cyan)">${(d.pagerank * 100).toFixed(1)}%</span>` : ''}
          </div>
        `);
      })
      .on('mousemove', (event) => {
        const rect = container.getBoundingClientRect();
        tooltip
          .style('left', (event.clientX - rect.left + 14) + 'px')
          .style('top', (event.clientY - rect.top - 24) + 'px');
      })
      .on('mouseout', () => {
        linkPaths
          .attr('stroke-opacity', d => (PATTERN_COLORS[d.pattern] || PATTERN_COLORS.NORMAL).opacity)
          .attr('stroke-width', d => edgeWidthScale(d.amount));
        nodeGroup.attr('opacity', 1);
        tooltip.transition().duration(200).style('opacity', 0);
      });

    /* ── Tick handler ── */
    simulation.on('tick', () => {
      // Update hull paths
      const hullPad = isLargeGraph ? 30 : 40;
      hullPaths.attr('d', d => computeHullPath(d.ids, nodeMap, hullPad));
      hullGlowPaths.attr('d', d => computeHullPath(d.ids, nodeMap, hullPad + 10));

      // Update cluster labels — position above cluster top
      clusterLabelEls.attr('transform', d => {
        const cNodes = d.ids.map(id => nodeMap.get(id)).filter(Boolean);
        if (!cNodes.length) return '';
        let minY = Infinity;
        let sumX = 0;
        cNodes.forEach(n => { if (n.y < minY) minY = n.y; sumX += n.x; });
        const cx = sumX / cNodes.length;
        return `translate(${cx},${minY - hullPad - 14})`;
      });

      // Update edge paths
      linkPaths.attr('d', d => curvedEdgePath(d, nodeRadiusMap));

      // Update edge labels
      edgeLabels
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2 - 5)
        .text(d => formatAmount(d.amount));

      // Update node positions
      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);

      // Update hub annotations
      hubAnnotEls.each(function(d) {
        const r = nodeRadius(d);
        const offsetX = r + 40;
        const offsetY = -(r + 15);
        d3.select(this).select('line')
          .attr('x1', d.x + r + 2).attr('y1', d.y - r)
          .attr('x2', d.x + offsetX - 2).attr('y2', d.y + offsetY + 6);
        const textEl = d3.select(this).select('text');
        textEl.attr('x', d.x + offsetX).attr('y', d.y + offsetY);
        const bbox = textEl.node()?.getBBox();
        if (bbox) {
          d3.select(this).select('rect')
            .attr('x', bbox.x - 5).attr('y', bbox.y - 3)
            .attr('width', bbox.width + 10).attr('height', bbox.height + 6);
        }
      });
    });

    return () => {
      activeTimers.forEach(clearTimeout);
      clearTimeout(fitTimer);
      simulation.stop();
      d3.select(container).selectAll('div').remove();
    };
  }, [nodes, edges]);

  /* ── Time filtering ── */
  useEffect(() => {
    const linkSel = linkSelRef.current;
    if (!linkSel || !timeRange) return;
    linkSel.attr('stroke-opacity', d => {
      const ts = d.timestamps || [];
      const inRange = ts.some(t => {
        const ms = new Date(t).getTime();
        return ms >= timeRange.start && ms <= timeRange.end;
      });
      return inRange
        ? (PATTERN_COLORS[d.pattern] || PATTERN_COLORS.NORMAL).opacity
        : 0.03;
    });
  }, [timeRange]);

  /* ── Zoom controls ── */
  const handleZoom = (factor) => {
    if (!zoomRef.current) return;
    const { zoom: z, svg: s } = zoomRef.current;
    s.transition().duration(300).call(z.scaleBy, factor);
  };
  const handleFit = () => {
    if (!zoomRef.current?.fitToView) return;
    zoomRef.current.fitToView();
  };

  /* ── Legend data ── */
  const legendRoles = [
    { role: 'SOURCE', label: 'Source' },
    { role: 'AGGREGATOR', label: 'Aggregator' },
    { role: 'MULE', label: 'Mule' },
    { role: 'LEGITIMATE', label: 'Legitimate' },
  ];

  const legendPatterns = [
    { pattern: 'SMURFING', label: 'Smurfing', color: PATTERN_COLORS.SMURFING.edge },
    { pattern: 'CONSOLIDATION', label: 'Consolidation', color: PATTERN_COLORS.CONSOLIDATION.edge },
  ];

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {/* ── Insights overlay ── */}
      {insights && (
        <div style={{
          position: 'absolute', top: 10, left: 12, zIndex: 5,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 8, padding: '10px 14px',
          backdropFilter: 'blur(12px)',
          minWidth: 190,
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700,
            color: 'var(--text-muted)', letterSpacing: '1.5px',
            textTransform: 'uppercase', marginBottom: 8,
          }}>Graph Insights</div>
          <div style={{ display: 'grid', gap: 5, fontFamily: 'var(--font-mono)', fontSize: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Clusters</span>
              <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{insights.clusterCount}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Hub Nodes</span>
              <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{insights.hubCount}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Suspicious Flow</span>
              <span style={{ color: '#F43F5E', fontWeight: 600 }}>{formatAmount(insights.totalSuspicious)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Avg Risk</span>
              <span style={{ color: riskColor(insights.avgRisk), fontWeight: 600 }}>
                {Math.round(insights.avgRisk * 100)}%
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Dominant</span>
              <span style={{
                color: (PATTERN_COLORS[insights.dominantPattern] || PATTERN_COLORS.NORMAL).edge,
                fontWeight: 600,
              }}>
                {insights.dominantPattern} ({insights.dominantPct}%)
              </span>
            </div>
          </div>
        </div>
      )}

      <svg ref={svgRef} role="img"
        aria-label="Network graph showing mule account clusters, money flows, and risk levels"
        style={{ display: 'block', background: 'transparent' }} />

      {/* ── Zoom controls ── */}
      <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: 4, zIndex: 5 }}>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 14, lineHeight: 1 }}
          onClick={() => handleZoom(1.3)} aria-label="Zoom in">+</button>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 14, lineHeight: 1 }}
          onClick={() => handleZoom(0.7)} aria-label="Zoom out">-</button>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 11, lineHeight: 1 }}
          onClick={handleFit} aria-label="Fit graph to view">Fit</button>
      </div>

      {/* ── Enhanced Legend ── */}
      <div style={{
        display: 'flex', gap: 16, padding: '10px 20px 12px',
        borderTop: '1px solid var(--border)', flexWrap: 'wrap', alignItems: 'center',
      }}>
        {/* Node roles */}
        {legendRoles.map(item => (
          <div key={item.role} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{
              width: 10, height: 10, borderRadius: '50%',
              background: ROLE_COLORS[item.role] + '22',
              border: `2px solid ${ROLE_COLORS[item.role]}`,
            }} />
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {item.label}
            </span>
          </div>
        ))}

        <div style={{ width: 1, height: 14, background: 'var(--border)', margin: '0 4px' }} />

        {/* Edge patterns */}
        {legendPatterns.map(item => (
          <div key={item.pattern} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <svg width={20} height={8}>
              <path d="M0,4 Q10,0 20,4" fill="none" stroke={item.color} strokeWidth={2} opacity={0.6} />
              <polygon points="18,2 22,4 18,6" fill={item.color} opacity={0.6} />
            </svg>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {item.label}
            </span>
          </div>
        ))}

        <div style={{ width: 1, height: 14, background: 'var(--border)', margin: '0 4px' }} />

        {/* Risk scale */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Risk</span>
          <div style={{
            display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', width: 60,
          }}>
            <div style={{ flex: 1, background: '#10B981' }} />
            <div style={{ flex: 1, background: '#FBBF24' }} />
            <div style={{ flex: 1, background: '#F97316' }} />
            <div style={{ flex: 1, background: '#EF4444' }} />
          </div>
          <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Low → High
          </span>
        </div>

        {/* Particle indicator */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#3EE7FF', boxShadow: '0 0 4px #3EE7FF' }} />
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#3EE7FF', opacity: 0.3 }} />
          </div>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Money Flow
          </span>
        </div>
      </div>
    </div>
  );
}
