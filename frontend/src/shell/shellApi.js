import { apiFetch } from '../auth/api';

const load = async url => {
  const body = await (await apiFetch(url)).json();
  return body?.data || body;
};

export const fetchCommandCenter = () => load('/api/v1/command-center');
export const fetchModules = () => load('/api/v1/modules').then(data => data.modules);
export const fetchEntity = id => load(`/api/v1/intelligence/entities/${encodeURIComponent(id)}`);

const send = async (url, body) => {
  const res = await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json?.error?.message || json?.detail || 'Request failed');
  return json?.data || json;
};

export const fetchInvestigations = () => load('/api/v1/investigations').then(data => data.investigations);
export const openInvestigation = (source, sourceId) => send('/api/v1/investigations', { source, source_id: sourceId });
export const moveInvestigation = (id, to, outcome) => send(`/api/v1/investigations/${id}/transition`, { to, outcome });
export const requestIntervention = (id, kind, accountId) =>
  send(`/api/v1/investigations/${id}/intervention`, { kind, account_id: accountId });

export const fetchModule = async id => {
  const res = await apiFetch(`/api/v1/modules/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error('Module not found');
  return (await res.json()).data;
};
