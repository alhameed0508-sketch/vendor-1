import React, { useMemo, useState } from 'react';
import useScoreStream from './useScoreStream';
import { p95 } from './streamReducer';
import CaseCard from './CaseCard';
import GraphCanvas from './GraphCanvas';
import NodeDetails from './NodeDetails';
import EventLog from './EventLog';
import './LiveStream.css';

const RATES = [2, 5, 10, 20];
const STATUS_LABEL = { idle: 'Ready', live: 'Streaming', ended: 'Replay finished', error: 'Unavailable' };

function Stat({ label, value, tone }) {
  return (
    <div className={`live-stream__stat${tone ? ` live-stream__stat--${tone}` : ''}`}>
      <div className="live-stream__stat-label">{label}</div>
      <div className="live-stream__stat-value">{value}</div>
    </div>
  );
}

export default function LiveStream() {
  const [rate, setRate] = useState(5);
  const { state, start, stop, review } = useScoreStream({ rate });
  const { counters, edges, rings, accountStats, log, latestCaseId, latencies, reviews, status, error } = state;
  const [picked, setPicked] = useState(null);
  const [selected, setSelected] = useState(null);

  const ringList = useMemo(() => Object.values(rings), [rings]);
  const shownId = picked && rings[picked] ? picked : latestCaseId;
  const selectedRing = useMemo(
    () => ringList.filter((r) => r.members.includes(selected)).sort((a, b) => b.risk - a.risk)[0] || null,
    [ringList, selected]
  );
  const counterparties = useMemo(
    () => [
      ...new Set(edges.flatMap((e) => (e.from === selected ? [e.to] : e.to === selected ? [e.from] : []))),
    ].sort(),
    [edges, selected]
  );
  const latency = p95(latencies);
  const running = status === 'live';

  return (
    <section className="live-stream" aria-label="Live payment stream">
      <header className="live-stream__head">
        <div>
          <h1 className="live-stream__title">Live payment stream</h1>
          <p className="live-stream__sub">
            Each payment is scored against the account network as it arrives. Flags route a ring to a human reviewer.
          </p>
        </div>
        <div className="live-stream__controls">
          <span className="live-stream__pill">Synthetic data</span>
          <label>
            <span className="sr-only">Payments per second </span>
            <select value={rate} onChange={(e) => setRate(Number(e.target.value))} disabled={running}>
              {RATES.map((r) => (
                <option key={r} value={r}>
                  {r} payments/s
                </option>
              ))}
            </select>
          </label>
          {running ? (
            <button type="button" onClick={stop}>Stop</button>
          ) : (
            <button type="button" onClick={start}>{status === 'idle' ? 'Start stream' : 'Replay'}</button>
          )}
        </div>
      </header>

      {status === 'error' && <div className="live-stream__error" role="alert">{error}</div>}

      <div className="live-stream__stats" role="status" aria-label={STATUS_LABEL[status]}>
        <Stat label="Payments scored" value={counters.payments} />
        <Stat label="Flagged for review" value={counters.flagged} tone={counters.flagged ? 'alert' : undefined} />
        <Stat label="Mule payments caught" value={counters.mule_payments_flagged} />
        <Stat label="Genuine accounts flagged" value={counters.genuine_accounts_flagged} tone="good" />
        <Stat label="p95 latency" value={latency == null ? '–' : `${Math.round(latency)} ms`} />
      </div>

      <div className="live-stream__body">
        <div className="live-stream__graph-col">
          <div className="live-stream__graph-wrap">
            <GraphCanvas edges={edges} rings={rings} stats={accountStats} selected={selected} onSelect={setSelected} />
            {selected && (
              <NodeDetails
                id={selected}
                stats={accountStats[selected]}
                ring={selectedRing}
                counterparties={counterparties}
                onClose={() => setSelected(null)}
              />
            )}
          </div>
          <EventLog log={log} />
        </div>
        <div>
          {ringList.length > 1 && (
            <div className="live-stream__cases" role="group" aria-label="Open cases">
              {ringList.map((r) => (
                <button key={r.caseId} type="button" aria-pressed={r.caseId === shownId} onClick={() => setPicked(r.caseId)}>
                  {r.caseId}
                </button>
              ))}
            </div>
          )}
          <CaseCard ring={shownId ? rings[shownId] : null} decision={shownId ? reviews[shownId] : null} onReview={review} />
        </div>
      </div>
      <p className="live-stream__note">
        Synthetic data only. Ground-truth labels stay on the server and are used only to count genuine accounts.
      </p>
    </section>
  );
}
