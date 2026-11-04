import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AlertQueue from './AlertQueue';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn(), resolveUrl: u => u, getToken: () => null }));
jest.mock('../hooks/useAlertStream', () => () => ({ connected: false }));

const A1 = {
  alert_id: 'ALT-1', status: 'UNDER_REVIEW', severity: 'CRITICAL', risk_score: 0.9,
  account_count: 20, txn_count: 40, investigation_complexity: 'HIGH',
};

beforeEach(() => {
  window.localStorage.setItem('mulecatch-queue-view', 'table');
  apiFetch.mockImplementation(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ data: { alerts: [A1] } }) }));
});

it('writes severity, status and effort in words on each queue row', async () => {
  render(<MemoryRouter><AlertQueue /></MemoryRouter>);
  const id = await screen.findByText('ALT-1');
  const row = id.closest('.queue-row');
  expect(row).toHaveTextContent('Critical');
  expect(row).toHaveTextContent('Under review');
  expect(row).toHaveTextContent('40 transfers');
  expect(row).toHaveTextContent('High effort');
  expect(row.textContent).not.toMatch(/CRITICAL|UNDER REVIEW|txns/);
});
