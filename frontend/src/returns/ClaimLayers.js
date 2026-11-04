import React from 'react';
import { SIGNAL, SIGNAL_HELP, SIGNAL_ORDER, formatWhen } from './labels';

const HUB_SIGNALS = ['device', 'graph'];
const STEP_SECONDS = 0.6;

/** Layer 1: every dated event, with a scrubber that moves through the case. */
export function Timeline({ events, cutoff, onCutoff, focus }) {
  if (!events.length) return <p className="rf-muted">No dated events yet. Events appear as the claim moves from delivery through filing to review.</p>;
  return (
    <>
      <label className="rf-muted" htmlFor="rf-scrub">
        Move through the case: event {cutoff + 1} of {events.length}
      </label>
      <input id="rf-scrub" className="rf-scrub" type="range" min={0} max={events.length - 1} value={cutoff}
             onChange={e => onCutoff(Number(e.target.value))} aria-valuetext={events[cutoff].label} />
      <ol className="rf-events">
        {events.map((e, i) => {
          const classes = ['rf-event', i > cutoff && 'is-later', focus && e.signal === focus && 'is-focus',
            focus && e.signal !== focus && 'is-dim'].filter(Boolean).join(' ');
          return (
            <li key={e.id} className={classes} aria-current={i === cutoff ? 'step' : undefined}>
              <time dateTime={e.at}>{formatWhen(e.at)}</time>
              <span>{e.label}</span>
            </li>
          );
        })}
      </ol>
    </>
  );
}

/** Layer 2: how hard each check hit, per claim. Clicking a check row focuses it in the other layers. */
export function Heatmap({ columns, focus, onFocus, cutoffTime }) {
  if (!columns.some(c => c.signals.some(s => s.available))) {
    return <p className="rf-muted">No checks have run yet. Results appear here as the claim progresses from filing through review.</p>;
  }
  return (
    <table className="rf-heat">
      <thead>
        <tr>
          <th scope="col"><span className="rf-muted">Check</span></th>
          {columns.map(c => <th key={c.id} scope="col">{c.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {SIGNAL_ORDER.map(name => (
          <tr key={name} className={focus === name ? 'is-focus' : undefined}>
            <th scope="row">
              <button type="button" title={SIGNAL_HELP[name]} aria-pressed={focus === name} onClick={() => onFocus(focus === name ? null : name)}>
                {SIGNAL[name]}
              </button>
            </th>
            {columns.map(c => {
              const s = c.signals.find(x => x.name === name);
              const later = cutoffTime != null && new Date(c.returnedAt) > cutoffTime;
              if (!s || !s.available) return <td key={c.id} className={`is-off${later ? ' is-later' : ''}`} title="This check did not run">—</td>;
              return (
                <td key={c.id} style={{ '--heat': s.score / 100 }} className={later ? 'is-later' : undefined}
                    title={s.reasons.join('. ')}>
                  {Math.round(s.score)}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Layer 3: customers around the edge, and the device, address or card that ties them together in the middle. */
export function RingGraph({ ring, selfCustomer, focus, cutoffTime, playKey }) {
  if (ring.customers.length < 3 || !ring.hubs.length) {
    return <p className="rf-muted">No connected customers found. When a claim shares a device, address or card with other customers, they appear here as a linked group.</p>;
  }
  const byId = Object.fromEntries([...ring.customers, ...ring.hubs].map(n => [n.id, n]));
  const hubsFocused = focus && HUB_SIGNALS.includes(focus);
  const later = c => cutoffTime != null && new Date(c.returnedAt) > cutoffTime;
  const hubDelay = ring.customers.length * STEP_SECONDS;
  return (
    <>
      <div className="rf-graph-wrap">
      <svg key={playKey} className="rf-graph rf-play" viewBox={`0 0 ${ring.width} ${ring.height}`} role="img"
           aria-label={`${ring.customers.length} customers linked through ${ring.hubs.length} shared identifiers`}>
        {ring.links.map((l, i) => {
          const a = byId[l.customer];
          const b = byId[l.hub];
          return (
            <line key={`${l.hub}-${l.customer}`} className={`rf-link${hubsFocused ? ' is-focus' : ''}`}
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y} style={{ '--delay': `${i * 0.2}s` }} />
          );
        })}
        {ring.hubs.map(h => (
          <g key={h.id} className="rf-hub-node" style={{ '--delay': `${hubDelay}s` }}>
            <rect className={`rf-hub${hubsFocused ? ' is-focus' : ''}`} x={h.x - 28} y={h.y - 11} width={56} height={22} rx={6} />
            <text x={h.x} y={h.y + 4} textAnchor="middle">{h.kind}</text>
          </g>
        ))}
        {ring.customers.map((c, i) => (
          <g key={c.id} className={`rf-person-node${c.id === selfCustomer ? ' is-self' : ''}${later(c) ? ' is-later' : ''}`}
             style={{ '--delay': `${i * STEP_SECONDS}s` }}>
            <circle className="rf-person" cx={c.x} cy={c.y} r={13} />
            <text x={c.x} y={c.y + 27} textAnchor="middle">{c.name}</text>
          </g>
        ))}
      </svg>
      </div>
      <p className="rf-caption">
        These {ring.customers.length} customers share {ring.hubs.map(h => h.kind.toLowerCase()).join(', ')}.
        Sharing one is common, sharing several is rare. That is a reason for a person to look, not proof.
      </p>
    </>
  );
}
