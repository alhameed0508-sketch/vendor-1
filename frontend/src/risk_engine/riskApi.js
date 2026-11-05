import { apiFetch } from '../auth/api';

export const RISK_BASE = '/api/v1/risk';

// Who may do what (mirrors backend/api/v1/routes/risk.py). The server enforces it; the UI only hides
// controls a role cannot use, so nothing on screen is a dead button.
export const FEEDBACK_ROLES = ['ADMIN', 'SUPERVISOR', 'INVESTIGATOR'];

export const ENGINE_ORDER = ['mule_network', 'session_device', 'beneficiary_intent', 'behaviour'];
export const ENGINE_META = {
  mule_network: { label: 'Mule network', prefix: 'MN', core: true,
    blurb: 'The existing mule-detection core: rings, smurf evidence and the open alert queue.' },
  session_device: { label: 'Session & device trust', prefix: 'SD',
    blurb: 'Device history and sharing, takeover sequences, remote access, Tor and hijacked networks.' },
  beneficiary_intent: { label: 'Payment intent & payee', prefix: 'BI',
    blurb: 'Known-fraud and mule-linked payees, coached payments, scam notes, sanctions.' },
  behaviour: { label: 'Behaviour & false-positive control', prefix: 'BH',
    blurb: "The customer's own baseline. Familiar payees, phones and hours calm the other engines." },
};

export const BAND_META = {
  APPROVE: { label: 'Approve', color: 'var(--accent)' },
  STEP_UP: { label: 'Step-up', color: 'var(--medium)' },
  REVIEW: { label: 'Review', color: 'var(--critical)' },
  DECLINE: { label: 'Decline', color: 'var(--critical)' },
};

export const SOURCE_META = {
  synthetic: { label: 'Synthetic', title: 'Simulated customers and fraud journeys' },
  scenario: { label: 'Scenario', title: 'Worked scenario replayed on an isolated engine (synthetic)' },
  live: { label: 'Real public payment', title: 'A real public payment (mempool.space)' },
  api: { label: 'What-if', title: 'Scored by staff, not committed' },
  ingest: { label: 'Ingested', title: 'Committed through the trusted ingest API' },
};

export async function readResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok || body?.success === false) {
    const message = body?.error?.message || body?.detail || `Request failed (${response.status})`;
    throw new Error(typeof message === 'string' ? message : 'Request failed');
  }
  return body?.data ?? body;
}

export const getJson = (path) => apiFetch(`${RISK_BASE}${path}`).then(readResponse);

export const postJson = (path, payload) =>
  apiFetch(`${RISK_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  }).then(readResponse);

export function formatInr(amount) {
  if (!Number.isFinite(amount)) return '—';
  return `₹${Math.round(amount).toLocaleString('en-IN')}`;
}

export function formatPct(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function engineReasons(reasons, engine) {
  return (reasons || []).filter((r) => r.engine === engine && r.kind !== 'familiarity');
}
