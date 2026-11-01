import React from 'react';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import AlertQueue from './AlertQueue';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn(), resolveUrl: u => u, getToken: () => null }));
jest.mock('../hooks/useAlertStream', () => () => ({ connected: false }));

const A1 = { alert_id: 'ALT-1', status: 'UNDER_REVIEW', severity: 'HIGH', risk_score: 0.9 };
const res = (ok, body = {}) => Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) });

function mockApi({ patchOk = true } = {}) {
  apiFetch.mockImplementation((url, init = {}) => {
    if (url.startsWith('/api/v1/alerts?')) return res(true, { data: { alerts: [A1] } });
    if (url.startsWith('/api/v1/compliance/str-export')) return res(true);
    if (init.method === 'PATCH') return res(patchOk);
    return res(true);
  });
}

const col = name => screen.getByRole('region', { name });

async function startFiling() {
  render(<MemoryRouter><AlertQueue /></MemoryRouter>);
  await screen.findByText('ALT-1');
  await userEvent.selectOptions(screen.getByLabelText('Move to'), 'STR_FILED');
  await userEvent.type(await screen.findByLabelText(/reason for filing/i), 'layering');
  await userEvent.click(screen.getByRole('button', { name: /confirm filing/i }));
}

beforeEach(() => {
  window.localStorage.setItem('mulecatch-queue-view', 'board');
  apiFetch.mockReset();
});

it('files an STR: export then PATCH, card lands in STR Filed', async () => {
  mockApi();
  await startFiling();
  await waitFor(() => expect(within(col('STR Filed')).getByText('ALT-1')).toBeInTheDocument());
  const writes = apiFetch.mock.calls.filter(([, i]) => i && i.method).map(([u, i]) => `${i.method} ${u}`);
  expect(writes).toEqual(['POST /api/v1/compliance/str-export', 'PATCH /api/v1/alerts/ALT-1']);
});

it('keeps the card in place and shows an error when the PATCH fails', async () => {
  mockApi({ patchOk: false });
  await startFiling();
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(within(col('Under Review')).getByText('ALT-1')).toBeInTheDocument();
});

it('cancelling the dialog sends no write requests', async () => {
  mockApi();
  render(<MemoryRouter><AlertQueue /></MemoryRouter>);
  await screen.findByText('ALT-1');
  await userEvent.selectOptions(screen.getByLabelText('Move to'), 'STR_FILED');
  await userEvent.keyboard('{Escape}');
  expect(apiFetch.mock.calls.some(([, i]) => i && i.method)).toBe(false);
  expect(within(col('Under Review')).getByText('ALT-1')).toBeInTheDocument();
});
