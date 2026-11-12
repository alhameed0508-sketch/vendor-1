import React from 'react';
import { DECISION_TEXT, money, requirementText, sentence, shortId, when } from './api';

export const Spinner = ({ label }) => (
  <span className="row small muted" role="status"><span className="spin" aria-hidden="true" />{label}</span>
);

export function ErrorNote({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="notice err" role="alert">
      <div className="row between">
        <span>{error.message}</span>
        {onRetry && <button className="btn small" onClick={onRetry}>Try again</button>}
      </div>
      {Array.isArray(error.details) && error.details.length > 0 && (
        <ul className="small" style={{ margin: '6px 0 0', paddingLeft: 18 }}>
          {error.details.map((d, i) => <li key={i}><span className="mono">{d.field}</span>: {d.message}</li>)}
        </ul>
      )}
    </div>
  );
}

export const DecisionBadge = ({ decision }) => <span className={`badge ${decision}`}>{DECISION_TEXT[decision] || decision}</span>;

export function Price({ quote }) {
  const c = quote.currency;
  const items = quote.unit_amount_minor * (quote.quantity || 1);
  return (
    <div className="price num">
      <span>Item{quote.quantity > 1 ? ` × ${quote.quantity}` : ''}</span><span>{money(items, c)}</span>
      <span>Shipping</span><span>{money(quote.shipping_amount_minor, c)}</span>
      <span>Tax</span><span>{money(quote.tax_amount_minor, c)}</span>
      <span className="total">Total</span><span className="total">{money(quote.total_amount_minor ?? quote.total_for_one_minor, c)}</span>
    </div>
  );
}

export function MandateSummary({ view, compact }) {
  const m = view.mandate;
  const reqs = Object.entries(m.product.requirements || {});
  return (
    <dl className="dl">
      <dt>Product</dt>
      <dd>{m.product.quantity} × {m.product.condition} {m.product.category}{m.product.model ? ` (${m.product.model})` : ''}</dd>
      {reqs.length > 0 && (<><dt>Must have</dt><dd>{reqs.map(([k, v]) => requirementText(k, v)).join('; ')}</dd></>)}
      <dt>Budget</dt>
      <dd className="num">
        Up to {money(m.spending.maximum_total_minor, m.currency)}
        <span className="muted"> ({['items', m.spending.include_shipping && 'shipping', m.spending.include_tax && 'tax'].filter(Boolean).join(' + ')})</span>
      </dd>
      <dt>Seller</dt>
      <dd>{m.seller.mode === 'any' ? 'Any seller' : `Approved sellers only: ${m.seller.approved_seller_ids.join(', ')}`}</dd>
      <dt>Substitutes</dt>
      <dd>{m.substitution.allowed ? 'Allowed' : 'Not allowed without asking you again'}</dd>
      <dt>Expires</dt>
      <dd>{when(m.expires_at)}</dd>
      {!compact && (<>
        <dt>Version</dt><dd>v{view.version} · <span className={`badge ${view.status === 'CONFIRMED' ? 'ok' : view.status === 'DRAFT' ? 'warn' : 'bad'}`}>{sentence(view.status)}</span></dd>
        <dt>Fingerprint</dt><dd className="mono" title="SHA-256 of the mandate terms">{view.canonical_hash}</dd>
      </>)}
    </dl>
  );
}

export function Checks({ evaluation }) {
  if (!evaluation) return null;
  return (
    <div className="table-wrap">
      <table className="checks">
        <thead><tr><th>Rule</th><th>Result</th><th>Your mandate says</th><th>Found</th><th>Why</th></tr></thead>
        <tbody>
          {evaluation.checks.map((c) => (
            <tr key={c.rule_id}>
              <td className="mono">{c.rule_id}</td>
              <td><span className={`badge ${c.status}`}>{c.status === 'PASS' ? 'Pass' : c.status === 'FAIL' ? 'Fail' : 'Unknown'}</span></td>
              <td>{c.expected}</td>
              <td>{c.observed}</td>
              <td>{c.reason}<div className="mono muted">{c.source}</div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ACTIONS = {
  MANDATE_DRAFTED: 'Mandate drafted', MANDATE_DRAFT_EDITED: 'Draft edited', MANDATE_VERSION_PROPOSED: 'New mandate version proposed',
  MANDATE_CONFIRMED: 'Buyer confirmed the mandate', MANDATE_REVOKED: 'Buyer revoked the mandate', PRODUCT_PROPOSED: 'Product proposed',
  QUOTE_CREATED: 'Server quote created', POLICY_EVALUATED: 'Policy evaluated', CHECKOUT_CREATED: 'Checkout opened',
  ORDER_REFUSED: 'Order refused by policy', ORDER_BLOCKED: 'Order blocked', PAYPAL_ORDER_CREATED: 'PayPal order created by the server',
  ORDER_CREATE_REJECTED: 'PayPal rejected the order', PAYPAL_APPROVAL_CANCELLED: 'Buyer closed PayPal without approving',
  BUYER_APPROVED: 'Buyer approved in PayPal', FINAL_VERIFICATION_PASSED: 'Final verification passed', FINAL_VERIFICATION_UNAVAILABLE: 'Order could not be verified',
  CAPTURE_REFUSED: 'Capture refused', CAPTURE_REQUESTED: 'Capture requested', CAPTURED: 'PayPal captured the payment',
  CAPTURE_DENIED: 'PayPal denied the capture', CAPTURE_PENDING: 'Capture pending at PayPal', CAPTURE_OUTCOME_UNKNOWN: 'Capture outcome unknown',
  CAPTURE_RETRIED_AFTER_RECONCILIATION: 'Capture retried after checking with PayPal', RECONCILED_NO_CAPTURE: 'PayPal confirmed no capture',
  RECONCILIATION_UNAVAILABLE: 'PayPal could not be reached to reconcile', WEBHOOK_RECONCILED: 'Verified webhook reconciled', RECEIPT_CREATED: 'Receipt issued',
  UNEXPECTED_CAPTURE_REPORTED: 'PayPal reported a capture this service did not request', REFUNDED: 'Payment refunded',
  CAPTURE_PENDING_REPORTED: 'PayPal reported the capture as pending', ORDER_EXPIRED: 'PayPal order expired',
};
const BAD = /REFUSED|BLOCKED|DENIED|UNKNOWN|UNAVAILABLE|REJECTED|UNEXPECTED|REVOKED/;

function detail(t) {
  const d = t.data || {};
  if (d.decision) return `${d.stage ? d.stage.replace('_', '-').toLowerCase() + ': ' : ''}${d.decision}${d.failed && d.failed.length ? ` (${d.failed.join(', ')})` : ''}`;
  if (d.total_minor !== undefined && d.total_minor !== null) return money(d.total_minor, d.currency);
  if (d.capture_id) return `capture ${d.capture_id}${d.result ? ` · ${d.result}` : ''}`;
  if (d.order_id) return `order ${d.order_id}`;
  if (d.product_id) return d.product_id;
  if (d.hash) return `v${d.version} · ${shortId(d.hash)}…`;
  return '';
}

export function Timeline({ events }) {
  if (!events || !events.length) return <p className="muted small">No events yet.</p>;
  return (
    <ol className="tl">
      {events.map((t) => (
        <li key={t.seq} className={BAD.test(t.action) || (t.data && t.data.decision && t.data.decision !== 'ALLOW') ? 'bad' : ''}>
          <div><b>{ACTIONS[t.action] || t.action}</b> <span className="muted">{detail(t)}</span></div>
          <div className="muted small">{when(t.at)} · {t.actor_type} · <span className="mono" title="Audit chain hash">{shortId(t.hash)}</span></div>
        </li>
      ))}
    </ol>
  );
}

// Related record types share a column so the chain stays readable at page width.
const COLUMN_OF = { Buyer: 0, PurchaseMandate: 1, MandateVersion: 2, Proposal: 3, AgentSession: 3, Product: 4, PolicyEvaluation: 4, Checkout: 4,
  Merchant: 5, PayPalOrder: 5, PaymentCapture: 6, Webhook: 7 };
const colOf = (kind) => COLUMN_OF[kind] ?? 0;

// Keep the path that leads to one checkout, so a receipt shows its own provenance and not every proposal.
export function pathFor(graph, checkoutId) {
  const target = `Checkout:${checkoutId}`;
  const proposal = graph.edges.find((e) => e.to === target);
  if (!proposal) return graph;
  const keep = new Set();
  const up = (id) => { keep.add(id); graph.edges.filter((e) => e.to === id).forEach((e) => up(e.from)); };
  const down = (id) => { keep.add(id); graph.edges.filter((e) => e.from === id).forEach((e) => down(e.to)); };
  up(proposal.from);
  down(proposal.from);
  return { ...graph, nodes: graph.nodes.filter((n) => keep.has(n.id)), edges: graph.edges.filter((e) => keep.has(e.from) && keep.has(e.to)) };
}

export function Graph({ graph }) {
  const W = 132, H = 34, GX = 30, GY = 14;
  const cols = {};
  graph.nodes.forEach((n) => { (cols[colOf(n.kind)] ||= []).push(n); });
  const used = Object.keys(cols).map(Number).sort((a, b) => a - b);
  const pos = {};
  used.forEach((c, i) => cols[c].forEach((n, j) => { pos[n.id] = { x: 8 + i * (W + GX), y: 8 + j * (H + GY) }; }));
  const rows = Math.max(...used.map((c) => cols[c].length), 1);
  const width = 16 + used.length * W + (used.length - 1) * GX;
  const height = 16 + rows * H + (rows - 1) * GY;
  const clip = (s) => (s.length > 21 ? `${s.slice(0, 20)}…` : s);
  return (
    <div className="table-wrap">
      <svg className="graph" viewBox={`0 0 ${width} ${height}`} style={{ minWidth: Math.min(width, 900) }} role="img"
        aria-label="Purchase provenance: how the buyer's mandate links to the product, policy checks, PayPal order and capture">
        {graph.edges.map((e, i) => {
          const a = pos[e.from], b = pos[e.to];
          if (!a || !b) return null;
          const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, mx = (x1 + x2) / 2;
          return (
            <g key={i}>
              <path d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} />
              <title>{e.relationship.replace(/_/g, ' ').toLowerCase()}</title>
            </g>
          );
        })}
        {graph.nodes.map((n) => (
          <g key={n.id}>
            <title>{`${n.kind}: ${n.label}`}</title>
            <rect className={`k-${n.kind}`} x={pos[n.id].x} y={pos[n.id].y} width={W} height={H} rx="7" />
            <text x={pos[n.id].x + 9} y={pos[n.id].y + 21}>{clip(n.label)}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
