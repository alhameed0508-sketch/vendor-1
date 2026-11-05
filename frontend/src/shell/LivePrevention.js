import React, { useEffect, useState } from 'react';
import useScoreStream from '../live_stream/useScoreStream';
import { confirmedAmount } from '../live_stream/streamReducer';
import { formatAmount } from '../utils/formatAmount';
import { SplitBar } from './Bars';
import './shell.css';

const TAPE_SIZE = 40;
const TABLE_ROWS = 8;
const CASE_ROWS = 6;

// Both sources are real and unlabelled, so the only money counted as prevented (or confirmed) is what a
// reviewer has confirmed. Trades cannot be stopped, so the stock view says "confirmed", not "prevented".
export const SOURCES = {
  live: {
    option: 'Live public payments',
    scored: 'Payments scored',
    passed: 'Payments authorised',
    value: 'Money scored',
    done: 'Prevented (verified)',
    split: 'Where the money went',
    segments: ['Authorised', 'Awaiting review', 'Prevented'],
    columns: ['From', 'To', 'Amount'],
    members: n => `${n} accounts`,
    rows: 'Latest payments',
  },
  market: {
    option: 'Live stock trades',
    scored: 'Trades checked',
    passed: 'Trades passed',
    value: 'Value traded',
    done: 'Confirmed by a reviewer',
    split: 'Where the traded value went',
    segments: ['Passed', 'Awaiting review', 'Confirmed'],
    columns: ['Stock', 'Exchange', 'Value'],
    members: () => '1 stock',
    rows: 'Latest trades',
  },
};

function Tile({ label, value, tone }) {
  return (
    <div className={`premium-card live-prev__tile${tone ? ` live-prev__tile--${tone}` : ''}`}>
      <div className="meta-label">{label}</div>
      <div className="data-value">{value}</div>
    </div>
  );
}

/** One bar per recent payment or trade, as tall as its value; held ones take the alert colour. */
function Tape({ log, label }) {
  const recent = log.slice(-TAPE_SIZE);
  const top = Math.max(1, ...recent.map(p => Number(p.amount) || 0));
  return (
    <div className="live-prev__tape" role="img" aria-label={`${label} by value, held ones highlighted`}>
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

/** Live money view on real data only: what is being scored, what is held, and what a reviewer has confirmed. */
export default function LivePrevention() {
  const [source, setSource] = useState('live');
  const { state, start, stop, review } = useScoreStream({ rate: 5, source });
  const { status, error, notice, counters, amounts, log, rings, reviews } = state;
  const words = SOURCES[source];
  const confirmed = confirmedAmount(state);
  const cases = Object.values(rings).sort((a, b) => b.openedAt - a.openedAt).slice(0, CASE_ROWS);
  const running = status === 'live';
  // Authorised = everything that was not held. Held money splits into what a reviewer has
  // confirmed and what is still waiting for review.
  const authorisedAmount = Math.max(0, (amounts.scored || 0) - (amounts.held || 0));
  const authorisedCount = Math.max(0, (counters.payments || 0) - (counters.flagged || 0));
  const confirmedShown = Math.min(confirmed, amounts.held || 0);
  // Starts on mount and again whenever the source changes, so the panel is never empty; Pause stays with the user.
  useEffect(() => { start(); }, [start]);

  return (
    <section className="live-prev" aria-label="Live payment prevention">
      <div className="live-prev__bar-top">
        <h2 className="live-prev__title">Live data</h2>
        <span className="live-prev__pill">Real data</span>
        <label>
          <span className="sr-only">Data source </span>
          <select value={source} onChange={e => setSource(e.target.value)}>
            {Object.entries(SOURCES).map(([value, s]) => <option key={value} value={value}>{s.option}</option>)}
          </select>
        </label>
        {running
          ? <button type="button" onClick={stop}>Pause</button>
          : <button type="button" onClick={start}>{status === 'idle' ? 'Start' : 'Resume'}</button>}
      </div>
      {status === 'error' && <div role="alert" className="shell-error">{error}</div>}
      {notice && <div role="status" className="shell-notice">{notice}</div>}
      {running && counters.payments === 0 && !notice && (
        <div role="status" className="mod-card__sub">Connecting to the live feed. The first {source === 'market' ? 'trades' : 'payments'} arrive within a few seconds.</div>
      )}
      <div className="shell-stats">
        <Tile label={words.scored} value={counters.payments} />
        <Tile label={words.passed} value={`${authorisedCount} · ${formatAmount(authorisedAmount)}`} tone="ok" />
        <Tile label={words.value} value={formatAmount(amounts.scored)} />
        <Tile label="Held for review" value={formatAmount(amounts.held)} tone="alert" />
        <Tile label={words.done} value={formatAmount(confirmed)} tone="good" />
      </div>
      <SplitBar
        label={words.split}
        format={formatAmount}
        segments={[
          { label: words.segments[0], value: authorisedAmount, tone: 'ok' },
          { label: words.segments[1], value: Math.max(0, (amounts.held || 0) - confirmedShown), tone: 'held' },
          { label: words.segments[2], value: confirmedShown, tone: 'prevented' },
        ]}
      />
      <Tape log={log} label={words.rows} />
      <table className="live-prev__table" aria-label="Open cases">
        <thead><tr><th>Case</th><th>{source === 'market' ? 'Stock' : 'Members'}</th><th>Held</th><th>Risk</th><th>Reviewer</th></tr></thead>
        <tbody>
          {cases.map(r => (
            <tr key={r.caseId}>
              <td>{r.caseId}</td>
              <td>{source === 'market' ? r.members[0] : words.members(r.members.length)}</td>
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
      <table className="live-prev__table" aria-label={words.rows}>
        <thead><tr>{words.columns.map(c => <th key={c}>{c}</th>)}<th>Result</th></tr></thead>
        <tbody>
          {[...log].reverse().slice(0, TABLE_ROWS).map(p => (
            <tr key={p.seq} className={p.decision === 'FLAG' ? 'live-prev__row--held' : undefined}>
              <td className="live-prev__id">{p.from}</td>
              <td className="live-prev__id">{p.to}</td>
              <td className="data-value">{formatAmount(p.amount)}</td>
              <td>{p.decision === 'FLAG' ? 'Held' : 'Passed'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
