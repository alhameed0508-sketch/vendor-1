import { apiFetch } from '../auth/api';

const BASE = '/api/v1/complaints';

async function readJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body?.success === false) {
    const error = body?.error || {};
    // A 422 carries the useful text in details; other errors in message.
    throw new Error((res.status === 422 && error.details) || error.message || `Request failed (${res.status})`);
  }
  return body?.data ?? body;
}

const post = (path, payload) => apiFetch(`${BASE}${path}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
}).then(readJson);

const casePath = id => `/${encodeURIComponent(id)}`;

export const listComplaints = () => apiFetch(BASE).then(readJson);
export const getComplaint = id => apiFetch(`${BASE}${casePath(id)}`).then(readJson);
export const getNarrative = id => apiFetch(`${BASE}${casePath(id)}/narrative`).then(readJson);
export const addEvidence = (id, item) => post(`${casePath(id)}/evidence`, item);
export const recordDecision = (id, decision) => post(`${casePath(id)}/decision`, decision);

/** Save the evidence pack as a file: 'pdf' or 'json'. */
export async function downloadPack(id, format) {
  const res = await apiFetch(`${BASE}${casePath(id)}/${format === 'pdf' ? 'pack.pdf' : 'pack'}`);
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const blob = format === 'pdf'
    ? await res.blob()
    : new Blob([JSON.stringify((await res.json()).data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${id}_evidence_pack.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
