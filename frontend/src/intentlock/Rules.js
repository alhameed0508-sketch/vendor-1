import React, { useEffect, useState } from 'react';
import { api } from './api';
import { DECISION_TEXT } from './api';
import { ErrorNote, Spinner } from './parts';

const STAGES = [
  ['PRE_ORDER', 'Before a PayPal order is created', 'Run on every proposal, by the buyer or an assistant, against the server\'s own quote.'],
  ['PRE_CAPTURE', 'After the buyer approves in PayPal, before capture', 'The server fetches the approved order from PayPal again; every rule above runs again, plus these.'],
  ['ANY', 'Always', 'If a check cannot complete, the purchase is not allowed.'],
];

export default function Rules() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { api.rules().then(setData).catch(setError); }, []);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Spinner label="Loading the rules" />;
  return (
    <div className="stack">
      <div className="page-head">
        <p className="lede" style={{ margin: 0 }}>The fixed rules every purchase must pass. The AI can draft and propose, but it cannot change a rule or overrule a result.</p>
        <span className="status"><i />Policy <span className="mono">{data.policy_version}</span></span>
      </div>
      {STAGES.map(([stage, title, note]) => (
        <section className="panel" key={stage} aria-label={title}>
          <div className="panel-head"><h2>{title}</h2><span className="small">{note}</span></div>
          <div className="table-wrap">
            <table className="ledger">
              <thead><tr><th>Rule</th><th>What it checks</th><th>If it fails</th><th className="r">Times it stopped a purchase</th></tr></thead>
              <tbody>{data.rules.filter((r) => r.stage === stage).map((r) => (
                <tr key={r.rule_id}>
                  <td style={{ minWidth: 200 }}><b>{r.title}</b><div className="mono muted">{r.rule_id}</div></td>
                  <td style={{ maxWidth: 520 }}>{r.checks}</td>
                  <td><span className={`badge ${r.on_fail}`}>{DECISION_TEXT[r.on_fail]}</span></td>
                  <td className={`amt ${r.fired ? 'neg' : 'muted'}`}>{r.fired}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      ))}
      <p className="small muted">When several rules fail, the strictest result wins: outside the mandate, then needs approval, then cannot be verified. Counts are store-wide.</p>
    </div>
  );
}
