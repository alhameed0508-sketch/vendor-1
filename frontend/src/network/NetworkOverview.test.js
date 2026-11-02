import React from 'react';
import { render, screen } from '@testing-library/react';
import NetworkOverview from './NetworkOverview';
import { apiFetch } from '../auth/api';
import useAlertStream from '../hooks/useAlertStream';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('../hooks/useAlertStream', () => jest.fn());
jest.mock('../components/IndiaMap', () => () => null);
jest.mock('../graph_viz/NetworkGraph', () => () => null);

const node = (account_id, city) => ({ account_id, city, role: 'MULE' });
const edge = (from_account, to_account, total_amount) => ({ from_account, to_account, total_amount, txn_count: 1 });

// Both alerts touch Pune and Mumbai, so a per-city sum would count each alert twice.
const ALERTS = [
  { alert_id: 'A1', severity: 'CRITICAL', nodes: [node('X', 'Pune'), node('Y', 'Mumbai')], edges: [edge('X', 'Y', 1000000)] },
  { alert_id: 'A2', severity: 'HIGH', nodes: [node('X', 'Pune'), node('Z', 'Mumbai')], edges: [edge('X', 'Z', 500000)] },
];

const respond = data => Promise.resolve({ json: () => Promise.resolve({ data }) });

beforeEach(() => {
  useAlertStream.mockReturnValue({ connected: true });
  apiFetch.mockImplementation(url => respond(url.includes('/alerts') ? { alerts: ALERTS } : null));
});

describe('NetworkOverview', () => {
  it('describes the page in plain words without middle dots', async () => {
    render(<NetworkOverview />);
    const subtitle = await screen.findByText(/Updated/);
    expect(subtitle.closest('p').textContent).not.toMatch('·');
    expect(screen.getByText('3 accounts, 2 transfers from 2 alerts')).toBeInTheDocument();
  });

  it('says whether live updates are on, so it never reads as the app being offline', async () => {
    render(<NetworkOverview />);
    expect(await screen.findByText('Live updates on')).toBeInTheDocument();
  });

  it('says live updates are off when the stream drops', async () => {
    useAlertStream.mockReturnValue({ connected: false });
    render(<NetworkOverview />);
    expect(await screen.findByText('Live updates off')).toBeInTheDocument();
  });

  it('puts the stat tiles in the shared grid that folds to two columns on phones', async () => {
    render(<NetworkOverview />);
    expect((await screen.findByText('Mule clusters')).closest('.stat-grid')).not.toBeNull();
  });

  it('counts each alert once in the regional flagged amount', async () => {
    render(<NetworkOverview />);
    expect(await screen.findByText('₹15L')).toBeInTheDocument();
  });
});
