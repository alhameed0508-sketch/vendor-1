import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('sonner', () => ({ toast: { error: jest.fn() } }));

const alert = (id, total_amount, over = {}) => ({
  alert_id: id, severity: 'CRITICAL', status: 'OPEN', risk_score: 0.9, total_amount,
  account_count: 3, created_at: '2026-11-01T10:00:00Z', ...over,
});

const serve = alerts => apiFetch.mockResolvedValue({ json: () => Promise.resolve({ data: { alerts } }) });

beforeEach(() => serve([alert('A1', 10000000), alert('A2', 7900000)]));

const renderDashboard = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);
const statCard = label => screen.getByText(label, { selector: '.text-metric-label' }).closest('.stat-card');
const filterGroup = name => within(screen.getByRole('group', { name }));

it('shows the flagged total in the shared rupee format', async () => {
  renderDashboard();
  expect(await screen.findByText('₹1.79Cr')).toBeInTheDocument();
  expect(screen.getByText('₹1.79Cr flagged')).toBeInTheDocument();
});

describe('stat cards', () => {
  it('colour only the cards that carry a risk level', async () => {
    renderDashboard();
    await screen.findByText('₹1.79Cr');
    expect(statCard('Critical')).toHaveClass('stat-card--critical');
    expect(statCard('High severity')).toHaveClass('stat-card--high');
    expect(statCard('Open cases').className).toBe('stat-card');
    expect(statCard('Total flagged').className).toBe('stat-card');
  });

  it('arrive one after another', async () => {
    renderDashboard();
    await screen.findByText('₹1.79Cr');
    expect(['Critical', 'High severity', 'Open cases', 'Total flagged']
      .map(label => statCard(label).style.getPropertyValue('--i'))).toEqual(['0', '1', '2', '3']);
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

    await userEvent.click(filterGroup('Severity').getByRole('button', { name: 'High' }));
    expect(screen.queryByText('A1')).not.toBeInTheDocument();
    expect(screen.getByText('A2')).toBeInTheDocument();
    expect(filterGroup('Severity').getByRole('button', { name: 'High' })).toHaveAttribute('aria-pressed', 'true');
    expect(filterGroup('Severity').getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false');

    await userEvent.click(filterGroup('Status').getByRole('button', { name: 'Resolved' }));
    expect(screen.queryByText('A2')).not.toBeInTheDocument();
    expect(screen.getByText('A3')).toBeInTheDocument();
  });

  it('keep every status the queue can hold', async () => {
    renderDashboard();
    await screen.findByText('A1');
    const names = filterGroup('Status').getAllByRole('button').map(b => b.textContent);
    expect(names).toEqual(['All', 'Open', 'Under review', 'Resolved', 'False positive', 'STR filed']);
  });

  it('say so when they hide every alert', async () => {
    renderDashboard();
    await screen.findByText('A1');
    await userEvent.click(filterGroup('Severity').getByRole('button', { name: 'Medium' }));
    expect(screen.getByText('No alerts match filters')).toBeInTheDocument();
    expect(screen.getByText('Adjust severity or status filters')).toBeInTheDocument();
  });
});

it('says the queue is clear when there are no alerts', async () => {
  serve([]);
  renderDashboard();
  expect(await screen.findByText('Queue is clear')).toBeInTheDocument();
});
