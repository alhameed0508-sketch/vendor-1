import React, { useEffect, useState } from 'react';
import useScoreStream from '../live_stream/useScoreStream';
import { confirmedAmount } from '../live_stream/streamReducer';
import { formatAmount } from '../utils/formatAmount';
import { SplitBar } from './Bars';
import './shell.css';

const TAPE_SIZE = 40;
const TABLE_ROWS = 8;
const CASE_ROWS = 6;

function Tile({ label, value, tone }) {
  return (
    <div className={`premium-card live-prev__tile${tone ? ` live-prev__tile--${tone}` : ''}`}>
      <div className="meta-label">{label}</div>
      <div className="data-value">{value}</div>
    </div>
  );
}

/** One bar per recent payment, as tall as its amount; held payments take the alert colour. */
function Tape({ log }) {
  const recent = log.slice(-TAPE_SIZE);
  const top = Math.max(1, ...recent.map(p => Number(p.amount) || 0));
  return (
    <div className="live-prev__tape" role="img" aria-label="Recent payments by amount, held payments highlighted">
      {recent.map(p => (
        <span
          key={p.seq}
          className={`live-prev__bar${p.decision === 'FLAG' ? ' live-prev__bar--held' : ''}`}
          style={{ height: `${Math.max(4, ((Number(p.amount) || 0) / top) * 100)}%` }}
          title={`${p.from} to ${p.to}: ${formatAmount(p.amount)}`}
        />
      ))}
    </div>
  );
}

/** Live money view: what is being scored, what is held, and what a reviewer has confirmed as prevented. */
export default function LivePrevention() {
  const [source, setSource] = useState('demo');
  const { state, start, stop, review } = useScoreStream({ rate: 5, source });
  const { status, error, counters, amounts, log, rings, reviews } = state;
  // The synthetic replay knows which payments were truly mule money; a real feed has no labels, so only a reviewer's confirmation counts.
  const prevented = counters.mule_amount_flagged ?? confirmedAmount(state);
  const cases = Object.values(rings).sort((a, b) => b.openedAt - a.openedAt).slice(0, CASE_ROWS);
  const running = status === 'live';
  // Authorised = every payment that was not held. Held money splits into what a reviewer (or, on
  // synthetic data, the ground truth) confirms as prevented and what is still waiting for review.
  const authorisedAmount = Math.max(0, (amounts.scored || 0) - (amounts.held || 0));
  const authorisedCount = Math.max(0, (counters.payments || 0) - (counters.flagged || 0));
  const preventedShown = Math.min(prevented || 0, amounts.held || 0);
  // Starts once on mount so the panel is never empty; Pause and Resume stay with the user.
  useEffect(() => { start(); }, []);

  return (
    <section className="live-prev" aria-label="Live payment prevention">
      <div className="live-prev__bar-top">
        <h2 className="live-prev__title">Live payments</h2>
        <span className="live-prev__pill">{source === 'live' ? 'Real data' : 'Synthetic data'}</span>
        <label>
          <span className="sr-only">Data source </span>
          <select value={source} onChange={e => setSource(e.target.value)} disabled={running}>
            <option value="demo">Synthetic replay</option>
            <option value="live">Real Bitcoin payments</option>
          </select>
        </label>
        {running
          ? <button type="button" onClick={stop}>Pause</button>
          : <button type="button" onClick={start}>{status === 'idle' ? 'Start' : 'Resume'}</button>}
      </div>
      {status === 'error' && <div role="alert" className="shell-error">{error}</div>}
      <div className="shell-stats">
        <Tile label="Payments scored" value={counters.payments} />
        <Tile label="Payments authorised" value={`${authorisedCount} · ${formatAmount(authorisedAmount)}`} tone="ok" />
        <Tile label="Money scored" value={formatAmount(amounts.scored)} />
        <Tile label="Held for review" value={formatAmount(amounts.held)} tone="alert" />
        <Tile label="Prevented (verified)" value={formatAmount(prevented)} tone="good" />
        {counters.genuine_amount_flagged != null && (
          <Tile label="Genuine money wrongly held" value={formatAmount(counters.genuine_amount_flagged)} />
        )}
      </div>
      <SplitBar
        label="Where the money went"
        format={formatAmount}
        segments={[
          { label: 'Authorised', value: authorisedAmount, tone: 'ok' },
          { label: 'Awaiting review', value: Math.max(0, (amounts.held || 0) - preventedShown), tone: 'held' },
          { label: 'Prevented', value: preventedShown, tone: 'prevented' },
        ]}
      />
      <Tape log={log} />
      <table className="live-prev__table" aria-label="Open cases">
        <thead><tr><th>Case</th><th>Members</th><th>Held</th><th>Risk</th><th>Reviewer</th></tr></thead>
        <tbody>
          {cases.map(r => (
            <tr key={r.caseId}>
              <td>{r.caseId}</td>
              <td>{r.members.length} accounts</td>
              <td className="data-value">{formatAmount(r.held)}</td>
              <td>{Math.round(r.risk * 100)}%</td>
              <td>
                {reviews[r.caseId]
                  ? (reviews[r.caseId] === 'confirmed' ? 'Confirmed' : 'Dismissed')
                  : (
                    <>
                      <button type="button" onClick={() => review(r.caseId, 'confirmed')}>Confirm</button>
                      {' '}
                      <button type="button" onClick={() => review(r.caseId, 'dismissed')}>Dismiss</button>
                    </>
                  )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <table className="live-prev__table" aria-label="Latest payments">
        <thead><tr><th>From</th><th>To</th><th>Amount</th><th>Result</th></tr></thead>
        <tbody>
          {[...log].reverse().slice(0, TABLE_ROWS).map(p => (
            <tr key={p.seq} className={p.decision === 'FLAG' ? 'live-prev__row--held' : undefined}>
              <td>{p.from}</td>
              <td>{p.to}</td>
              <td className="data-value">{formatAmount(p.amount)}</td>
              <td>{p.decision === 'FLAG' ? 'Held' : 'Passed'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
