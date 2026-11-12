import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, money, sentence, shortId, WEBHOOK_TEXT, WEBHOOK_TONE, when } from './api';
import { outcomeOf } from './ledgerParts';
import { ErrorNote, Spinner } from './parts';

function useList(fetcher, key) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => { setError(null); fetcher().then((d) => setRows(d[key])).catch(setError); }, [fetcher, key]);
  useEffect(load, [load]);
  return [rows, error, load];
}

function Frame({ intro, error, rows, load, empty, children }) {
  return (
    <div className="stack">
      <div className="page-head"><p className="lede" style={{ margin: 0 }}>{intro}</p></div>
      {error ? <ErrorNote error={error} onRetry={load} /> : !rows ? <Spinner label="Loading" /> : rows.length === 0 ? <div className="panel empty">{empty}</div> : (
        <section className="panel"><div className="table-wrap">{children}</div></section>
      )}
    </div>
  );
}

const STATUS_TONE = { CONFIRMED: 'ok', DRAFT: 'warn', REVOKED: 'bad', EXPIRED: 'plain' };

export function Mandates() {
  const [rows, error, load] = useList(api.mandates, 'mandates');
  return (
    <Frame intro="The purchase terms you set and locked. Each confirmed version is fingerprinted and can never be edited; a change makes a new version." error={error} rows={rows} load={load}
      empty={<><h2>No mandates yet</h2><p>A mandate is what an assistant may buy for you: product, must-haves, budget, seller and expiry.</p><div style={{ marginTop: 14 }}><Link className="btn primary" to="/new">Set up a purchase</Link></div></>}>
      <table className="ledger">
        <thead><tr><th>Mandate</th><th>Request</th><th>Product</th><th className="r">Budget</th><th>Status</th><th className="r">Proposals</th><th>Expires</th><th /></tr></thead>
        <tbody>{rows && rows.map((m) => (
          <tr key={m.mandate_id}>
            <td className="ref"><Link to={`/mandates/${m.mandate_id}`}>{shortId(m.mandate_id)}</Link> <span className="muted">v{m.version}</span></td>
            <td style={{ maxWidth: 320 }}>{m.request ? `“${m.request}”` : <span className="muted">entered by hand</span>}<div className="small muted">{m.source === 'ai' ? 'drafted by AI, confirmed by you' : 'entered by hand'}</div></td>
            <td>{m.quantity} × {m.condition} {m.category}</td>
            <td className="amt">{money(m.budget_minor, m.currency)}</td>
            <td><span className={`badge ${STATUS_TONE[m.status] || 'plain'}`}>{sentence(m.status)}</span></td>
            <td className="r num">{m.proposals}{m.paid ? <span className="small muted"> · {m.paid} paid</span> : ''}</td>
            <td className="nowrap small">{when(m.expires_at)}</td>
            <td className="nowrap">{m.status === 'CONFIRMED' ? <Link className="btn small" to={`/mandates/${m.mandate_id}`}>Choose a product</Link> : <Link className="btn small" to={`/new?m=${m.mandate_id}`}>Review</Link>}</td>
          </tr>
        ))}</tbody>
      </table>
    </Frame>
  );
}

const WEBHOOK = Object.fromEntries(Object.keys(WEBHOOK_TEXT).map((k) => [k, [WEBHOOK_TEXT[k], WEBHOOK_TONE[k]]]));

export function Checkouts() {
  const [rows, error, load] = useList(api.checkouts, 'checkouts');
  return (
    <Frame intro="Your checkouts with PayPal. A capture happens only after the approved order is fetched again and passes every rule." error={error} rows={rows} load={load}
      empty={<><h2>No checkouts yet</h2><p>A checkout opens when a product passes every rule and you continue to PayPal.</p></>}>
      <table className="ledger">
        <thead><tr><th>Checkout</th><th>Item</th><th className="r">Total</th><th>State</th><th>PayPal order</th><th>Capture</th><th>Webhook</th><th>Updated</th></tr></thead>
        <tbody>{rows && rows.map((c) => {
          const [label, tone] = outcomeOf(c.state, c.paypal_order_id ? 'PRE_CAPTURE' : null);
          const [wl, wt] = WEBHOOK[c.reconciliation] || [c.reconciliation, 'plain'];
          return (
            <tr key={c.checkout_id}>
              <td className="ref"><Link to={`/checkout/${c.checkout_id}`}>{shortId(c.checkout_id)}</Link></td>
              <td><b>{c.product_title}</b>{c.reason && <div className="small muted" style={{ maxWidth: 340 }}>{c.reason}</div>}</td>
              <td className="amt">{money(c.total_minor, c.currency)}</td>
              <td><span className={`badge ${tone}`}>{label}</span></td>
              <td className="ref">{c.paypal_order_id || '—'}</td>
              <td className="ref">{c.capture_id ? (c.receipt_id ? <Link to={`/receipt/${c.receipt_id}`}>{c.capture_id}</Link> : c.capture_id) : '—'}</td>
              <td>{c.capture_id ? <span className={`badge ${wt}`}>{wl}</span> : <span className="muted small">n/a</span>}</td>
              <td className="nowrap small">{when(c.updated_at)}</td>
            </tr>
          );
        })}</tbody>
      </table>
    </Frame>
  );
}

export function Receipts() {
  const [rows, error, load] = useList(api.receipts, 'receipts');
  const [copied, setCopied] = useState(null);
  const copy = (r) => {
    const url = window.location.origin + r.share_path;
    const done = () => { setCopied(r.receipt_id); setTimeout(() => setCopied(null), 2500); };
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, () => window.prompt('Copy this link', url)); else window.prompt('Copy this link', url);
  };
  return (
    <Frame intro="Signed receipts for captured payments. Each links the instruction, the locked mandate, every rule check and the PayPal capture." error={error} rows={rows} load={load}
      empty={<><h2>No receipts yet</h2><p>A receipt is issued when PayPal captures a payment that passed the final check.</p></>}>
      <table className="ledger">
        <thead><tr><th>Receipt</th><th>Item</th><th className="r">Captured</th><th>PayPal capture</th><th>Webhook</th><th>Fingerprint</th><th>Issued</th><th /></tr></thead>
        <tbody>{rows && rows.map((r) => {
          const [wl, wt] = WEBHOOK[r.reconciliation] || [r.reconciliation, 'plain'];
          return (
            <tr key={r.receipt_id}>
              <td className="ref"><Link to={`/receipt/${r.receipt_id}`}>{shortId(r.receipt_id)}</Link></td>
              <td><b>{r.product_title}</b>{r.state === 'REFUNDED' && <div className="small muted">refunded</div>}</td>
              <td className="amt cap">{money(r.amount_minor, r.currency)}</td>
              <td className="ref">{r.capture_id}</td>
              <td><span className={`badge ${wt}`}>{wl}</span></td>
              <td className="ref" title={r.receipt_hash}>{r.receipt_hash.slice(0, 12)}…</td>
              <td className="nowrap small">{when(r.issued_at)}</td>
              <td><button className="btn small" onClick={() => copy(r)}>{copied === r.receipt_id ? 'Link copied' : 'Copy share link'}</button></td>
            </tr>
          );
        })}</tbody>
      </table>
    </Frame>
  );
}
