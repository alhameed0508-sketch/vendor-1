import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AlertDetail from './AlertDetail';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn(), resolveUrl: u => u, getToken: () => null }));
jest.mock('../graph_viz/NetworkGraph', () => () => null);
jest.mock('../graph_viz/TimelineSlider', () => () => null);
jest.mock('../explainability/ExplainabilityPanel', () => () => null);
jest.mock('../genai/InvestigationChat', () => () => null);
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('lucide-react', () => ({ ArrowLeft: () => null, Check: () => null }));

const ALERT = { alert_id: 'ALT-1', status: 'UNDER_REVIEW', severity: 'CRITICAL', risk_score: 0.99,
  confidence: 1, gnn_score: 0.87, account_count: 9, txn_count: 42, total_amount: 17900000,
  nodes: [], edges: [], reason_codes: [], shared_devices: [], shared_ips: [] };

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockImplementation(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ data: ALERT }) }));
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/alert/ALT-1']}>
      <Routes><Route path="/alert/:alertId" element={<AlertDetail />} /></Routes>
    </MemoryRouter>,
  );
}

it('shows the alert figures as labelled values, not a dotted run-on line', async () => {
  renderPage();
  const figures = (await screen.findByText('Risk', { selector: 'dt' })).closest('dl');
  const value = label => within(figures).getByText(label).nextSibling.textContent;
  expect(value('Risk')).toBe('99%');
  expect(value('Confidence')).toBe('100%');
  expect(value('Model score')).toBe('87%');
  expect(value('Accounts')).toBe('9');
  expect(value('Transfers')).toBe('42');
  expect(value('Amount')).toBe('₹1.79Cr');
  expect(figures.textContent).not.toMatch('·');
});

it('names severity and status in sentence case', async () => {
  renderPage();
  expect(await screen.findByText('Critical')).toBeInTheDocument();
  expect(screen.getByText('Under review', { selector: '.badge' })).toBeInTheDocument();
});
