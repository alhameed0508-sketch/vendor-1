/* Pure state for the live payment stream. No I/O, never mutates its input. */

export const MAX_EDGES = 120;
export const MAX_LATENCIES = 200;

export const initialState = {
  status: 'idle', // idle | live | ended | error
  events: 0,
  counters: { payments: 0, flagged: 0, mule_payments_flagged: 0, genuine_accounts_flagged: 0 },
  edges: [],
  rings: {},
  flaggedAccounts: [],
  latestCaseId: null,
  latencies: [],
  error: null,
};

export function p95(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))];
}

function applyEvent(state, event) {
  const { payment } = event;
  const isFlag = event.decision === 'FLAG' && event.case_id;
  const edge = { id: payment.txn_id, from: payment.from_account, to: payment.to_account, flagged: Boolean(isFlag) };
  const rings = isFlag
    ? {
        ...state.rings,
        [event.case_id]: {
          caseId: event.case_id,
          members: event.ring_members,
          reasons: event.reasons,
          risk: event.risk_score,
          openedAt: state.events + 1,
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
  };
}

export function streamReducer(state, action) {
  switch (action.type) {
    case 'open':
      return { ...initialState, status: 'live' };
    case 'event':
      return applyEvent(state, action.event);
    case 'closed':
      return state.events > 0
        ? { ...state, status: 'ended' }
        : { ...state, status: 'error', error: 'Stream unavailable. No payments received.' };
    default:
      return state;
  }
}
