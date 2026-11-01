import { apiFetch } from '../auth/api';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function send(url, method, payload, what) {
  const r = await apiFetch(url, { method, headers: JSON_HEADERS, body: JSON.stringify(payload) });
  if (!r.ok) throw new Error(`${what} failed (HTTP ${r.status})`);
  return r;
}

export function updateAlertStatus(alertId, status, notes) {
  const payload = notes ? { status, investigator_notes: notes } : { status };
  return send(`/api/v1/alerts/${alertId}`, 'PATCH', payload, 'Status update');
}

export async function fileStr(alert, reason) {
  await send('/api/v1/compliance/str-export', 'POST', { alert_ids: [alert.alert_id] }, 'STR export');
  await updateAlertStatus(alert.alert_id, 'STR_FILED', reason);
}
