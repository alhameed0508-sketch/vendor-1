import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, money, shortId, when } from './api';
import { DecisionBadge, ErrorNote, Spinner } from './parts';

const OUTCOME = {
  RECEIPT_CREATED: ['Paid', 'ok'], CAPTURED: ['Paid', 'ok'], REFUNDED: ['Refunded', 'warn'],
  BLOCKED: ['Refused', 'bad'], REAUTHORISATION_REQUIRED: ['Needs your approval', 'warn'], REVIEW_REQUIRED: ['Could not be verified', 'info'],
  POLICY_ALLOWED: ['Allowed, not paid', 'plain'], PAYPAL_ORDER_CREATED: ['Waiting for PayPal approval', 'plain'],
  PAYPAL_APPROVAL_CANCELLED: ['PayPal approval cancelled', 'plain'], BUYER_APPROVED: ['Approved, not yet captured', 'plain'],
  CAPTURE_REQUESTED: ['Capture in progress', 'plain'], RECONCILIATION_REQUIRED: ['Checking with PayPal', 'warn'],
  CAPTURE_DENIED: ['PayPal declined', 'bad'], EXPIRED: ['Expired', 'plain'],
};
const FILTERS = [['all', 'All'], ['ALLOW', 'Allowed'], ['refused', 'Refused'], ['agent', 'Proposed by an agent']];

export default function Activity() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const load = useCallback(() => { setError(null); api.activity().then(setData).catch(setError); }, []);
  useEffect(load, [load]);

  if (error) return <ErrorNote error={error} onRetry={load} />;
  if (!data) return <Spinner label="Loading activity" />;
  const st = data.stats;
  const rows = data.rows.filter((r) => filter === 'all' || (filter === 'refused' ? r.decision !== 'ALLOW' : filter === 'agent' ? r.proposed_by === 'agent' : r.decision === filter));
  const most = Math.max(1, ...st.by_rule.map((r) => r.count));

  return (
    <div className="stack">
      <div>
        <p className="eyebrow">Activity</p>
        <h1>Every proposal, and what the rules decided</h1>
        <p className="lede">Each row is one product put forward under one of your mandates, by you or by an assistant. Refusals show the rule that stopped them.</p>
      </div>

      {st.proposals === 0 ? (
        <div className="card stack">
          <h2>Nothing here yet</h2>
          <p className="muted">Proposals appear here once you confirm a mandate and a product is checked against it.</p>
          <div><Link className="btn primary" to="/">Start a purchase</Link></div>
        </div>
      ) : (
        <>
          <div className="tiles">
            <div className="tile"><span className="tile-n num">{st.proposals}</span><span className="small muted">proposals checked{st.by_agent ? `, ${st.by_agent} by an agent` : ''}</span></div>
            <div className="tile"><span className="tile-n num" style={{ color: 'var(--allow)' }}>{st.allowed}</span><span className="small muted">within a mandate</span></div>
            <div className="tile"><span className="tile-n num" style={{ color: 'var(--block)' }}>{st.refused}</span><span className="small muted">refused before any money moved</span></div>
            <div className="tile"><span className="tile-n num">{st.captured_count ? money(st.captured_minor, st.currency) : 'none'}</span><span className="small muted">captured in {st.captured_count} payment{st.captured_count === 1 ? '' : 's'}</span></div>
          </div>

          {st.by_rule.length > 0 && (
            <section className="card stack" aria-labelledby="why">
              <h2 id="why">Why purchases were refused</h2>
              <ul className="bars">
                {st.by_rule.map((r) => (
                  <li key={r.rule_id}>
                    <span className="mono">{r.rule_id}</span>
                    <span className="bar"><span style={{ width: `${(r.count / most) * 100}%` }} /></span>
                    <span className="num">{r.count}</span>
                  </li>
                ))}
              </ul>
              <p className="small muted">A proposal can fail more than one rule, so these can add up to more than the number refused.</p>
            </section>
          )}

          <section className="card stack" aria-labelledby="ledger">
            <div className="row between">
              <h2 id="ledger">Ledger</h2>
              <div className="seg" role="group" aria-label="Filter">
                {FILTERS.map(([key, label]) => <button key={key} type="button" aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}
              </div>
            </div>
            <div className="table-wrap">
              <table className="checks ledger">
                <thead><tr><th>When</th><th>Product</th><th>Proposed by</th><th className="r">Total</th><th>Rules</th><th>Outcome</th><th>Record</th></tr></thead>
                <tbody>
                  {rows.map((r) => {
                    const [label, tone] = OUTCOME[r.outcome] || [r.outcome, 'plain'];
                    return (
                      <tr key={r.purchase_session_id}>
                        <td className="nowrap">{when(r.at)}</td>
                        <td><b>{r.product_title}</b><div className="small muted">mandate <span className="mono">{shortId(r.mandate_id)}</span> v{r.mandate_version}</div></td>
                        <td>{r.proposed_by === 'agent' ? 'Assistant' : 'You'}</td>
                        <td className="r num nowrap">{money(r.total_minor, r.currency)}</td>
                        <td><DecisionBadge decision={r.decision} />{r.failed.length > 0 && <div className="small mono muted">{r.failed.join(', ')}{r.refused_at === 'PRE_CAPTURE' ? ' (at final check)' : ''}</div>}</td>
                        <td><span className={`badge ${tone}`}>{label}</span></td>
                        <td className="nowrap">{r.receipt_id ? <Link to={`/receipt/${r.receipt_id}`}>Receipt</Link> : r.checkout_id ? <Link to={`/checkout/${r.checkout_id}`}>Checkout</Link> : <span className="muted">none</span>}</td>
                      </tr>
                    );
                  })}
                  {rows.length === 0 && <tr><td colSpan="7" className="muted">No proposals match this filter.</td></tr>}
                </tbody>
              </table>
            </div>
            <p className="small muted">Showing your own activity in this browser, newest first{data.rows.length >= data.limit ? `, limited to ${data.limit}` : ''}.</p>
          </section>
        </>
      )}
    </div>
  );
}
