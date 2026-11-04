import { apiFetch } from '../auth/api';

const BASE = '/api/v1/returns';

async function readJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body?.success === false) {
    const error = body?.error || {};
    throw Object.assign(
      new Error((res.status === 422 && error.details) || error.message || `Request failed (${res.status})`),
      { status: res.status },
    );
  }
  return body?.data ?? body;
}

const post = (path, payload) => apiFetch(`${BASE}${path}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
}).then(readJson);

const claimPath = id => `/${encodeURIComponent(id)}`;

export const getOverview = () => apiFetch(`${BASE}/overview`).then(readJson);
export const listClaims = () => apiFetch(BASE).then(readJson);
export const getClaim = id => apiFetch(`${BASE}${claimPath(id)}`).then(readJson);
export const fileClaim = claim => post('', claim);
export const reviewClaim = (id, review) => post(`${claimPath(id)}/review`, review);

/** Save the bank package as a file: 'pdf' or 'json'. */
export async function downloadPackage(id, format) {
  const res = await apiFetch(`${BASE}${claimPath(id)}/${format === 'pdf' ? 'package.pdf' : 'package'}`);
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const blob = format === 'pdf'
    ? await res.blob()
    : new Blob([JSON.stringify((await res.json()).data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${id}_bank_package.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
