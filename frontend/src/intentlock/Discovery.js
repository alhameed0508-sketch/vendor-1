import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, attrValue, humanise, money } from './api';
import { useConfig } from './IntentLockApp';
import { Checks, DecisionBadge, ErrorNote, MandateSummary, Price, Spinner } from './parts';

function compare(requirements, attributes) {
  return Object.entries(requirements || {}).map(([key, wanted]) => {
    const attr = key.replace(/_(min|max)$/, '');
    const got = attributes[attr];
    let ok = null;
    if (got !== undefined && got !== null) {
      if (key.endsWith('_min')) ok = got >= wanted;
      else if (key.endsWith('_max')) ok = got <= wanted;
      else ok = String(got).toLowerCase() === String(wanted).toLowerCase();
    }
    return { key, label: humanise(key), shown: got === undefined || got === null ? 'not stated' : attrValue(key, got), ok };
  });
}

// Products inside the mandate come first, then the ones that need a decision, then the ones outside it.
const ORDER = { ALLOW: 0, REAUTHORISE: 1, REVIEW: 2, BLOCK: 3 };
const rank = (p) => (p.policy_preview ? ORDER[p.policy_preview.decision] : 0);

const WHAT_NEXT = {
  BLOCK: 'This product breaks a limit you set, so no PayPal order is created for it.',
  REAUTHORISE: 'This differs from what you approved. To buy it, change your mandate and confirm the new version.',
  REVIEW: 'Something needed to check this product is missing or out of date, so it is not allowed. Nothing is assumed.',
};

export default function Discovery() {
  const { mandateId } = useParams();
  const config = useConfig();
  const navigate = useNavigate();
  const [mandate, setMandate] = useState(null);
  const [products, setProducts] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const panel = useRef(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([api.intent(mandateId), api.search(mandateId)])
      .then(([m, s]) => { setMandate(m); setProducts([...s.products].sort((a, b) => rank(a) - rank(b) || a.unit_amount_minor - b.unit_amount_minor)); })
      .catch(setError);
  }, [mandateId]);
  useEffect(load, [load]);
  useEffect(() => { if (result && panel.current) panel.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [result]);

  const run = async (key, fn) => {
    setBusy(key); setError(null);
    try { setResult(await fn()); } catch (e) { setError(e); } finally { setBusy(''); }
  };
  const toCheckout = async () => {
    setBusy('checkout'); setError(null);
    try { const co = await api.createCheckout(result.purchase_session_id); navigate(`/checkout/${co.checkout_id}`); } catch (e) { setError(e); setBusy(''); }
  };

  if (error && !mandate) return <ErrorNote error={error} onRetry={load} />;
  if (!mandate || !products) return <Spinner label="Loading your mandate and the catalogue" />;
  if (mandate.status !== 'CONFIRMED') {
    return (
      <div className="card stack">
        <h2>This mandate is {mandate.status.toLowerCase()}</h2>
        <p className="muted">Only a confirmed, unexpired mandate can be used to buy. <Link to={`/?m=${mandate.mandate_id}`}>Review and confirm it</Link>.</p>
      </div>
    );
  }
  const reqs = mandate.mandate.product.requirements;
  const decision = result && result.evaluation.decision;

  return (
    <div className="stack">
      <div>
        <p className="eyebrow">Step 2</p>
        <h1>Choose a product</h1>
        <p className="lede">Every product is checked against your confirmed mandate by fixed rules. The assistant can suggest one, but the rules decide whether it can be bought.</p>
      </div>
      <div className="split wide-right">
        <aside className="card flat stack" aria-labelledby="locked">
          <div className="row between"><h2 id="locked">Your mandate</h2><span className="badge ok">Locked · v{mandate.version}</span></div>
          <MandateSummary view={mandate} compact />
          <p className="mono muted" title="Mandate fingerprint (SHA-256)">{mandate.canonical_hash.slice(0, 24)}…</p>
          <Link className="btn small" to={`/?m=${mandate.mandate_id}`}>Change the mandate</Link>
          <hr style={{ border: 0, borderTop: '1px solid var(--line)', width: '100%' }} />
          <h3>Let the assistant choose</h3>
          <p className="small muted">The AI reads the catalogue and proposes one product. Catalogue text is treated as data, never as an instruction.</p>
          <button className="btn primary" disabled={!!busy || !config.ai_enabled} onClick={() => run('agent', () => api.agentPropose(mandate.mandate_id))}>
            {busy === 'agent' ? <Spinner label="The assistant is choosing" /> : 'Ask the assistant to propose'}
          </button>
          {!config.ai_enabled && <p className="small muted">The AI assistant is not configured on this instance. Choose a product yourself.</p>}
        </aside>

        <div className="stack">
          <ErrorNote error={error} />
          {result && (
            <section className="card stack" ref={panel} aria-live="polite" aria-labelledby="res">
              <div className="row between">
                <h2 id="res">{result.proposed_by === 'agent' ? 'The assistant proposed' : 'You selected'}: {result.quote.product.title}</h2>
                <DecisionBadge decision={decision} />
              </div>
              {result.agent && <p className="small"><b>Assistant's reason:</b> {result.agent.rationale} <span className="muted">({result.agent.model})</span></p>}
              {decision === 'ALLOW'
                ? <div className="notice ok">Every rule passes. You can pay with PayPal; the order is checked again after you approve it and before any money is captured.</div>
                : <div className={`notice ${decision === 'BLOCK' ? 'err' : 'info'}`}>{WHAT_NEXT[decision]}</div>}
              <div className="split even">
                <Price quote={result.quote} />
                <div className="row" style={{ alignSelf: 'end', justifyContent: 'flex-end' }}>
                  {decision === 'ALLOW' && <button className="btn primary" onClick={toCheckout} disabled={!!busy}>{busy === 'checkout' ? <Spinner label="Opening checkout" /> : 'Continue to PayPal'}</button>}
                  {decision === 'REAUTHORISE' && <Link className="btn" to={`/?m=${mandate.mandate_id}`}>Change the mandate</Link>}
                </div>
              </div>
              <details open={decision !== 'ALLOW'}>
                <summary className="small" style={{ cursor: 'pointer', fontWeight: 600 }}>Rule-by-rule result ({result.evaluation.checks.length} checks, {result.evaluation.policy_version})</summary>
                <Checks evaluation={result.evaluation} />
              </details>
            </section>
          )}

          {products.length === 0 ? (
            <div className="card"><h2>No products in this category</h2><p className="lede">The demo catalogue has no {mandate.mandate.product.category}. <Link to={`/?m=${mandate.mandate_id}`}>Change the mandate</Link> to try laptops or headphones.</p></div>
          ) : (
            <div className="grid">
              {products.map((p) => {
                const pre = p.policy_preview;
                const within = pre && pre.decision === 'ALLOW';
                return (
                  <article key={p.product_id} className={`card product ${within ? '' : 'out'}`}>
                    <div className="row between"><h3>{p.title}</h3>{pre && <DecisionBadge decision={pre.decision} />}</div>
                    <p className="small muted">{p.condition} · sold by {p.seller_name} ({p.seller_id}){p.merchant_checkout_eligible ? '' : ' · not payable through this store'}</p>
                    <ul className="attrs">
                      {compare(reqs, p.attributes).map((r) => (
                        <li key={r.key}>
                          <span className={`tick ${r.ok === null ? 'q' : r.ok ? 'y' : 'n'}`} aria-hidden="true">{r.ok === null ? '?' : r.ok ? '✓' : '✕'}</span>
                          <span>{r.label}: <b>{r.shown}</b><span className="sr"> {r.ok === null ? '(unknown)' : r.ok ? '(meets your requirement)' : '(does not meet your requirement)'}</span></span>
                        </li>
                      ))}
                    </ul>
                    <Price quote={{ ...p, quantity: mandate.mandate.product.quantity, total_amount_minor: p.total_for_one_minor === null ? null
                      : p.unit_amount_minor * mandate.mandate.product.quantity + p.shipping_amount_minor + p.tax_amount_minor * mandate.mandate.product.quantity }} />
                    {pre && pre.failed.length > 0 && <p className="small"><b>{pre.failed[0].rule_id}:</b> {pre.failed[0].reason}{pre.failed.length > 1 ? ` (+${pre.failed.length - 1} more)` : ''}</p>}
                    <div className="untrusted"><b>Seller's text · not trusted</b>{p.description}</div>
                    <button className={`btn ${within ? 'primary' : ''}`} disabled={!!busy} onClick={() => run(p.product_id, () => api.evaluate(mandate.mandate_id, p.product_id))}>
                      {busy === p.product_id ? <Spinner label="Checking" /> : within ? 'Select this product' : 'Check it against my mandate'}
                    </button>
                  </article>
                );
              })}
            </div>
          )}
          <p className="small muted">Prices, shipping and tax are synthetic demo values in {money(0, config.currency).split(' ')[0]}. Totals are calculated on the server.</p>
        </div>
      </div>
    </div>
  );
}
