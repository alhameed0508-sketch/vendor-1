import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CompliancePortal from './CompliancePortal';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const ALERTS = [
  { alert_id: 'ALT_1', severity: 'CRITICAL', status: 'OPEN', risk_score: 0.9, account_count: 5, total_amount: 1250000 },
  { alert_id: 'ALT_2', severity: 'HIGH', status: 'OPEN', risk_score: 0.7, account_count: 2, total_amount: 500000 },
];
const STRS = [{ str_id: 'STR_1', alert_id: 'ALT_1', status: 'DRAFT', total_amount: 1250000, transaction_count: 14, accounts_involved: ['a', 'b', 'c', 'd', 'e'] }];
const AUDIT = [{ log_id: 'L1', action: 'ESCALATION_CREATED', user: 'analyst', alert_id: 'ALT_1', details: 'Sent to MLRO', timestamp: '2026-11-01T10:00:00Z' }];

const respond = data => Promise.resolve({ json: () => Promise.resolve({ data }) });

beforeEach(() => {
  apiFetch.mockImplementation(url => {
    if (url.startsWith('/api/v1/alerts')) return respond({ alerts: ALERTS });
    if (url.startsWith('/api/v1/compliance/strs')) return respond({ records: STRS });
    return respond(AUDIT);
  });
});

describe('CompliancePortal', () => {
  it('describes the page without middle dots', async () => {
    render(<CompliancePortal />);
    const heading = await screen.findByRole('heading', { name: 'Compliance Portal' });
    expect(heading.nextSibling.textContent).not.toMatch('·');
  });

  it('shows alert amounts and the selected total in the shared rupee format', async () => {
    render(<CompliancePortal />);
    expect(await screen.findByRole('cell', { name: '₹12.5L' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '₹5L' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Select All' }));
    expect(screen.getByText('Total Amount').previousSibling).toHaveTextContent('₹17.5L');
  });

  it('names severity in words', async () => {
    render(<CompliancePortal />);
    expect(await screen.findByText('Critical', { selector: '.badge' })).toBeInTheDocument();
    expect(screen.queryByText('CRITICAL')).toBeNull();
  });

  it('describes each STR in a plain list instead of dot-joined fragments', async () => {
    render(<CompliancePortal />);
    expect(await screen.findByText('ALT_1, ₹12.5L, 14 transfers, 5 accounts')).toBeInTheDocument();
  });

  it('exports the selected alerts as STRs, then reloads the STR list', async () => {
    render(<CompliancePortal />);
    await userEvent.click(await screen.findByRole('cell', { name: '₹5L' }));
    await userEvent.click(screen.getByRole('button', { name: /Export 1 STR$/ }));
    const post = apiFetch.mock.calls.find(([url]) => url === '/api/v1/compliance/str-export');
    expect(JSON.parse(post[1].body)).toEqual({ alert_ids: ['ALT_2'] });
    expect(apiFetch.mock.calls.filter(([url]) => url.startsWith('/api/v1/compliance/strs'))).toHaveLength(2);
  });

  it('moves a draft STR forward when it is approved', async () => {
    render(<CompliancePortal />);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const post = apiFetch.mock.calls.find(([url]) => url === '/api/v1/compliance/str/STR_1/approve');
    expect(post[1].method).toBe('POST');
  });

  it('writes audit actions in words and joins details with commas', async () => {
    render(<CompliancePortal />);
    expect(await screen.findByText('Escalation created')).toBeInTheDocument();
    expect(screen.getByText('analyst, ALT_1, Sent to MLRO')).toBeInTheDocument();
  });
});
