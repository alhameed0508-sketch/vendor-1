import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RiskEnginePage from './RiskEnginePage';
import { riskStreamReducer, initialStreamState } from './useRiskStream';
import { formatInr, formatPct, readResponse } from './riskApi';
import { apiFetch } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('../auth/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const ok = (data) => ({ ok: true, status: 200, json: async () => ({ success: true, data }) });
const missing = () => ({ ok: false, status: 404, json: async () => ({ success: false, error: { message: 'not run' } }) });

const ENGINES = {
  mule_network: { label: 'Mule network (core)', score: 0.9, data_available: true, note: '', codes: ['MN02'] },
  session_device: { label: 'Session', score: 0, data_available: true, note: '', codes: [] },
  beneficiary_intent: { label: 'Payee', score: 0.88, data_available: true, note: '', codes: ['BI07'] },
  behaviour: { label: 'Behaviour', score: 0.1, data_available: true, note: '', codes: [] },
};

const FULL = {
  decision_id: 'd-1', txn_id: 't-1', customer_id: 'CUST1', beneficiary_id: 'MULE7', amount: 85000, score: 100,
  band: 'REVIEW', confidence: 1, source: 'synthetic', event_time: '2026-10-20T15:40:00+05:30',
  engines: { mule_network: 0.9 }, contributions: { 'Mule network': 3.6, Familiarity: -0.2 },
  reasons: [
    { code: 'MN02', text: 'The payee MULE7 is in mule ring R1 (6 accounts).', strength: 0.85, kind: 'decisive', engine: 'mule_network' },
    { code: 'BI07', text: 'The customer was on a call during the payment.', strength: 0.6, kind: 'strong', engine: 'beneficiary_intent' },
    { code: 'FC02', text: 'Known device and usual place.', strength: 0.25, kind: 'familiarity', engine: 'behaviour' },
  ],
  explanation: {
    summary: 'Held for review: mule ring payee during a call.', action: 'Hold for a human reviewer.',
    model: { version: 'prior-2026.11', probability: 0.99, raw_score: 99, intercept: -4, log_odds: {} },
    engines: ENGINES, familiarity: 0.25, confidence: 1, corroborating_engines: 2,
    false_positive_controls: [], personal_limit: 4000, context: {},
  },
  outcome: null,
};

const METRICS = {
  decisions: 10, bands: { APPROVE: 8, STEP_UP: 1, REVIEW: 1 }, engine_active: { mule_network: 3 },
  top_reasons: [['MN02', 3], ['BI07', 2], ['FC01', 5]], latency_ms: { p50: 0.1, p95: 0.2, samples: 10 },
  synthetic_labelled: { genuine_payments: 8, genuine_interrupted_rate: 0.125 }, demo_traffic: { state: 'streaming' },
};

const EVALUATION = {
  caveat: 'Synthetic, time-separated test days. Targets are design targets, not results.',
  generated_at: '2026-11-04T12:00:00+00:00', model_used: 'prior-2026.11', latency_decision_p95_ms_worst_seed: 0.3,
  targets: { review_precision: { target: 0.9, op: '>=', label: 'Precision of the REVIEW band' } },
  systems: {
    unified: { label: 'Unified engine (this work)', customer_payments: {
      recall_interrupt: { mean: 0.8 }, genuine_interrupt_rate: { mean: 0.004 }, genuine_review_rate: { mean: 0 },
      review_precision: { mean: 1 } } },
    static_rules: { label: 'Static rules', customer_payments: {
      recall_interrupt: { mean: 0.5 }, genuine_interrupt_rate: { mean: 0.03 }, genuine_review_rate: { mean: 0.01 },
      review_precision: { mean: 0.4 } } },
  },
};

const FEEDS = {
  threat_feeds: { enabled: true, feeds: [
    { name: 'tor_exit', label: 'Tor exit-node list (torproject.org)', fetched_at: 1, entries: 1200, age_hours: 2,
      origin: 'download', stale: false },
    { name: 'spamhaus_drop', label: 'Spamhaus DROP (hijacked networks)', fetched_at: null, entries: 0,
      error: 'URLError: offline', stale: true },
  ] },
  live_payments: { provider: 'mempool.space', used_by: 'live stream', enabled: true },
  sanctions: { provider: 'UN list', used_by: 'BI10', enabled: false },
  complaints: { provider: 'Complaints', used_by: 'BI01' },
  mule_alerts: { provider: 'Alert queue', used_by: 'MN03' },
};

const SCENARIOS = [{ name: 'app_scam_mule_payee', title: 'APP scam: ₹85,000 to a mule-ring account',
  story: 'A coached payment.', expected_band: 'REVIEW', expected_why: 'Held for review.' }];

function route(overrides = {}) {
  apiFetch.mockImplementation(async (url) => {
    if (url in overrides) return overrides[url]();
    if (url.endsWith('/metrics')) return ok(METRICS);
    if (url.includes('/decisions?')) return ok({ decisions: [{ ...FULL, explanation: undefined }] });
    if (url.endsWith('/decisions/d-1')) return ok(FULL);
    if (url.endsWith('/scenarios')) return ok({ scenarios: SCENARIOS });
    if (url.endsWith('/evaluation')) return ok(EVALUATION);
    if (url.endsWith('/feeds')) return ok(FEEDS);
    if (url.endsWith('/run')) return ok({ name: 'app_scam_mule_payee', matched_expectation: true, decisions: [FULL] });
    if (url.endsWith('/feedback')) return ok({ ...FULL, outcome: 'FALSE_ALERT', outcome_by: 'investigator' });
    throw new Error(`unexpected ${url}`);
  });
}

describe('RiskEnginePage', () => {
  beforeEach(() => {
    apiFetch.mockReset();
    useAuth.mockReturnValue({ user: { role: 'INVESTIGATOR' } });
  });

  test('shows the four engines with the mule core first', async () => {
    route();
    render(<RiskEnginePage />);
    const panels = await screen.findAllByRole('region', { name: /mule network|session|payment intent|behaviour/i });
    expect(panels[0]).toHaveAccessibleName('Mule network');
    expect(within(panels[0]).getByText('Core')).toBeInTheDocument();
    expect(await within(panels[0]).findByText('30.0%')).toBeInTheDocument();
  });

  test('lists decisions with their data source and explains one on click', async () => {
    route();
    const user = userEvent.setup();
    render(<RiskEnginePage />);
    expect(await screen.findByText('Synthetic')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /explain decision for CUST1 to MULE7/i }));
    const drawer = await screen.findByRole('dialog', { name: /decision explanation/i });
    expect(await within(drawer).findByText(/mule ring payee during a call/)).toBeInTheDocument();
    expect(within(drawer).getByText('Confirmed fact')).toBeInTheDocument();
    expect(within(drawer).getByText('What calmed the score')).toBeInTheDocument();
  });

  test('investigators can record feedback; guests never see the buttons', async () => {
    route();
    const user = userEvent.setup();
    const { unmount } = render(<RiskEnginePage />);
    await user.click(await screen.findByRole('button', { name: /explain decision/i }));
    await user.click(await screen.findByRole('button', { name: 'False alert' }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/v1/risk/decisions/d-1/feedback',
      expect.objectContaining({ method: 'POST' })));
    unmount();

    useAuth.mockReturnValue({ user: { role: 'GUEST' } });
    render(<RiskEnginePage />);
    await user.click(await screen.findByRole('button', { name: /explain decision/i }));
    await screen.findByRole('dialog');
    expect(screen.queryByRole('button', { name: 'False alert' })).not.toBeInTheDocument();
  });

  test('keeps targets apart from synthetic results', async () => {
    route();
    render(<RiskEnginePage />);
    const panel = await screen.findByRole('region', { name: 'Model performance' });
    expect(within(panel).getByText('Synthetic, time-separated test days')).toBeInTheDocument();
    expect(within(panel).getByText('Design targets (targets, not results)')).toBeInTheDocument();
    expect(within(panel).getByText('Unified engine (this work)')).toBeInTheDocument();
  });

  test('says when no evaluation has been run instead of inventing numbers', async () => {
    route({ '/api/v1/risk/evaluation': missing });
    render(<RiskEnginePage />);
    expect(await screen.findByText('No offline evaluation has been run on this build.')).toBeInTheDocument();
  });

  test('shows feed provenance including failures', async () => {
    route();
    render(<RiskEnginePage />);
    const panel = await screen.findByRole('region', { name: 'Data sources' });
    expect(within(panel).getByText(/1,200 entries, 2 h old/)).toBeInTheDocument();
    expect(within(panel).getByText(/not loaded: URLError: offline/)).toBeInTheDocument();
  });

  test('runs a scenario and reports whether it matched its intent', async () => {
    route();
    const user = userEvent.setup();
    render(<RiskEnginePage />);
    const panel = await screen.findByRole('region', { name: 'Scenarios' });
    await user.click(await within(panel).findByRole('button', { name: /run/i }));
    expect(await within(panel).findByText('As intended')).toBeInTheDocument();
  });
});

describe('risk stream reducer', () => {
  test('prepends decisions and keeps provenance', () => {
    const event = { source: 'live', decision: { decision_id: 'a', band: 'APPROVE' }, provenance: { url: 'u' } };
    const next = riskStreamReducer({ ...initialStreamState, status: 'connecting' }, { type: 'event', event });
    expect(next.status).toBe('streaming');
    expect(next.decisions[0]).toMatchObject({ decision_id: 'a', _source: 'live' });
    expect(next.provenance).toEqual({ url: 'u' });
  });

  test('a server error event stops the stream with its message', () => {
    const next = riskStreamReducer(initialStreamState, { type: 'event', event: { error: 'mempool.space unreachable' } });
    expect(next).toMatchObject({ status: 'failed', error: 'mempool.space unreachable' });
  });
});

describe('risk api helpers', () => {
  test('format money and shares, Indian style', () => {
    expect(formatInr(8000000)).toBe('₹80,00,000');
    expect(formatPct(0.0042, 2)).toBe('0.42%');
    expect(formatPct(null)).toBe('—');
  });

  test('readResponse surfaces the server message', async () => {
    await expect(readResponse({ ok: false, status: 409, json: async () => ({ error: { message: 'disabled' } }) }))
      .rejects.toThrow('disabled');
  });
});
