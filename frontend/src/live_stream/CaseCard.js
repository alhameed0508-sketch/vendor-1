import React from 'react';
import { riskBand } from './riskBand';

const money = (amount) => `₹${Number(amount).toLocaleString('en-IN')}`;

export default function CaseCard({ ring }) {
  if (!ring) {
    return (
      <aside className="live-stream__case live-stream__case--empty" aria-live="polite">
        <p>No case open yet. When a payment joins a suspicious ring, the case appears here.</p>
      </aside>
    );
  }
  const band = riskBand(ring.risk);
  return (
    <aside className="live-stream__case" aria-live="polite">
      <h2>{ring.caseId}</h2>
      <p>
        {band && <span className={`live-stream__band live-stream__band--${band.id}`}>{band.label}</span>} Risk{' '}
        {ring.risk.toFixed(2)} · {ring.members.length} accounts · opened at payment #{ring.openedAt}
      </p>
      <ul className="live-stream__chips" aria-label="Reasons">
        {ring.reasons.map((reason) => (
          <li key={reason} className="live-stream__chip">{reason}</li>
        ))}
      </ul>
      <h3 className="live-stream__sub-head">Flagged payments ({ring.payments.length})</h3>
      <ul className="live-stream__timeline">
        {ring.payments.map((p) => (
          <li key={p.id}>
            <span className="live-stream__mono">{p.from} → {p.to}</span> {money(p.amount)}
          </li>
        ))}
      </ul>
      <p className="live-stream__note">Routed to a human reviewer. The payment is not blocked.</p>
    </aside>
  );
}
