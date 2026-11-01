/* Deterministic layout: no physics, so the picture never jitters on a projector.
   Ring members slide into a cluster; everyone else keeps a stable hashed spot. */

const MARGIN = 24;
const MIN_RING_RADIUS = 28;
const RING_RADIUS_PER_MEMBER = 3;
const MAX_RING_RADIUS = 70;

export function hashUnit(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

function ringCenters(rings, width, height) {
  const cx = width / 2;
  const cy = height / 2;
  const orbit = Math.min(width, height) * 0.28;
  return rings.map((ring, i) => {
    const angle = (2 * Math.PI * i) / Math.max(rings.length, 1) - Math.PI / 2;
    return rings.length === 1
      ? { cx, cy }
      : { cx: cx + orbit * 1.4 * Math.cos(angle), cy: cy + orbit * Math.sin(angle) };
  });
}

export function layoutNodes({ accounts, rings, width, height }) {
  const positions = {};
  const centers = ringCenters(rings, width, height);
  rings.forEach((ring, ringIndex) => {
    const { cx, cy } = centers[ringIndex];
    const radius = Math.min(MAX_RING_RADIUS, MIN_RING_RADIUS + RING_RADIUS_PER_MEMBER * ring.members.length);
    ring.members.forEach((id, i) => {
      if (positions[id]) return;
      const angle = (2 * Math.PI * i) / ring.members.length;
      positions[id] = { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle), ringId: ring.caseId };
    });
  });
  accounts.forEach((id) => {
    if (positions[id]) return;
    positions[id] = {
      x: MARGIN + hashUnit(`${id}x`) * (width - 2 * MARGIN),
      y: MARGIN + hashUnit(`${id}y`) * (height - 2 * MARGIN),
      ringId: null,
    };
  });
  return positions;
}
