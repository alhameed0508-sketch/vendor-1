import { layoutNodes, hashUnit } from './layout';

const view = { width: 800, height: 480 };

describe('layoutNodes', () => {
  it('is deterministic', () => {
    const args = { accounts: ['A', 'B', 'C'], rings: [], ...view };
    expect(layoutNodes(args)).toEqual(layoutNodes(args));
  });

  it('pulls ring members into a tight cluster and leaves others spread', () => {
    const rings = [{ caseId: 'CASE-1', members: ['M1', 'M2', 'M3', 'M4'] }];
    const pos = layoutNodes({ accounts: ['M1', 'M2', 'M3', 'M4', 'X1'], rings, ...view });
    const cx = (pos.M1.x + pos.M2.x + pos.M3.x + pos.M4.x) / 4;
    const cy = (pos.M1.y + pos.M2.y + pos.M3.y + pos.M4.y) / 4;
    ['M1', 'M2', 'M3', 'M4'].forEach((id) => {
      expect(Math.hypot(pos[id].x - cx, pos[id].y - cy)).toBeLessThan(90);
      expect(pos[id].ringId).toBe('CASE-1');
    });
    expect(pos.X1.ringId).toBeNull();
  });

  it('keeps every node inside the canvas', () => {
    const pos = layoutNodes({ accounts: Array.from({ length: 50 }, (_, i) => `N${i}`), rings: [], ...view });
    Object.values(pos).forEach(({ x, y }) => {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(view.width);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(view.height);
    });
  });
});

describe('hashUnit', () => {
  it('maps strings into [0, 1)', () => {
    ['a', 'ACC_1', ''].forEach((s) => {
      const v = hashUnit(s);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    });
  });
});
