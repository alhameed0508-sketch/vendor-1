import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AlertDetail from './AlertDetail';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn(), resolveUrl: u => u, getToken: () => null }));
jest.mock('../graph_viz/NetworkGraph', () => () => <div data-testid="graph" />);
jest.mock('../graph_viz/TimelineSlider', () => () => null);
jest.mock('../explainability/ExplainabilityPanel', () => () => null);
jest.mock('../genai/InvestigationChat', () => () => null);
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('lucide-react', () => ({ ArrowLeft: () => null, Check: () => null }));

const ALERT = { alert_id: 'ALT-1', status: 'UNDER_REVIEW', severity: 'HIGH', risk_score: 0.9,
  confidence: 0.8, account_count: 3, txn_count: 5, nodes: [], edges: [],
  reason_codes: [], shared_devices: [], shared_ips: [] };
const res = (ok, body = {}) => Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) });

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/alert/ALT-1']}>
      <Routes><Route path="/alert/:alertId" element={<AlertDetail />} /></Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockImplementation((url, init = {}) => {
    if (init.method) return res(true);
    return res(true, { data: ALERT });
  });
});

it('offers STR_FILED as a status option', async () => {
  renderPage();
  const select = await screen.findByLabelText('Status');
  expect(Array.from(select.options).map(o => o.value)).toContain('STR_FILED');
});

it('saving STR_FILED opens the approval dialog instead of patching directly', async () => {
  renderPage();
  await userEvent.selectOptions(await screen.findByLabelText('Status'), 'STR_FILED');
  await userEvent.click(screen.getByRole('button', { name: /^save$/i }));
  expect(await screen.findByRole('dialog')).toBeInTheDocument();
  expect(apiFetch.mock.calls.some(([, i]) => i && i.method)).toBe(false);
});

it('confirming files the STR: export then PATCH', async () => {
  renderPage();
  await userEvent.selectOptions(await screen.findByLabelText('Status'), 'STR_FILED');
  await userEvent.click(screen.getByRole('button', { name: /^save$/i }));
  await userEvent.type(await screen.findByLabelText(/reason for filing/i), 'layering');
  await userEvent.click(screen.getByRole('button', { name: /confirm filing/i }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  const writes = apiFetch.mock.calls.filter(([, i]) => i && i.method).map(([u, i]) => `${i.method} ${u}`);
  expect(writes).toEqual(['POST /api/v1/compliance/str-export', 'PATCH /api/v1/alerts/ALT-1']);
});

it('a disposition status cannot be saved without a reason in Notes', async () => {
  renderPage();
  await userEvent.selectOptions(await screen.findByLabelText('Status'), 'NO_FURTHER_ACTION');
  await userEvent.click(screen.getByRole('button', { name: /^save$/i }));
  expect(apiFetch.mock.calls.some(([, i]) => i && i.method)).toBe(false);
  await userEvent.type(screen.getByLabelText('Notes'), 'payroll batch');
  await userEvent.click(screen.getByRole('button', { name: /^save$/i }));
  await waitFor(() => expect(apiFetch.mock.calls.some(([, i]) => i && i.method === 'PATCH')).toBe(true));
});
