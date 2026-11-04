/* Cut points on the 0-1 risk score. Presentation bands, not calibrated probabilities. */

export const BAND_REVIEW_MIN = 0.5; // matches the backend flag threshold
export const BAND_HIGH_MIN = 0.75;

export function riskBand(score) {
  if (typeof score !== 'number' || Number.isNaN(score) || score < BAND_REVIEW_MIN) return null;
  return score >= BAND_HIGH_MIN ? { id: 'high', label: 'High' } : { id: 'review', label: 'Review' };
}
