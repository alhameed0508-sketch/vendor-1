import { apiFetch } from '../auth/api';

const load = async url => {
  const body = await (await apiFetch(url)).json();
  return body?.data || body;
};

export const fetchCommandCenter = () => load('/api/v1/command-center');
export const fetchModules = () => load('/api/v1/modules').then(data => data.modules);
