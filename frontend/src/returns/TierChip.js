import React from 'react';
import { TIER } from './labels';

/** The recommendation as a word and a dot, so colour never carries it alone. */
export function TierChip({ tier, score }) {
  const t = TIER[tier];
  return (
    <span className="rf-chip" style={{ color: t.colour }}>
      {score != null ? `${t.label}, ${Math.round(score)}` : t.label}
    </span>
  );
}
