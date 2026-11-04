import React from 'react';
import { riskBand } from './riskBand';

const money = (amount) => `₹${Number(amount).toLocaleString('en-IN')}`;
const EMPTY = { inCount: 0, inAmount: 0, outCount: 0, outAmount: 0 };

export default function NodeDetails({ id, stats, ring, counterparties, onClose }) {
  const s = stats || EMPTY;
  const band = ring ? riskBand(ring.risk) : null;
  return (
    <div
      className="live-graph__details"
      role="dialog"
      aria-label={`Account ${id}`}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="live-graph__details-head">
        <span>Account details</span>
        {band && <span className={`live-stream__band live-stream__band--${band.id}`}>{band.label}</span>}
        <button type="button" onClick={onClose} aria-label="Close details" autoFocus>×</button>
      </div>
      <dl>
        <dt>Account</dt>
        <dd className="live-stream__mono">{id}</dd>
        <dt>Case</dt>
        <dd>{ring ? <span className="live-stream__mono">{ring.caseId}</span> : 'Not in a flagged ring'}</dd>
        <dt>Received</dt>
        <dd>{money(s.inAmount)} <span className="live-graph__muted">in {s.inCount} payments</span></dd>
        <dt>Sent</dt>
        <dd>{money(s.outAmount)} <span className="live-graph__muted">in {s.outCount} payments</span></dd>
        <dt>Linked to</dt>
        <dd className="live-stream__mono">{counterparties.length ? counterparties.join(', ') : 'None yet'}</dd>
      </dl>
      <p className="live-graph__muted">Amounts cover payments seen in this replay only.</p>
    </div>
  );
}
