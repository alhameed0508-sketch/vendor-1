import React, { useEffect, useState } from 'react';
import { api, when } from './api';
import { useConfig } from './IntentLockApp';
import { ErrorNote, Spinner } from './parts';

const EVENTS = ['CHECKOUT.ORDER.APPROVED', 'PAYMENT.CAPTURE.COMPLETED', 'PAYMENT.CAPTURE.DENIED', 'PAYMENT.CAPTURE.PENDING', 'PAYMENT.CAPTURE.REFUNDED'];
const ENDPOINTS = [
  ['POST', '/api/v1/intents/parse', 'Draft a mandate from the buyer\'s words (AI)'],
  ['POST', '/api/v1/intents', 'Save a draft mandate'],
  ['POST', '/api/v1/intents/{id}/confirm', 'Buyer confirms; the version is locked and fingerprinted'],
  ['POST', '/api/v1/purchases/evaluate', 'Check a proposed product against the mandate'],
  ['POST', '/api/v1/agent/run', 'Let an assistant propose, with the rules\' refusals fed back'],
  ['POST', '/api/v1/checkout', 'Open a checkout for an allowed proposal'],
  ['POST', '/api/v1/checkout/{id}/paypal-order', 'Create the PayPal order from the stored quote'],
  ['POST', '/api/v1/checkout/{id}/finalize', 'Re-fetch the approved order, check it again, capture or refuse'],
  ['POST', '/api/v1/paypal/webhooks', 'Verified PayPal webhooks'],
  ['GET', '/api/v1/receipts/{id}', 'Signed receipt with its audit trail'],
  ['GET', '/api/v1/public/receipts/{token}', 'Read-only shared receipt'],
];

function Row({ name, state, tone, children }) {
  return (
    <tr>
      <td style={{ minWidth: 170 }}><b>{name}</b></td>
      <td><span className={`badge ${tone}`}>{state}</span></td>
      <td>{children}</td>
    </tr>
  );
}

export default function Integrations() {
  const config = useConfig();
  const [health, setHealth] = useState(null);
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    Promise.all([api.health(), api.overview(0)]).then(([h, o]) => { setHealth(h); setOverview(o); }).catch(setError);
  }, []);
  if (error) return <ErrorNote error={error} />;
  if (!health || !overview) return <Spinner label="Checking the connections" />;
  const hook = `${window.location.origin}/api/v1/paypal/webhooks`;
  const integ = overview.integrity;
  return (
    <div className="stack">
      <div className="page-head"><p className="lede" style={{ margin: 0 }}>What this instance is connected to, read live from the server. Secrets never leave the server.</p></div>
      <section className="panel">
        <div className="table-wrap">
          <table className="ledger">
            <thead><tr><th>Connection</th><th>Status</th><th>Details</th></tr></thead>
            <tbody>
              <Row name="PayPal REST" state={health.paypal_configured ? 'Connected' : 'Not configured'} tone={health.paypal_configured ? 'ok' : 'bad'}>
                {health.paypal_env === 'sandbox' ? 'Sandbox' : 'Live'} · Orders v2 create, show and capture, each with a stored <span className="mono">PayPal-Request-Id</span>. Buyer approval uses the PayPal JavaScript SDK.
                {config && <div className="small muted">Client ID <span className="mono">{config.paypal_client_id.slice(0, 10)}…</span> (public; the secret stays on the server)</div>}
              </Row>
              <Row name="PayPal webhooks" state={health.webhook_configured ? 'Verifying' : 'Not configured'} tone={health.webhook_configured ? 'ok' : 'warn'}>
                Signatures checked with PayPal before an event is stored; each event is applied once.
                <div className="small"><span className="muted">Endpoint</span> <span className="mono">{hook}</span></div>
                <div className="small"><span className="muted">Events</span> <span className="mono">{EVENTS.join(', ')}</span></div>
                <div className="small muted">{integ.webhooks_verified} verified so far{integ.last_webhook_at ? `, last ${when(integ.last_webhook_at)}` : ''}.</div>
              </Row>
              <Row name="AI model" state={health.ai_enabled ? 'On' : 'Off'} tone={health.ai_enabled ? 'ok' : 'plain'}>
                {config && config.ai_model ? <span className="mono">{config.ai_model}</span> : 'Not configured'} · drafts mandates, proposes products, explains records. It cannot confirm a mandate, set an amount or payee, overrule a rule, or call PayPal.
              </Row>
              <Row name="Database" state={health.database === 'ok' ? 'Connected' : 'Unavailable'} tone={health.database === 'ok' ? 'ok' : 'bad'}>
                {health.database_durable ? 'PostgreSQL, the source of truth.' : 'Temporary SQLite file: records are lost when the server restarts.'}
              </Row>
              <Row name="Audit chain" state={integ.audit_intact ? 'Intact' : 'Broken'} tone={integ.audit_intact ? 'ok' : 'bad'}>
                {integ.audit_events} append-only events; each carries the hash of the one before it. Recomputed on every load of this page.
              </Row>
              <Row name="Policy" state="Fixed rules" tone="ok"><span className="mono">{health.policy_version}</span> · deterministic, no model involved.</Row>
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel" aria-labelledby="api">
        <div className="panel-head"><h2 id="api">API for agent platforms</h2><span className="small">Same calls this console makes. JSON in and out.</span></div>
        <div className="table-wrap">
          <table className="ledger">
            <thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead>
            <tbody>{ENDPOINTS.map(([m, p, what]) => <tr key={p + m}><td className="ref">{m}</td><td className="mono">{p}</td><td>{what}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
