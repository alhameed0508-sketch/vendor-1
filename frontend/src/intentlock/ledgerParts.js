import React from 'react';
import { Link } from 'react-router-dom';
import { codeBreaks, ledgerAmount, when } from './api';

const DAY = { year: undefined, month: 'short', day: 'numeric' };
const short = (iso) => new Date(iso).toLocaleDateString(undefined, DAY);
const time = (iso) => new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

export const OUTCOME = {
  RECEIPT_CREATED: ['Paid', 'ok'], CAPTURED: ['Paid', 'ok'], REFUNDED: ['Refunded', 'warn'],
  BLOCKED: ['Refused', 'bad'], REAUTHORISATION_REQUIRED: ['Needs approval', 'warn'], REVIEW_REQUIRED: ['Unverified', 'info'],
  POLICY_ALLOWED: ['Allowed', 'plain'], PRODUCT_SELECTED: ['Selected', 'plain'], PAYPAL_ORDER_CREATED: ['Awaiting PayPal', 'plain'],
  PAYPAL_APPROVAL_CANCELLED: ['PayPal cancelled', 'plain'], BUYER_APPROVED: ['Approved', 'plain'], FINAL_POLICY_REVALIDATION: ['Final check', 'plain'],
  CAPTURE_REQUESTED: ['Capturing', 'plain'], RECONCILIATION_REQUIRED: ['Checking PayPal', 'warn'], CAPTURE_DENIED: ['Declined', 'bad'], EXPIRED: ['Expired', 'plain'],
};
const STOPPED = new Set(['BLOCKED', 'REAUTHORISATION_REQUIRED', 'REVIEW_REQUIRED']);
// A refusal after the buyer approved in PayPal reads the same everywhere: refused at the final check.
export const outcomeOf = (state, refusedAt) => (refusedAt === 'PRE_CAPTURE' && STOPPED.has(state) ? ['Refused at final check', 'bad'] : OUTCOME[state] || [state, 'plain']);

// One ledger line per proposal. Refusals post in red with the rule codes as the memo.
export function LedgerRows({ rows, showDate = true }) {
  return rows.map((r) => {
    const stopped = r.decision !== 'ALLOW';
    const [label, tone] = outcomeOf(r.outcome, r.refused_at);
    const link = r.receipt_id ? `/receipt/${r.receipt_id}` : r.checkout_id ? `/checkout/${r.checkout_id}` : r.mandate_id ? `/mandates/${r.mandate_id}` : null;
    return (
      <tr key={r.ref}>
        <td className="ref c-ref">{link ? <Link to={link}>{r.ref}</Link> : r.ref}</td>
        <td className="nowrap c-when" title={when(r.at)}>{showDate ? `${short(r.at)}, ` : ''}{time(r.at)}</td>
        <td className="c-item"><b>{r.product_title}</b><div className="small muted">{r.seller_name}</div></td>
        <td className="c-by">{r.proposed_by === 'agent' ? 'AI assistant' : 'Buyer'}</td>
        <td className="c-memo">{stopped ? <span className="memo">{codeBreaks(r.failed.join(', ') || r.decision)}{r.refused_at === 'PRE_CAPTURE' ? ' · final check' : ''}</span> : <span className="muted small">{r.captured ? `captured${r.verified ? ', webhook verified' : ''}` : 'all rules passed'}</span>}</td>
        <td className={`amt c-amt ${stopped ? 'neg' : r.captured ? 'cap' : ''}`}>{ledgerAmount(r.total_minor, r.currency, stopped)}</td>
        <td className="c-out"><span className={`badge ${tone}`}>{label}</span>{r.mine && <span className="small muted"> · yours</span>}</td>
      </tr>
    );
  });
}

export const LEDGER_HEAD = (
  <tr><th>Ref</th><th>When</th><th>Item</th><th>Proposed by</th><th>Memo</th><th className="r">Amount</th><th>Outcome</th></tr>
);
