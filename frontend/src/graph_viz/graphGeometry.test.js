import { computeHullPath, curvedEdgePath, hubTargets, pointOnEdge } from './graphGeometry';

// Source at the origin, target 100px to the right with a 10px node radius.
const EDGE = { source: { id: 'S', x: 0, y: 0 }, target: { id: 'T', x: 100, y: 0 } };
const RADII = new Map([['T', 10]]);

describe('curvedEdgePath', () => {
  it('bends the edge and stops it clear of the target node and its ring', () =>
    expect(curvedEdgePath(EDGE, RADII)).toBe('M0,0Q40,-12,80,0'));
});

describe('hubTargets', () => {
  const into = (target, n) => Array.from({ length: n }, (_, i) => ({ source: `S${target}${i}`, target }));

  it('lists accounts that receive from six or more others', () =>
    expect(hubTargets([...into('H', 6), ...into('Q', 5)])).toEqual(new Set(['H'])));
  it('reads targets that the layout already resolved to nodes', () =>
    expect(hubTargets(into('H', 6).map(l => ({ ...l, target: { id: 'H' } })))).toEqual(new Set(['H'])));
});

describe('pointOnEdge', () => {
  it('starts at the source', () => expect(pointOnEdge(EDGE, RADII, 0)).toEqual([0, 0]));
  it('ends where the drawn edge ends', () => expect(pointOnEdge(EDGE, RADII, 1)).toEqual([80, 0]));
  it('follows the same curve in between', () => expect(pointOnEdge(EDGE, RADII, 0.5)).toEqual([40, -6]));
});

describe('computeHullPath', () => {
  const nodeMap = new Map([
    ['A', { x: 0, y: 0 }], ['B', { x: 50, y: 0 }], ['C', { x: 25, y: 40 }], ['NaN', { x: NaN, y: 0 }],
  ]);
  it('draws nothing for unknown or unplaced nodes', () =>
    expect(computeHullPath(['missing', 'NaN'], nodeMap, 10)).toBe(''));
  it('draws a circle around a single node', () =>
    expect(computeHullPath(['A'], nodeMap, 10)).toMatch(/^M-10,0A10,10/));
  it.each([[['A', 'B']], [['A', 'B', 'C']]])('draws a closed outline around %j', ids => {
    const path = computeHullPath(ids, nodeMap, 10);
    const start = path.match(/^M([-\d.]+,[-\d.]+)/)[1];
    expect(path.endsWith(start)).toBe(true);
  });
});
