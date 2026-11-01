/* Deterministic force-directed layout (Fruchterman-Reingold). Pure: no randomness, no
   mutation of inputs. Warm-starting from previous positions keeps a live graph steady:
   each new payment nudges the picture instead of reshuffling it. */
const MARGIN = 18;
const DEFAULT_ITERATIONS = 120;
const GRAVITY = 0.04;

// FNV-1a: a stable [0, 1) value per string, so first positions never change between renders.
export function hashUnit(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

function seed(id, width, height) {
  return {
    x: MARGIN + hashUnit(`${id}x`) * (width - 2 * MARGIN),
    y: MARGIN + hashUnit(`${id}y`) * (height - 2 * MARGIN),
  };
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function forceLayout({ nodes, links, width, height, previous = {}, iterations = DEFAULT_ITERATIONS }) {
  if (!nodes.length) return {};
  const pos = Object.fromEntries(nodes.map((id) => [id, { ...(previous[id] || seed(id, width, height)) }]));
  const edges = links.filter((l) => pos[l.from] && pos[l.to] && l.from !== l.to);
  const k = Math.sqrt((width * height) / nodes.length) * 0.6;
  const warm = nodes.every((id) => previous[id]) ? 0.25 : 1;
  let temperature = (Math.min(width, height) / 8) * warm;
  const cooling = temperature / (iterations + 1);
  const cx = width / 2;
  const cy = height / 2;

  for (let step = 0; step < iterations; step += 1) {
    const disp = Object.fromEntries(nodes.map((id) => [id, { x: 0, y: 0 }]));
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = pos[nodes[i]];
        const b = pos[nodes[j]];
        const dx = a.x - b.x || 0.01;
        const dy = a.y - b.y || 0.01;
        const d = Math.max(Math.hypot(dx, dy), 0.01);
        const f = (k * k) / d;
        disp[nodes[i]].x += (dx / d) * f;
        disp[nodes[i]].y += (dy / d) * f;
        disp[nodes[j]].x -= (dx / d) * f;
        disp[nodes[j]].y -= (dy / d) * f;
      }
    }
    edges.forEach(({ from, to }) => {
      const dx = pos[from].x - pos[to].x;
      const dy = pos[from].y - pos[to].y;
      const d = Math.max(Math.hypot(dx, dy), 0.01);
      const f = (d * d) / k;
      disp[from].x -= (dx / d) * f;
      disp[from].y -= (dy / d) * f;
      disp[to].x += (dx / d) * f;
      disp[to].y += (dy / d) * f;
    });
    const limit = temperature;
    nodes.forEach((id) => {
      const p = pos[id];
      const dx = disp[id].x + (cx - p.x) * GRAVITY * k * 0.05;
      const dy = disp[id].y + (cy - p.y) * GRAVITY * k * 0.05;
      const d = Math.max(Math.hypot(dx, dy), 0.01);
      const move = Math.min(d, limit);
      pos[id] = {
        x: clamp(p.x + (dx / d) * move, MARGIN, width - MARGIN),
        y: clamp(p.y + (dy / d) * move, MARGIN, height - MARGIN),
      };
    });
    temperature = Math.max(temperature - cooling, 0.5);
  }
  return Object.fromEntries(nodes.map((id) => [id, { x: Math.round(pos[id].x * 10) / 10, y: Math.round(pos[id].y * 10) / 10 }]));
}
