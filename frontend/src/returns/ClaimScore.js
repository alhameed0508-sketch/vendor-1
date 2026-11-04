import React from 'react';
import { AGREES_ABOVE, SIGNAL, SIGNAL_HELP, SIGNAL_ORDER } from './labels';

const NEEDED = { BLOCK: 3, CHALLENGE: 2, VERIFY: 2, APPROVE: 2 };

/** How many checks agree, and how many it takes: the firewall in one line. */
export function CorroborationBadge({ fusion, available }) {
  const need = NEEDED[fusion.tier];
  return (
    <span className="rf-agree" title={fusion.firewall}>
      {fusion.corroborating} of {available} checks agree. {need} needed to {fusion.tier === 'BLOCK' ? 'send to the fraud desk' : 'hold a refund'}.
    </span>
  );
}

/** Where the score comes from: each check's share, then adjustments, adding up to the combined score. */
export function ContributionBar({ fusion }) {
  const parts = fusion.contributions;
  if (!parts) return null;
  const total = fusion.raw_score ?? fusion.score;
  const rows = SIGNAL_ORDER.filter(n => (parts[n] ?? 0) > 0).sort((a, b) => parts[b] - parts[a]);
  const quiet = SIGNAL_ORDER.filter(n => !(parts[n] > 0));
  const shownDiffers = fusion.raw_score != null && Math.round(fusion.raw_score) !== Math.round(fusion.score);
  return (
    <div className="rf-contrib">
      {rows.length === 0 && <p className="rf-muted">No check found anything, so nothing adds to the score.</p>}
      <ul className="rf-contrib__rows">
        {rows.map(n => (
          <li key={n} title={SIGNAL_HELP[n]}>
            <span>{SIGNAL[n]}</span>
            <span className="rf-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, (parts[n] / Math.max(total, 1)) * 100)}%` }} /></span>
            <span className="num">+{parts[n].toFixed(1)}</span>
          </li>
        ))}
        {(fusion.adjustments || []).map(a => (
          <li key={a.label}>
            <span>{a.label}</span>
            <span className="rf-bar" aria-hidden="true" />
            <span className="num">{a.points.toFixed(1)}</span>
          </li>
        ))}
        <li className="rf-contrib__total">
          <span>Combined score</span>
          <span className="rf-bar" aria-hidden="true" />
          <span className="num">{total.toFixed(1)}</span>
        </li>
      </ul>
      {quiet.length > 0 && rows.length > 0 && (
        <p className="rf-muted">Adds nothing: {quiet.map(n => SIGNAL[n].toLowerCase()).join(', ')}.</p>
      )}
      {shownDiffers && (
        <p className="rf-muted">
          Shown as {Math.round(fusion.score)}, not {Math.round(total)}, {fusion.capped_from
            ? `because too few checks above ${AGREES_ABOVE} agree for the ${fusion.capped_from.toLowerCase()} band.`
            : 'so the number matches the recommendation.'}
        </p>
      )}
    </div>
  );
}
