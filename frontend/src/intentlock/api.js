// API client and small formatting helpers. The browser never sends amounts, payees or policy results.

export class ApiError extends Error {
  constructor(status, error) {
    super((error && error.message) || 'The request failed');
    this.status = status;
    this.code = (error && error.code) || 'REQUEST_FAILED';
    this.details = error && error.details;
  }
}

async function call(method, path, body) {
  let res;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-IntentLock-Client': 'web' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, { code: 'NETWORK', message: 'The server could not be reached. Check your connection and try again.' });
  }
  let json = null;
  try { json = await res.json(); } catch (e) { /* not JSON */ }
  if (!res.ok || !json || json.success === false) {
    throw new ApiError(res.status, (json && json.error) || { message: `The server answered ${res.status}` });
  }
  return json.data;
}

export const api = {
  config: () => call('GET', '/config'),
  parse: (request) => call('POST', '/intents/parse', { request }),
  saveIntent: (original_request, source, mandate) => call('POST', '/intents', { original_request, source, mandate }),
  changeIntent: (id, mandate) => call('PUT', `/intents/${id}`, { mandate }),
  confirmIntent: (id, canonical_hash) => call('POST', `/intents/${id}/confirm`, { canonical_hash }),
  intent: (id) => call('GET', `/intents/${id}`),
  search: (mandate_id) => call('POST', '/catalog/search', { mandate_id }),
  evaluate: (mandate_id, product_id) => call('POST', '/purchases/evaluate', { mandate_id, product_id }),
  agentPropose: (mandate_id) => call('POST', '/agent/propose', { mandate_id }),
  createCheckout: (purchase_session_id) => call('POST', '/checkout', { purchase_session_id }),
  checkout: (id) => call('GET', `/checkout/${id}`),
  paypalOrder: (id) => call('POST', `/checkout/${id}/paypal-order`),
  finalize: (id) => call('POST', `/checkout/${id}/finalize`),
  cancel: (id) => call('POST', `/checkout/${id}/cancel`),
  tamper: (id) => call('POST', `/demo/tamper/${id}`),
  receipt: (id) => call('GET', `/receipts/${id}`),
  graph: (mandateId) => call('GET', `/graph/${mandateId}`),
  explain: (checkout_id) => call('POST', '/assistant/explain', { checkout_id }),
};

const EXPONENT = { USD: 2, EUR: 2, GBP: 2, JPY: 0 };

export function money(minor, currency = 'USD') {
  if (minor === null || minor === undefined) return 'not stated';
  const exp = EXPONENT[currency] ?? 2;
  const s = String(Math.abs(minor)).padStart(exp + 1, '0');
  const whole = s.slice(0, s.length - exp).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${currency} ${minor < 0 ? '-' : ''}${whole}${exp ? '.' + s.slice(-exp) : ''}`;
}

// "1,000.5" -> 100050, without floating point. Returns null when the text is not an amount.
export function toMinor(text, currency = 'USD') {
  const exp = EXPONENT[currency] ?? 2;
  const m = String(text).replace(/[,\s]/g, '').match(/^(\d+)(?:\.(\d+))?$/);
  if (!m) return null;
  const frac = m[2] || '';
  if (frac.length > exp) return null;
  return Number(m[1] + frac.padEnd(exp, '0'));
}

export function fromMinor(minor, currency = 'USD') {
  if (minor === null || minor === undefined) return '';
  const exp = EXPONENT[currency] ?? 2;
  const s = String(minor).padStart(exp + 1, '0');
  return exp ? `${s.slice(0, -exp)}.${s.slice(-exp)}` : s;
}

export const shortId = (id) => (id ? String(id).slice(0, 8) : '');
export const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '');

export const DECISION_TEXT = {
  ALLOW: 'Within your mandate',
  BLOCK: 'Outside your mandate',
  REAUTHORISE: 'Needs your approval',
  REVIEW: 'Cannot be verified',
};

const LABELS = { ram_gb: 'Memory', storage_gb: 'Storage', screen_in_tenths: 'Screen', battery_hours: 'Battery', noise_cancelling: 'Noise cancelling' };

export function humanise(key) {
  const base = String(key).replace(/_(min|max)$/, '');
  if (LABELS[base]) return LABELS[base];
  const words = base.replace(/_in_tenths$/, '').replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function attrValue(key, value) {
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (/_in_tenths/.test(key)) return `${(value / 10).toFixed(1)} in`;
  if (/_gb/.test(key)) return `${value} GB`;
  if (/_hours/.test(key)) return `${value} h`;
  return String(value);
}

export function requirementText(key, value) {
  const base = humanise(key);
  const shown = attrValue(key, value);
  if (key.endsWith('_min')) return `${base}: at least ${shown}`;
  if (key.endsWith('_max')) return `${base}: at most ${shown}`;
  return `${base}: ${shown}`;
}

// ── additions: shared receipts, agent runs, activity ────────────────────────
api.publicReceipt = (token) => call('GET', `/public/receipts/${token}`);
api.agentRun = (mandate_id, mode) => call('POST', '/agent/run', { mandate_id, mode });
api.activity = () => call('GET', '/activity');

// Requirements a buyer can pick in plain words. `key` is what the rule engine stores.
export const SPECS = [
  { key: 'ram_gb_min', label: 'Memory', phrase: 'at least', unit: 'GB', kind: 'number' },
  { key: 'storage_gb_min', label: 'Storage', phrase: 'at least', unit: 'GB', kind: 'number' },
  { key: 'screen_in_tenths_min', label: 'Screen size', phrase: 'at least', unit: 'inches', kind: 'tenths' },
  { key: 'screen_in_tenths_max', label: 'Screen size', phrase: 'at most', unit: 'inches', kind: 'tenths' },
  { key: 'battery_hours_min', label: 'Battery life', phrase: 'at least', unit: 'hours', kind: 'number' },
  { key: 'noise_cancelling', label: 'Noise cancelling', phrase: 'required', unit: '', kind: 'flag' },
];
const specOf = (key) => SPECS.find((s) => s.key === key);

// Stored requirement -> form row.
export function requirementRow(name, stored) {
  const spec = specOf(name);
  if (!spec) return { key: 'custom', name, value: String(stored) };
  if (spec.kind === 'tenths') return { key: name, name: '', value: String(stored / 10) };
  if (spec.kind === 'flag') return { key: name, name: '', value: 'true' };
  return { key: name, name: '', value: String(stored) };
}

// Form row -> [name, value] for the mandate, or { error }. An empty custom row returns null.
export function requirementEntry(row) {
  const spec = specOf(row.key);
  const raw = String(row.value || '').trim();
  if (!spec) {
    const name = String(row.name || '').trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    if (!name && !raw) return null;
    if (!name || !raw) return { error: 'Each custom requirement needs a name and a value.' };
    return [name, /^\d+$/.test(raw) ? Number(raw) : /^(true|yes)$/i.test(raw) ? true : /^(false|no)$/i.test(raw) ? false : raw];
  }
  if (spec.kind === 'flag') return [spec.key, true];
  if (spec.kind === 'tenths') {
    if (!/^\d+(\.\d)?$/.test(raw)) return { error: `${spec.label} must be a size in inches, such as 14 or 13.3.` };
    return [spec.key, Math.round(parseFloat(raw) * 10)];
  }
  if (!/^\d+$/.test(raw)) return { error: `${spec.label} must be a whole number of ${spec.unit}.` };
  return [spec.key, Number(raw)];
}
