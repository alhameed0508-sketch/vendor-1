/* Pure: turns stream state into graph nodes and merged links. */
import { riskBand } from './riskBand';

const MIN_RADIUS = 3.5;
const MAX_RADIUS = 11;

function ringIndex(rings) {
  const byAccount = {};
  Object.values(rings).forEach((ring) => {
    ring.members.forEach((id) => {
      const current = byAccount[id];
      if (!current || ring.risk > current.risk) byAccount[id] = ring;
    });
  });
  return byAccount;
}

export function graphModel({ edges, rings, stats }) {
  const pairs = new Map();
  edges.forEach((e) => {
    const key = `${e.from}>${e.to}`;
    const prev = pairs.get(key);
    pairs.set(key, prev
      ? { ...prev, count: prev.count + 1, flagged: prev.flagged || e.flagged }
      : { id: key, from: e.from, to: e.to, count: 1, flagged: e.flagged });
  });
  const links = [...pairs.values()];

  const ringOf = ringIndex(rings);
  const ids = [...new Set([...edges.flatMap((e) => [e.from, e.to]), ...Object.keys(ringOf)])];
  const moved = (id) => {
    const s = stats[id];
    return s ? s.inAmount + s.outAmount : 0;
  };
  const top = Math.max(1, ...ids.map(moved));
  const nodes = ids.map((id) => {
    const ring = ringOf[id];
    const band = ring ? riskBand(ring.risk) : null;
    return {
      id,
      caseId: ring ? ring.caseId : null,
      category: band ? band.id : 'account',
      radius: MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * Math.sqrt(moved(id) / top),
    };
  });
  return { nodes, links };
}
