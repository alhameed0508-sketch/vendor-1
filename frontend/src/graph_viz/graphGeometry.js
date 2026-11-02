import * as d3 from 'd3';

// Arrowheads stop clear of the node and its risk ring.
const TARGET_GAP = 10;

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
export function computeHullPath(nodeIds, nodeMap, padding) {
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
export function curvedEdgePath(d, nodeRadiusMap) {
  const sx = d.source.x, sy = d.source.y;
  const tx = d.target.x, ty = d.target.y;
  const dx = tx - sx, dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const tgtR = nodeRadiusMap.get(d.target.id) || 12;
  const shortenRatio = (tgtR + TARGET_GAP) / dist;
  const endX = tx - dx * shortenRatio;
  const endY = ty - dy * shortenRatio;
  const curvature = 0.12;
  const mx = (sx + endX) / 2 + dy * curvature;
  const my = (sy + endY) / 2 - dx * curvature;
  return `M${sx},${sy}Q${mx},${my},${endX},${endY}`;
}

/** Point on the same curve at t (0..1), so replay dots follow the drawn edge. */
export function pointOnEdge(d, nodeRadiusMap, t) {
  const sx = d.source.x, sy = d.source.y;
  const dx = d.target.x - sx, dy = d.target.y - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const shorten = ((nodeRadiusMap.get(d.target.id) || 12) + TARGET_GAP) / dist;
  const ex = d.target.x - dx * shorten, ey = d.target.y - dy * shorten;
  const mx = (sx + ex) / 2 + dy * 0.12, my = (sy + ey) / 2 - dx * 0.12;
  const u = 1 - t;
  return [u * u * sx + 2 * u * t * mx + t * t * ex, u * u * sy + 2 * u * t * my + t * t * ey];
}
