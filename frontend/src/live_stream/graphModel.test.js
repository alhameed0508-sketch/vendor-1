import { graphModel } from './graphModel';

const edges = [
  { id: 'T1', from: 'A', to: 'B', flagged: true },
  { id: 'T2', from: 'A', to: 'B', flagged: false },
  { id: 'T3', from: 'C', to: 'D', flagged: false },
];
const rings = { 'CASE-1': { caseId: 'CASE-1', members: ['A', 'B', 'E'], risk: 0.9 } };
const stats = { A: { inCount: 0, inAmount: 0, outCount: 2, outAmount: 5000 } };

describe('graphModel', () => {
  it('merges repeated payments between a pair into one link', () => {
    const { links } = graphModel({ edges, rings, stats });
    const ab = links.find((l) => l.from === 'A' && l.to === 'B');
    expect(links).toHaveLength(2);
    expect(ab).toMatchObject({ count: 2, flagged: true });
  });

  it('categorises accounts by the band of their ring', () => {
    const { nodes } = graphModel({ edges, rings, stats });
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    expect(byId.A.category).toBe('high');
    expect(byId.E.category).toBe('high');
    expect(byId.C.category).toBe('account');
    expect(byId.A.caseId).toBe('CASE-1');
  });

  it('sizes nodes by money moved', () => {
    const { nodes } = graphModel({ edges, rings, stats });
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    expect(byId.A.radius).toBeGreaterThan(byId.C.radius);
  });
});
