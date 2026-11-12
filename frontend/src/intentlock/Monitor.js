import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, money, shortId } from './api';
import { useConfig } from './IntentLockApp';
import { Guide } from './scenarios';
import { Checks, DecisionBadge, ErrorNote, Price, Spinner, Timeline } from './parts';

const STEPS = ['Mandate confirmed', 'Product and server quote', 'Policy check passed', 'PayPal order created by the server',
  'You approve in PayPal', 'Order re-fetched and verified', 'Payment captured', 'Receipt issued'];
const REACHED = {
  POLICY_ALLOWED: 3, PAYPAL_ORDER_CREATED: 4, PAYPAL_APPROVAL_CANCELLED: 4, BUYER_APPROVED: 5, FINAL_POLICY_REVALIDATION: 5,
  CAPTURE_REQUESTED: 6, RECONCILIATION_REQUIRED: 6, CAPTURED: 7, RECEIPT_CREATED: 8, REFUNDED: 8,
};
const REFUSED = ['BLOCKED', 'REAUTHORISATION_REQUIRED', 'REVIEW_REQUIRED', 'EXPIRED'];
const HEADLINE = {
  POLICY_ALLOWED: ['Preparing your PayPal order', 'info'],
  PAYPAL_ORDER_CREATED: ['Ready for you to approve in PayPal', 'info'],
  PAYPAL_APPROVAL_CANCELLED: ['You closed PayPal without approving', 'warn'],
  BUYER_APPROVED: ['Approved in PayPal. Verifying the order', 'info'],
  FINAL_POLICY_REVALIDATION: ['Verifying the order', 'info'],
  CAPTURE_REQUESTED: ['Capture requested. Waiting for PayPal', 'info'],
  RECONCILIATION_REQUIRED: ['Checking the payment with PayPal', 'warn'],
  CAPTURED: ['Payment captured', 'ok'],
  RECEIPT_CREATED: ['Payment captured and receipt issued', 'ok'],
  REFUNDED: ['Payment refunded', 'warn'],
  BLOCKED: ['Not captured: the purchase is outside your mandate', 'bad'],
  REAUTHORISATION_REQUIRED: ['Not captured: the order no longer matches what you approved', 'warn'],
  REVIEW_REQUIRED: ['Not captured: the order could not be verified', 'info'],
  EXPIRED: ['Not captured: the PayPal order expired', 'warn'],
  CAPTURE_DENIED: ['PayPal did not complete the payment', 'bad'],
};
const PAYABLE = ['PAYPAL_ORDER_CREATED', 'PAYPAL_APPROVAL_CANCELLED', 'BUYER_APPROVED'];

let sdkPromise = null;
function loadPayPal(clientId, currency) {
  if (window.paypal) return Promise.resolve(window.paypal);
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=${currency}&intent=capture&components=buttons&disable-funding=card,credit,paylater,venmo`;
      s.onload = () => (window.paypal ? resolve(window.paypal) : reject(new Error('PayPal did not load')));
      s.onerror = () => { sdkPromise = null; reject(new Error('PayPal could not be loaded. Check your connection or ad blocker.')); };
      document.head.appendChild(s);
    });
  }
  return sdkPromise;
}

export default function Monitor() {
  const { checkoutId } = useParams();
  const config = useConfig();
  const [co, setCo] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState('');
  const [explain, setExplain] = useState(null);
  const box = useRef(null);
  const rendered = useRef(null);

  const act = useCallback(async (key, fn) => {
    setBusy(key); setError(null);
    try { const v = await fn(); if (v && v.checkout_id) setCo(v); return v; } catch (e) { setError(e); return null; } finally { setBusy(''); }
  }, []);

  useEffect(() => {
    let live = true;
    api.checkout(checkoutId)
      .then((v) => { if (!live) return; setCo(v); if (v.state === 'POLICY_ALLOWED') act('order', () => api.paypalOrder(checkoutId)); })
      .catch((e) => live && setError(e));
    return () => { live = false; };
  }, [checkoutId, act]);

  const payable = co && PAYABLE.includes(co.state) && co.paypal_order_id;
  useEffect(() => {
    if (!payable || !box.current || rendered.current === co.paypal_order_id) return undefined;
    let buttons = null;
    let cancelled = false;
    loadPayPal(config.paypal_client_id, config.currency).then((paypal) => {
      if (cancelled || !box.current) return;
      rendered.current = co.paypal_order_id;
      box.current.innerHTML = '';
      buttons = paypal.Buttons({
        style: { layout: 'horizontal', tagline: false, height: 44 },
        createOrder: () => co.paypal_order_id, // created by the server from the stored quote
        onApprove: () => act('finalize', () => api.finalize(checkoutId)), // the server re-fetches the order; this call carries no amounts
        onCancel: () => act('cancel', () => api.cancel(checkoutId)),
        onError: () => setError({ message: 'PayPal reported a problem. Nothing was captured. You can try again.' }),
      });
      buttons.render(box.current).catch(() => {});
    }).catch((e) => setError({ message: e.message }));
    return () => { cancelled = true; };
  }, [payable, co, config, checkoutId, act]);

  if (error && !co) return <ErrorNote error={error} />;
  if (!co) return <Spinner label="Loading the checkout" />;

  const [headline, tone] = HEADLINE[co.state] || [co.state, 'info'];
  const refused = REFUSED.includes(co.state) || co.state === 'CAPTURE_DENIED';
  const preCapture = co.evaluations.find((e) => e.stage === 'PRE_CAPTURE');
  const latest = co.evaluations[co.evaluations.length - 1];
  const stopAt = co.state === 'CAPTURE_DENIED' ? 6 : preCapture ? 5 : 3;
  const reached = refused ? stopAt : REACHED[co.state] ?? 0;
  const q = co.quote;

  return (
    <div className="stack">
      <Guide page="monitor" />
      <div>
        <h2 className="h-large">{headline}</h2>
        <p className="small muted">Checkout <span className="mono">{shortId(co.checkout_id)}</span></p>
        <p className="lede">
          {refused ? 'No money was taken. The reason and the rule that failed are below.'
            : 'The amount and payee come from the server\'s stored quote. After you approve, the server fetches the order from PayPal again and captures only if it still matches your mandate.'}
        </p>
      </div>
      {co.reason && <div className={`notice ${tone === 'bad' ? 'err' : tone === 'ok' ? 'ok' : 'info'}`} role="status">{co.reason}</div>}
      <ErrorNote error={error} />

      <div className="split wide-right">
        <aside className="card flat stack">
          <h2>Progress</h2>
          <ol className="progress">
            {STEPS.map((s, i) => {
              const cls = refused && i === stopAt ? 'stop' : i < reached ? 'done' : i === reached && !refused ? 'now' : '';
              return <li key={s} className={cls}><i aria-hidden="true">{cls === 'done' ? '✓' : cls === 'stop' ? '✕' : i + 1}</i><span>{s}{cls === 'stop' ? ': refused' : ''}</span></li>;
            })}
          </ol>
          <dl className="dl small">
            <dt>Mandate</dt><dd>v{co.mandate.version} · <span className="mono">{shortId(co.mandate.canonical_hash)}…</span></dd>
            <dt>PayPal order</dt><dd className="mono">{co.paypal_order_id || 'not created'}</dd>
            <dt>Capture</dt><dd className="mono">{co.payment ? `${co.payment.capture_id} (${co.payment.status})` : 'none'}</dd>
            <dt>Webhook</dt><dd><span className={`badge ${co.reconciliation_status === 'VERIFIED' ? 'ok' : co.reconciliation_status === 'MISMATCH' ? 'bad' : 'plain'}`}>{co.reconciliation_status.toLowerCase()}</span></dd>
          </dl>
        </aside>

        <div className="stack">
          <section className="card stack" aria-labelledby="buying">
            <div className="row between"><h2 id="buying">{co.product.title}</h2>{latest && <DecisionBadge decision={latest.decision} />}</div>
            <p className="small muted">{co.product.condition} · sold by {co.product.seller_name} · quote {shortId(q.quote_id)} · server-calculated</p>
            <div className="split even">
              <Price quote={q} />
              <div className="stack-s">
                {co.state === 'POLICY_ALLOWED' && (busy === 'order' ? <Spinner label="Creating the PayPal order on the server" />
                  : <button className="btn primary" onClick={() => act('order', () => api.paypalOrder(checkoutId))}>Create the PayPal order</button>)}
                {payable && (<>
                  <p className="small">Pay <b className="num">{money(q.total_amount_minor, q.currency)}</b> with your PayPal Sandbox buyer account.</p>
                  <div className="paypal-box" ref={box}><Spinner label="Loading PayPal" /></div>
                  {busy === 'finalize' && <Spinner label="Verifying the approved order with PayPal" />}
                  <button className="btn small quiet" disabled={!!busy} onClick={() => act('finalize', () => api.finalize(checkoutId))}>I approved in PayPal. Check now</button>
                  {config.demo_tools && (
                    <button className="btn small" disabled={!!busy} title="Demo tool"
                      onClick={() => act('tamper', () => api.tamper(checkoutId)).then((v) => v && setError({ message: `${v.note} Approve in PayPal and watch the capture be refused.` }))}>
                      Demo: change the PayPal order behind the checkout
                    </button>
                  )}
                </>)}
                {['CAPTURE_REQUESTED', 'RECONCILIATION_REQUIRED'].includes(co.state) && (
                  <button className="btn primary" disabled={!!busy} onClick={() => act('finalize', () => api.finalize(checkoutId))}>
                    {busy === 'finalize' ? <Spinner label="Asking PayPal what happened" /> : 'Check the payment with PayPal'}
                  </button>
                )}
                {co.receipt_id && <Link className="btn primary" to={`/receipt/${co.receipt_id}`}>View the purchase receipt</Link>}
                {refused && <Link className="btn" to={`/mandates/${co.mandate.mandate_id}`}>Choose another product</Link>}
                {co.state === 'REAUTHORISATION_REQUIRED' && <Link className="btn" to={`/new?m=${co.mandate.mandate_id}`}>Change the mandate</Link>}
              </div>
            </div>
          </section>

          {co.evaluations.map((e) => (
            <section className="card stack" key={e.evaluation_id}>
              <div className="row between">
                <h2>{e.stage === 'PRE_CAPTURE' ? 'Final verification against the PayPal order' : 'Policy check before the order'}</h2>
                <DecisionBadge decision={e.decision} />
              </div>
              <p className="small muted">Evaluation <span className="mono">{shortId(e.evaluation_id)}</span> · {e.policy_version} · decided by fixed rules, not by the AI</p>
              <details open={e.decision !== 'ALLOW'}>
                <summary className="small" style={{ cursor: 'pointer', fontWeight: 600 }}>{e.checks.length} checks{e.failed_constraints.length ? `, ${e.failed_constraints.length} not passed` : ', all passed'}</summary>
                <Checks evaluation={e} />
              </details>
            </section>
          ))}

          <section className="card stack">
            <div className="row between">
              <h2>Explain this in plain words</h2>
              <button className="btn small" disabled={!!busy || !config.ai_enabled} onClick={async () => { const v = await act('explain', () => api.explain(checkoutId)); if (v) setExplain(v); }}>
                {busy === 'explain' ? <Spinner label="Writing" /> : 'Ask the assistant'}
              </button>
            </div>
            {explain ? (<><p>{explain.explanation}</p><p className="small muted">Based on stored records: {explain.evidence_ids.map((id) => <span key={id} className="mono"> {id.split(':')[0]}:{shortId(id.split(':')[1])}</span>)} · {explain.model}</p></>)
              : <p className="small muted">{config.ai_enabled ? 'The assistant reads the stored records only. It cannot change the result.' : 'The AI assistant is not configured on this instance.'}</p>}
          </section>

          <section className="card stack"><h2>Audit trail</h2><Timeline events={co.timeline} /></section>
        </div>
      </div>
    </div>
  );
}
