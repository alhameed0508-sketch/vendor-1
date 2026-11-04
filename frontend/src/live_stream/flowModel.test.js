import { flowModel } from './flowModel';

const payments = [
  { id: 'T1', from: 'S', to: 'M', amount: 1000 },
  { id: 'T2', from: 'M', to: 'A', amount: 900 },
  { id: 'T3', from: 'X', to: 'A', amount: 100 },
];

describe('flowModel', () => {
  it('orders accounts by first appearance, so money reads left to right', () => {
    expect(flowModel(payments).nodes).toEqual(['S', 'M', 'A', 'X']);
  });

  it('scales link width by amount within the case', () => {
    const { links } = flowModel(payments);
    expect(links).toHaveLength(3);
    expect(links[0].width).toBeGreaterThan(links[2].width);
    expect(Math.max(...links.map((l) => l.width))).toBeLessThanOrEqual(8);
    expect(Math.min(...links.map((l) => l.width))).toBeGreaterThanOrEqual(1);
  });

  it('handles an empty list and does not mutate input', () => {
    expect(flowModel([])).toEqual({ nodes: [], links: [] });
    const copy = JSON.stringify(payments);
    flowModel(payments);
    expect(JSON.stringify(payments)).toBe(copy);
  });
});
