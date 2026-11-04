import { riskBand, BAND_HIGH_MIN } from './riskBand';

describe('riskBand', () => {
  it('maps flagged scores to review or high', () => {
    expect(riskBand(0.5)).toEqual({ id: 'review', label: 'Review' });
    expect(riskBand(BAND_HIGH_MIN - 0.01).id).toBe('review');
    expect(riskBand(BAND_HIGH_MIN).id).toBe('high');
    expect(riskBand(1).id).toBe('high');
  });

  it('returns null for scores below the flag threshold or invalid input', () => {
    expect(riskBand(0.49)).toBeNull();
    expect(riskBand(undefined)).toBeNull();
    expect(riskBand(NaN)).toBeNull();
  });
});
