import React, { useEffect, useRef } from 'react';

const money = (amount) => `₹${Number(amount).toLocaleString('en-IN')}`;

export default function EventLog({ log }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [log]);
  return (
    <div className="live-log">
      <div className="live-log__head">
        <span>Scoring log</span>
        <span>{log.length ? `last ${log.length} payments` : 'idle'}</span>
      </div>
      <div className="live-log__body" role="log" ref={ref} tabIndex={0}>
        {log.length === 0 && <div className="live-log__line">Waiting for payments…</div>}
        {log.map((e) => (
          <div key={e.seq} className={`live-log__line${e.decision === 'FLAG' ? ' live-log__line--flag' : ''}`}>
            <span className="live-log__seq">#{String(e.seq).padStart(4, '0')}</span>
            <span>{e.from} → {e.to}</span>
            <span>{money(e.amount)}</span>
            <span>{e.decision === 'FLAG' ? `FLAG ${e.caseId} · human review` : 'pass'}</span>
            <span className="live-log__seq">{Math.round(e.latencyMs)} ms</span>
          </div>
        ))}
      </div>
    </div>
  );
}
