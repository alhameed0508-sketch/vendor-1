import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import Dashboard from './Dashboard';
import { apiFetch } from '../auth/api';
import { toast } from 'sonner';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('sonner', () => ({ toast: { error: jest.fn() } }));

const alert = (id, total_amount, over = {}) => ({
  alert_id: id, severity: 'CRITICAL', status: 'OPEN', risk_score: 0.9, total_amount,
  account_count: 3, txn_count: 12, reason_codes: ['FAN_OUT: many payouts'], created_at: '2026-11-01T10:00:00Z', ...over,
});

const serve = alerts => apiFetch.mockResolvedValue({ json: () => Promise.resolve({ data: { alerts } }) });

beforeEach(() => {
  apiFetch.mockReset();
  serve([alert('A1', 10000000), alert('A2', 7900000, { severity: 'HIGH', risk_score: 0.7 })]);
});

const Where = () => <div data-testid="path">{useLocation().pathname}</div>;
const renderDashboard = () => render(
  <MemoryRouter>
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/alert/:id" element={<Where />} />
    </Routes>
  </MemoryRouter>,
);
const card = label => screen.getByText(label, { selector: '.meta-label' }).closest('.premium-card');
const group = name => within(screen.getByRole('group', { name }));

describe('Alert Queue header and cards', () => {
  it('shows the flagged total in the shared rupee format, in the header and on the card', async () => {
    renderDashboard();
    expect((await screen.findAllByText('₹1.79Cr')).length).toBe(2);
  });

  it('counts critical, high and open alerts', async () => {
    renderDashboard();
    await screen.findByText('A1');
    expect(within(card('Critical')).getByText('1')).toBeInTheDocument();
    expect(within(card('High Severity')).getByText('1')).toBeInTheDocument();
    expect(within(card('Open Cases')).getByText('2')).toBeInTheDocument();
  });

  it('asks the server for the configured number of alerts', async () => {
    renderDashboard();
    await screen.findByText('A1');
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/alerts?limit=100');
  });

  it('says so when alerts fail to load', async () => {
    apiFetch.mockRejectedValue(new Error('offline'));
    jest.spyOn(console, 'error').mockImplementation(() => {});
    renderDashboard();
    await screen.findByText('Alert Queue');
    await screen.findByText('System Operational: Queue Clear');
    expect(toast.error).toHaveBeenCalledWith('Failed to load alerts');
    console.error.mockRestore();
  });
});

describe('filters', () => {
  beforeEach(() => serve([
    alert('A1', 1000, { severity: 'CRITICAL' }),
    alert('A2', 1000, { severity: 'HIGH' }),
    alert('A3', 1000, { severity: 'HIGH', status: 'RESOLVED' }),
  ]));

  it('narrow the table by severity, then by status, and mark what is on', async () => {
    renderDashboard();
    await screen.findByText('A1');

    await userEvent.click(group('Severity').getByRole('button', { name: 'HIGH' }));
    expect(screen.queryByText('A1')).not.toBeInTheDocument();
    expect(screen.getByText('A2')).toBeInTheDocument();
    expect(group('Severity').getByRole('button', { name: 'HIGH' })).toHaveAttribute('aria-pressed', 'true');
    expect(group('Severity').getByRole('button', { name: 'ALL' })).toHaveAttribute('aria-pressed', 'false');

    await userEvent.click(group('Status').getByRole('button', { name: 'Resolved' }));
    expect(screen.queryByText('A2')).not.toBeInTheDocument();
    expect(screen.getByText('A3')).toBeInTheDocument();
  });

  it('offer every disposition status, not just three', async () => {
    serve([alert('A1', 1000), alert('A4', 1000, { status: 'NO_FURTHER_ACTION' })]);
    renderDashboard();
    await screen.findByText('A1');
    const names = group('Status').getAllByRole('button').map(b => b.textContent);
    expect(names).toEqual(['All', 'Open', 'Under review', 'Resolved', 'False positive',
      'No further action', 'Suspicion confirmed, escalated', 'STR filed']);

    await userEvent.click(group('Status').getByRole('button', { name: 'No further action' }));
    expect(screen.queryByText('A1')).not.toBeInTheDocument();
    expect(screen.getByText('A4')).toBeInTheDocument();
  });

  it('say so when they hide every alert', async () => {
    renderDashboard();
    await screen.findByText('A1');
    await userEvent.click(group('Severity').getByRole('button', { name: 'MEDIUM' }));
    expect(screen.getByText('No Alerts Match Current Criteria')).toBeInTheDocument();
  });
});

describe('the table', () => {
  it('shows the top signal in words and the full status label', async () => {
    serve([alert('A5', 1000, { status: 'SUSPICION_CONFIRMED_ESCALATED', reason_codes: ['CC01: Dense transaction cluster'] })]);
    renderDashboard();
    const row = (await screen.findByText('A5')).closest('tr');
    expect(within(row).getByText('Dense transaction cluster')).toBeInTheDocument();
    expect(within(row).getByText('Suspicion confirmed, escalated')).toBeInTheDocument();
  });

  it('says the queue is clear when there are no alerts', async () => {
    serve([]);
    renderDashboard();
    expect(await screen.findByText('System Operational: Queue Clear')).toBeInTheDocument();
  });

  it('sorts by a column header, riskiest first, then flips', async () => {
    renderDashboard();
    await screen.findByText('A1');
    const ids = () => screen.getAllByRole('row').slice(1).map(r => within(r).getByText(/^A\d$/).textContent);
    expect(ids()).toEqual(['A1', 'A2']);
    await userEvent.click(screen.getByText(/^Risk/));
    expect(ids()).toEqual(['A2', 'A1']);
  });

  it('opens an alert when its row is clicked', async () => {
    renderDashboard();
    await userEvent.click(await screen.findByText('A2'));
    expect(screen.getByTestId('path')).toHaveTextContent('/alert/A2');
  });

  it('walks the rows with j and k and opens one with Enter', async () => {
    renderDashboard();
    await screen.findByText('A1');
    await userEvent.keyboard('j');
    await userEvent.keyboard('j');
    await userEvent.keyboard('k');
    await userEvent.keyboard('{Enter}');
    expect(screen.getByTestId('path')).toHaveTextContent('/alert/A1');
  });
});
