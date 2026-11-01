import { roleStyle, nodeRadius, ringWidth, shapePath, edgeStyle } from './graphStyle';

describe('roleStyle', () => {
  it('gives each suspicious role its own colour token and shape', () => {
    expect(roleStyle('SOURCE')).toMatchObject({ color: 'var(--role-source)', shape: 'diamond' });
    expect(roleStyle('AGGREGATOR')).toMatchObject({ color: 'var(--role-aggregator)', shape: 'hexagon' });
    expect(roleStyle('MULE')).toMatchObject({ color: 'var(--role-mule)', shape: 'circle' });
  });
  it('keeps legitimate and unknown accounts neutral grey', () => {
    expect(roleStyle('LEGITIMATE').color).toBe('var(--role-neutral)');
    expect(roleStyle(undefined).color).toBe('var(--role-neutral)');
  });
});

describe('nodeRadius', () => {
  it('grows with risk', () =>
    expect(nodeRadius({ role: 'MULE', smurf_score: 1 })).toBeGreaterThan(nodeRadius({ role: 'MULE', smurf_score: 0 })));
  it('makes sources larger than mules', () =>
    expect(nodeRadius({ role: 'SOURCE' })).toBeGreaterThan(nodeRadius({ role: 'MULE' })));
});

describe('ringWidth', () => {
  it.each([[0, 0.75], [1, 3.5], [2, 3.5], [-1, 0.75]])('%s -> %s', (score, width) =>
    expect(ringWidth(score)).toBeCloseTo(width));
});

describe('shapePath', () => {
  const vertices = path => (path.match(/L/g) || []).length + 1;
  it('draws a four-point diamond', () => expect(vertices(shapePath('diamond', 10))).toBe(4));
  it('draws a six-point hexagon', () => expect(vertices(shapePath('hexagon', 10))).toBe(6));
  it('draws a circle with arcs', () => expect(shapePath('circle', 10)).toMatch(/A10,10/));
});

describe('edgeStyle', () => {
  it('draws flagged transfers solid and other transfers dashed', () => {
    expect(edgeStyle(true).dash).toBeNull();
    expect(edgeStyle(false).dash).toBeTruthy();
  });
});
