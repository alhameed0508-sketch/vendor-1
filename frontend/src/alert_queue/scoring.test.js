import { riskTerm, scorePriority, breakdown } from './scoring';

const base = { risk_score: 0.99, total_amount: 100000, nodes: [], reason_codes: [] };

describe('riskTerm', () => {
  test('uses the evidence-weighted rank when the backend sends one', () => {
    expect(riskTerm({ ...base, rank_score: 0.3 })).toBe(0.3);
  });

  test('falls back to the raw risk score', () => {
    expect(riskTerm(base)).toBe(0.99);
    expect(riskTerm({})).toBe(0);
  });

  test('never exceeds 1', () => {
    expect(riskTerm({ rank_score: 4 })).toBe(1);
  });
});

describe('queue ranking', () => {
  test('a saturated-risk ring with no member evidence ranks below one with evidence', () => {
    const hollow = { ...base, rank_score: 0.1 };
    const solid = { ...base, rank_score: 0.8 };
    expect(scorePriority(solid)).toBeGreaterThan(scorePriority(hollow));
  });

  test('the score breakdown shows the same risk term as the ranking', () => {
    expect(breakdown({ ...base, rank_score: 0.4 }).risk_score).toBe(0.4);
  });
});
