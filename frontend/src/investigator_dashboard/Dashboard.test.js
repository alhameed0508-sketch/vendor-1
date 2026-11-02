import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('sonner', () => ({ toast: { error: jest.fn() } }));

const alert = (id, total_amount) => ({
  alert_id: id, severity: 'CRITICAL', status: 'OPEN', risk_score: 0.9, total_amount,
  account_count: 3, created_at: '2026-11-01T10:00:00Z',
});

beforeEach(() => {
  apiFetch.mockResolvedValue({
    json: () => Promise.resolve({ data: { alerts: [alert('A1', 10000000), alert('A2', 7900000)] } }),
  });
});

it('shows the flagged total in the shared rupee format', async () => {
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  expect(await screen.findByText('₹1.79Cr')).toBeInTheDocument();
  expect(screen.getByText('₹1.79Cr flagged')).toBeInTheDocument();
});
