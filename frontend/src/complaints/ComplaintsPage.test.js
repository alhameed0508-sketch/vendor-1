import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ComplaintsPage from './ComplaintsPage';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const row = (id, name, extra) => ({
  complaint_id: id, customer_name: name, channel: 'UPI', amount: 240000, status: 'OPEN', cross_border: false,
  reported_at: '2027-01-12T17:30:00+05:30', resolve_by: '2027-02-26T17:30:00+05:30', days_left: 39, overdue: false,
  resolution_limit_days: 45, shadow_credit_by: null, category: 'THIRD_PARTY_BREACH', outcome: 'ZERO_LIABILITY',
  flags: [], evidence_count: 4, ...extra,
});

const DESK = {
  as_of: '2027-03-01T10:00:00+05:30',
  summary: { open: 7, due_soon: 1, overdue: 1, shadow_credits_pending: 1, compensation_due: 21250, mule_linked: 1,
             amount_disputed: 651749 },
  cases: [
    row('FC-2027-000105', 'Imran Hussain', { days_left: -3, overdue: true, outcome: 'BANK_POLICY' }),
    row('FC-2027-000103', 'Vikram Sethi', { category: 'NOT_FRAUD', outcome: 'NOT_FRAUD', flags: ['RETURN_ABUSE'] }),
  ],
};

const renderPage = () => render(<MemoryRouter><ComplaintsPage /></MemoryRouter>);

describe('ComplaintsPage', () => {
  it('shows the desk counts, with compensation to the exact rupee', async () => {
    apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: DESK }) });
    renderPage();
    expect(await screen.findByText('₹21,250')).toBeInTheDocument();
    expect(screen.getByText('₹6.5L disputed')).toBeInTheDocument();
    expect(screen.getByText(/a demo date after the rules start/)).toBeInTheDocument();
  });

  it('lists cases most urgent first, each with its clock, in plain words', async () => {
    apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: DESK }) });
    renderPage();
    const [first, second] = await screen.findAllByRole('link');
    expect(first).toHaveAttribute('href', '/complaints/FC-2027-000105');
    expect(within(first).getByText('3 days overdue')).toBeInTheDocument();
    expect(within(first).getByText('Bank policy decides')).toBeInTheDocument();
    expect(within(second).getByText('Customer made the payment')).toBeInTheDocument();
    expect(within(second).getByText('Returned item was swapped')).toBeInTheDocument();
  });

  it('says when the desk cannot load', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 403, json: () => Promise.resolve({ success: false,
      error: { message: "Permission 'complaints:read' not granted" } }) });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('not granted');
  });
});
