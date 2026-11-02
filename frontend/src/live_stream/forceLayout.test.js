import { forceLayout, hashUnit } from './forceLayout';

describe('hashUnit', () => {
  it('maps strings into [0, 1)', () => {
    ['a', 'ACC_1', ''].forEach((s) => {
      const v = hashUnit(s);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    });
  });
});

const box = { width: 400, height: 300 };
const nodes = ['A', 'B', 'C', 'D', 'E', 'F'];
const links = [
  { from: 'A', to: 'B' },
  { from: 'B', to: 'C' },
  { from: 'C', to: 'A' },
];
const dist = (p, a, b) => Math.hypot(p[a].x - p[b].x, p[a].y - p[b].y);

describe('forceLayout', () => {
  it('is deterministic and stays inside the box', () => {
    const a = forceLayout({ nodes, links, ...box });
    const b = forceLayout({ nodes, links, ...box });
    expect(a).toEqual(b);
    Object.values(a).forEach(({ x, y }) => {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(box.width);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(box.height);
    });
  });

  it('pulls linked accounts closer together than unlinked ones', () => {
    const p = forceLayout({ nodes, links, ...box });
    const linked = (dist(p, 'A', 'B') + dist(p, 'B', 'C') + dist(p, 'C', 'A')) / 3;
    const unlinked = (dist(p, 'D', 'E') + dist(p, 'E', 'F') + dist(p, 'D', 'F')) / 3;
    expect(linked).toBeLessThan(unlinked);
  });

  it('warm-starts from previous positions, so a small change moves nodes only a little', () => {
    const first = forceLayout({ nodes, links, ...box });
    const next = forceLayout({ nodes: [...nodes, 'G'], links, ...box, previous: first, iterations: 20 });
    expect(dist({ ...first, n: next.A }, 'A', 'n')).toBeLessThan(40);
    expect(next.G).toBeDefined();
  });

  it('handles empty input and does not mutate arguments', () => {
    expect(forceLayout({ nodes: [], links: [], ...box })).toEqual({});
    const frozenLinks = JSON.stringify(links);
    forceLayout({ nodes, links, ...box });
    expect(JSON.stringify(links)).toBe(frozenLinks);
  });

  it('ignores links to unknown nodes', () => {
    expect(() => forceLayout({ nodes: ['A'], links: [{ from: 'A', to: 'Z' }], ...box })).not.toThrow();
  });
});

test('lone account pairs are not crowded against the edges', () => {
  const nodes = [];
  const links = [];
  for (let i = 0; i < 25; i += 1) {
    nodes.push(`a${i}`, `b${i}`);
    links.push({ from: `a${i}`, to: `b${i}` });
  }
  const pos = forceLayout({ nodes, links, width: 800, height: 520 });
  const nearEdge = Object.values(pos).filter(({ x, y }) => x < 60 || x > 740 || y < 60 || y > 460);
  expect(nearEdge.length / nodes.length).toBeLessThan(0.55);
});
