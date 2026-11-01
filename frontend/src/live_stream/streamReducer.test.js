import { streamReducer, initialState, p95, MAX_EDGES, MAX_RING_PAYMENTS } from './streamReducer';

const event = (n, over = {}) => ({
  payment: { txn_id: `T${n}`, from_account: `A${n}`, to_account: `B${n}`, amount: 1000 },
  decision: 'PASS',
  case_id: null,
  ring_members: [],
  reasons: [],
  risk_score: 0.1,
  latency_ms: 20 + n,
  counters: { payments: n, flagged: 0, genuine_accounts_flagged: 0, mule_payments_flagged: 0 },
  ...over,
});

const flagEvent = (n) =>
  event(n, {
    decision: 'FLAG',
    case_id: 'CASE-1',
    ring_members: ['A1', 'B1', 'C1'],
    reasons: ['CC01: dense ring'],
    risk_score: 0.9,
    counters: { payments: n, flagged: 1, genuine_accounts_flagged: 0, mule_payments_flagged: 1 },
  });

describe('streamReducer', () => {
  it('starts idle and goes live on open', () => {
    expect(initialState.status).toBe('idle');
    expect(streamReducer(initialState, { type: 'open' }).status).toBe('live');
  });

  it('records edges, counters and latencies without mutating state', () => {
    const live = streamReducer(initialState, { type: 'open' });
    const frozen = JSON.stringify(live);
    const next = streamReducer(live, { type: 'event', event: event(1) });
    expect(JSON.stringify(live)).toBe(frozen);
    expect(next.edges).toHaveLength(1);
    expect(next.counters.payments).toBe(1);
    expect(next.latencies).toEqual([21]);
  });

  it('opens a case on FLAG and keeps the ring', () => {
    const live = streamReducer(initialState, { type: 'open' });
    const next = streamReducer(live, { type: 'event', event: flagEvent(2) });
    expect(next.latestCaseId).toBe('CASE-1');
    expect(next.rings['CASE-1'].members).toEqual(['A1', 'B1', 'C1']);
    expect(next.rings['CASE-1'].reasons).toContain('CC01: dense ring');
    expect(next.flaggedAccounts).toEqual(['A1', 'B1', 'C1']);
  });

  it('caps stored edges', () => {
    let state = streamReducer(initialState, { type: 'open' });
    for (let i = 1; i <= MAX_EDGES + 20; i += 1) {
      state = streamReducer(state, { type: 'event', event: event(i) });
    }
    expect(state.edges).toHaveLength(MAX_EDGES);
  });

  it('marks error when no events arrived and ended when some did', () => {
    const live = streamReducer(initialState, { type: 'open' });
    expect(streamReducer(live, { type: 'closed' }).status).toBe('error');
    const withEvent = streamReducer(live, { type: 'event', event: event(1) });
    expect(streamReducer(withEvent, { type: 'closed' }).status).toBe('ended');
  });
});

describe('stopped', () => {
  it('ends a live stream and leaves other states alone', () => {
    const live = streamReducer(initialState, { type: 'open' });
    expect(streamReducer(live, { type: 'stopped' }).status).toBe('ended');
    expect(streamReducer(initialState, { type: 'stopped' }).status).toBe('idle');
  });
});

describe('p95', () => {
  it('returns null for no data and the 95th percentile otherwise', () => {
    expect(p95([])).toBeNull();
    const values = Array.from({ length: 100 }, (_, i) => i + 1);
    expect(p95(values)).toBe(96);
  });
});

describe('ring payment history', () => {
  it('keeps flagged payments per case, keeps the first openedAt, and caps the list', () => {
    let state = streamReducer(initialState, { type: 'open' });
    for (let i = 1; i <= MAX_RING_PAYMENTS + 5; i += 1) {
      state = streamReducer(state, { type: 'event', event: flagEvent(i) });
    }
    const ring = state.rings['CASE-1'];
    expect(ring.openedAt).toBe(1);
    expect(ring.payments).toHaveLength(MAX_RING_PAYMENTS);
    expect(ring.payments[ring.payments.length - 1]).toMatchObject({ id: `T${MAX_RING_PAYMENTS + 5}`, amount: 1000 });
  });
});
