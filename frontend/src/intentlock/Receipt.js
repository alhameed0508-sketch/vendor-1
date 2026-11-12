import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, money, requirementText, shortId, when } from './api';
import { ErrorNote, Graph, Price, Spinner, Timeline, pathFor } from './parts';

export default function Receipt() {
  const { receiptId, token } = useParams(); // `token` is set on a shared, read-only link
  const [r, setR] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => (token ? api.publicReceipt(token) : api.receipt(receiptId)).then((v) => {
    setR(v);
    if (v.graph) return setGraph(pathFor(v.graph, v.receipt.checkout_id)); // a shared receipt carries its own graph
    return api.graph(v.receipt.mandate.mandate_id).then((g) => setGraph(pathFor(g, v.receipt.checkout_id)));
  }).catch(setError), [receiptId, token]);

  const copyLink = () => {
    const url = window.location.origin + r.share_path;
    const done = () => { setCopied(true); setTimeout(() => setCopied(false), 2500); };
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, () => window.prompt('Copy this link', url));
    else window.prompt('Copy this link', url);
  };
  useEffect(() => { load(); }, [load]);

  // The webhook arrives after the capture, so keep checking for a while.
  const pending = r && r.reconciliation.status === 'PENDING';
  useEffect(() => {
    if (!pending) return undefined;
    let tries = 0;
    const t = setInterval(() => { tries += 1; if (tries > 24) clearInterval(t); else load(); }, 5000);
    return () => clearInterval(t);
  }, [pending, load]);

  if (error && !r) return <ErrorNote error={error} onRetry={load} />;
  if (!r) return <Spinner label="Loading the receipt" />;
  const rc = r.receipt;
  const terms = rc.mandate.terms;
  const rec = r.reconciliation;
  const intact = r.integrity.hash_matches && r.integrity.signature_matches;

  return (
    <div className="stack">
      {r.shared && <div className="notice info">Shared receipt, read-only. It shows a real PayPal Sandbox purchase. Contact details are left out.</div>}
      <div>
        <h2 className="h-large">{r.checkout_state === 'REFUNDED' ? 'Purchase refunded' : 'Purchase complete, and it matches what you asked for'}</h2>
        <p className="small muted">Receipt <span className="mono">{shortId(r.receipt_id)}</span></p>
        <p className="lede">This receipt links your instruction, the mandate you confirmed, the rule checks and the PayPal payment. Every value comes from stored records.</p>
      </div>

      <div className="split even">
        <section className="card stack" aria-labelledby="asked">
          <h2 id="asked">What you authorised</h2>
          {rc.original_request && <p>“{rc.original_request}”</p>}
          <dl className="dl">
            <dt>Mandate</dt><dd>v{rc.mandate.version}, confirmed {when(rc.mandate.confirmed_at)} <span className="muted">({rc.mandate.source === 'ai' ? 'drafted by AI, confirmed by you' : 'entered by hand'})</span></dd>
            <dt>Fingerprint</dt><dd className="mono">{rc.mandate.canonical_hash}</dd>
            <dt>Product</dt><dd>{terms.product.quantity} × {terms.product.condition} {terms.product.category}</dd>
            {Object.keys(terms.product.requirements).length > 0 && (<><dt>Must have</dt><dd>{Object.entries(terms.product.requirements).map(([k, v]) => requirementText(k, v)).join('; ')}</dd></>)}
            <dt>Budget</dt><dd className="num">up to {money(terms.spending.maximum_total_minor, terms.currency)}</dd>
            <dt>Seller</dt><dd>{terms.seller.mode === 'any' ? 'any seller' : terms.seller.approved_seller_ids.join(', ')}</dd>
          </dl>
        </section>

        <section className="card stack" aria-labelledby="bought">
          <h2 id="bought">What was bought</h2>
          <div><b>{rc.product.title}</b><p className="small muted">{rc.product.condition} · sold by {rc.product.seller_name} ({rc.product.seller_id}){rc.product.synthetic ? ' · synthetic demo product' : ''}</p></div>
          <Price quote={rc.quote} />
          <dl className="dl">
            <dt>PayPal order</dt><dd className="mono">{rc.payment.order_id}</dd>
            <dt>PayPal capture</dt><dd><span className="mono">{rc.payment.capture_id}</span> <span className={`badge ${rc.payment.status === 'COMPLETED' ? 'ok' : 'warn'}`}>{rc.payment.status}</span></dd>
            <dt>Captured</dt><dd className="num">{money(rc.payment.amount_minor, rc.payment.currency)}</dd>
            <dt>Paid to</dt><dd className="mono">{(rc.payment.payee && (rc.payment.payee.merchant_id || rc.payment.payee.email)) || 'not recorded'}</dd>
          </dl>
        </section>
      </div>

      <div className="split even">
        <section className="card stack" aria-labelledby="checks">
          <h2 id="checks">Rule checks</h2>
          {rc.policy.map((p) => (
            <div key={p.evaluation_id} className="row between" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
              <span>{p.stage === 'PRE_CAPTURE' ? 'Final verification against the PayPal order' : 'Before the order was created'}
                <span className="muted small"> · {p.checks.length} checks · <span className="mono">{shortId(p.evaluation_id)}</span></span></span>
              <span className={`badge ${p.decision}`}>{p.decision}</span>
            </div>
          ))}
          <p className="small muted">Policy version <span className="mono">{rc.policy[0] && rc.policy[0].policy_version}</span>. Rules are fixed code. The AI did not make these decisions.</p>
        </section>

        <section className="card stack" aria-labelledby="proof">
          <h2 id="proof">Verification</h2>
          <div className="row between">
            <span>PayPal webhook</span>
            <span className={`badge ${rec.status === 'VERIFIED' ? 'ok' : rec.status === 'MISMATCH' ? 'bad' : 'plain'}`}>
              {rec.status === 'VERIFIED' ? 'Signature verified and amounts match' : rec.status === 'MISMATCH' ? 'Does not match our record' : 'Waiting for PayPal'}
            </span>
          </div>
          {rec.webhook_events.map((e) => <p key={e.event_id} className="small muted"><span className="mono">{e.event_id}</span> · {e.type} · {e.processing.toLowerCase()} · {when(e.received_at)}</p>)}
          {rec.status === 'PENDING' && <p className="small muted">PayPal sends the confirmation separately. This page checks again every few seconds; the capture above is already confirmed by PayPal's own response.</p>}
          <div className="row between"><span>Receipt integrity</span><span className={`badge ${intact ? 'ok' : 'bad'}`}>{intact ? 'Unchanged since issue' : 'Has been altered'}</span></div>
          <dl className="dl small">
            <dt>Receipt hash</dt><dd className="mono">{r.receipt_hash}</dd>
            <dt>Signature</dt><dd className="mono">{r.signature.slice(0, 32)}… <span className="muted">({r.signing_key_id})</span></dd>
          </dl>
          <p className="small muted">The hash is a tamper-evident fingerprint of this receipt. It is not a legal signature or proof of identity.</p>
        </section>
      </div>

      <section className="card stack" aria-labelledby="prov">
        <h2 id="prov">How this purchase traces back to your instruction</h2>
        {graph ? <Graph graph={graph} /> : <Spinner label="Building the provenance graph" />}
        <p className="small muted">Built from the database records. It organises evidence; it is not proof of anything beyond those records.</p>
      </section>

      <section className="card stack" aria-labelledby="audit"><h2 id="audit">Audit trail</h2><Timeline events={r.timeline} /></section>
      <div className="row">
        <Link className="btn primary" to={r.shared ? '/' : '/new'}>{r.shared ? 'Try IntentLock yourself' : 'Start another purchase'}</Link>
        {!r.shared && <Link className="btn" to={`/checkout/${rc.checkout_id}`}>Back to the checkout</Link>}
        {r.share_path && <button className="btn" onClick={copyLink}>{copied ? 'Link copied' : 'Copy a share link'}</button>}
        {r.share_path && <span className="small muted">Anyone with the link can view this receipt, read-only.</span>}
      </div>
    </div>
  );
}
