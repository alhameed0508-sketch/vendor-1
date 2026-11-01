/* Pure state for the live payment stream. No I/O, never mutates its input. */

export const MAX_EDGES = 120;
export const MAX_LATENCIES = 200;
export const MAX_RING_PAYMENTS = 30;
export const MAX_LOG = 40;
export const REVIEW_DECISIONS = ['confirmed', 'dismissed'];

export const initialState = {
  status: 'idle', // idle | live | ended | error
  events: 0,
  counters: { payments: 0, flagged: 0, mule_payments_flagged: 0, genuine_accounts_flagged: 0 },
  edges: [],
  rings: {},
  flaggedAccounts: [],
  latestCaseId: null,
  latencies: [],
  reviews: {},
  accountStats: {},
  log: [],
  error: null,
};

export function p95(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))];
}

const EMPTY_STATS = { inCount: 0, inAmount: 0, outCount: 0, outAmount: 0 };

function withFlow(stats, payment) {
  const amount = Number(payment.amount) || 0;
  const from = stats[payment.from_account] || EMPTY_STATS;
  const to = stats[payment.to_account] || EMPTY_STATS;
  const next = { ...stats, [payment.from_account]: { ...from, outCount: from.outCount + 1, outAmount: from.outAmount + amount } };
  const target = next[payment.to_account] || to;
  return { ...next, [payment.to_account]: { ...target, inCount: target.inCount + 1, inAmount: target.inAmount + amount } };
}

function applyEvent(state, event) {
  const { payment } = event;
  const isFlag = event.decision === 'FLAG' && event.case_id;
  const edge = { id: payment.txn_id, from: payment.from_account, to: payment.to_account, flagged: Boolean(isFlag) };
  const previous = isFlag ? state.rings[event.case_id] : null;
  const rings = isFlag
    ? {
        ...state.rings,
        [event.case_id]: {
          caseId: event.case_id,
          members: event.ring_members,
          reasons: event.reasons,
          risk: event.risk_score,
          openedAt: previous ? previous.openedAt : state.events + 1,
          payments: [
            ...(previous ? previous.payments : []),
            { id: payment.txn_id, from: payment.from_account, to: payment.to_account, amount: payment.amount, risk: event.risk_score },
          ].slice(-MAX_RING_PAYMENTS),
        },
      }
    : state.rings;
  return {
    ...state,
    status: 'live',
    events: state.events + 1,
    counters: { ...state.counters, ...event.counters },
    edges: [...state.edges, edge].slice(-MAX_EDGES),
    rings,
    flaggedAccounts: isFlag ? [...new Set([...state.flaggedAccounts, ...event.ring_members])] : state.flaggedAccounts,
    latestCaseId: isFlag ? event.case_id : state.latestCaseId,
    latencies: [...state.latencies, event.latency_ms].slice(-MAX_LATENCIES),
    accountStats: withFlow(state.accountStats, payment),
    log: [
      ...state.log,
      {
        seq: state.events + 1,
        txnId: payment.txn_id,
        from: payment.from_account,
        to: payment.to_account,
        amount: payment.amount,
        decision: event.decision,
        caseId: isFlag ? event.case_id : null,
        latencyMs: event.latency_ms,
      },
    ].slice(-MAX_LOG),
  };
}

export function streamReducer(state, action) {
  switch (action.type) {
    case 'open':
      return { ...initialState, status: 'live' };
    case 'event':
      return applyEvent(state, action.event);
    case 'review':
      return REVIEW_DECISIONS.includes(action.decision) && state.rings[action.caseId]
        ? { ...state, reviews: { ...state.reviews, [action.caseId]: action.decision } }
        : state;
    case 'stopped':
      return state.status === 'live' ? { ...state, status: 'ended' } : state;
    case 'closed':
      return state.events > 0
        ? { ...state, status: 'ended' }
        : { ...state, status: 'error', error: 'Stream unavailable. No payments received.' };
    default:
      return state;
  }
}
