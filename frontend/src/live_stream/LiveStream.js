import React, { useMemo, useState } from 'react';
import useScoreStream from './useScoreStream';
import { p95 } from './streamReducer';
import { layoutNodes } from './layout';
import './LiveStream.css';

const VIEW = { width: 800, height: 480 };
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

function CaseCard({ ring }) {
  if (!ring) {
    return (
      <aside className="live-stream__case live-stream__case--empty" aria-live="polite">
        <p>No case open yet. When a payment joins a suspicious ring, the case appears here.</p>
      </aside>
    );
  }
  return (
    <aside className="live-stream__case" aria-live="polite">
      <h2>{ring.caseId}</h2>
      <p>
        Risk {ring.risk.toFixed(2)} · {ring.members.length} accounts · opened at payment #{ring.openedAt}
      </p>
      <ul>
        {ring.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <p className="live-stream__note">Routed to a human reviewer. The payment is not blocked.</p>
    </aside>
  );
}

export default function LiveStream() {
  const [rate, setRate] = useState(5);
  const { state, start, stop } = useScoreStream({ rate });
  const { counters, edges, rings, flaggedAccounts, latestCaseId, latencies, status, error } = state;

  const ringList = useMemo(() => Object.values(rings), [rings]);
  const accounts = useMemo(
    () => [...new Set([...edges.flatMap((e) => [e.from, e.to]), ...flaggedAccounts])],
    [edges, flaggedAccounts]
  );
  const positions = useMemo(
    () => layoutNodes({ accounts, rings: ringList, ...VIEW }),
    [accounts, ringList]
  );
  const flagged = useMemo(() => new Set(flaggedAccounts), [flaggedAccounts]);
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
        <div className="live-stream__graph">
          <svg viewBox={`0 0 ${VIEW.width} ${VIEW.height}`} role="img" aria-label="Account network with flagged rings highlighted">
            {edges.map((e) =>
              positions[e.from] && positions[e.to] ? (
                <line
                  key={e.id}
                  className={`live-stream__edge${e.flagged ? ' live-stream__edge--flag' : ''}`}
                  x1={positions[e.from].x}
                  y1={positions[e.from].y}
                  x2={positions[e.to].x}
                  y2={positions[e.to].y}
                />
              ) : null
            )}
            {accounts.map((id) => (
              <g
                key={id}
                className="live-stream__node"
                style={{ transform: `translate(${positions[id].x}px, ${positions[id].y}px)` }}
              >
                <circle r={flagged.has(id) ? 6 : 3.5} fill={flagged.has(id) ? 'var(--critical)' : 'var(--text-faint)'} />
              </g>
            ))}
          </svg>
        </div>
        <CaseCard ring={latestCaseId ? rings[latestCaseId] : null} />
      </div>
      <p className="live-stream__note">
        Synthetic data only. Ground-truth labels stay on the server and are used only to count genuine accounts.
      </p>
    </section>
  );
}
