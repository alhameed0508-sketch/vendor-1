import React from 'react';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { toast } from 'sonner';
import CaseView, { POLL_MS } from './CaseView';
import { apiFetch } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('../auth/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('sonner', () => ({ toast: Object.assign(jest.fn(), { error: jest.fn() }) }));

const step = (id, source, category, outcome) => ({
  evidence_id: id, at: '2027-02-23T01:40:00+05:30', received_at: '2027-02-23T09:15:00+05:30', source, kind: 'x',
  summary: `${source} says ${id}`, category, outcome, customer_liability: 0, flags: [], proof_met: 0, proof_needed: 0,
});
const item = (id, source) => ({ id, source, summary: `${source} says ${id}`, hash: `hash-${id}` });

const VIEW = {
  complaint_id: 'FC-2027-000101', customer_name: 'Kavitha Raman', channel: 'NETBANKING', amount: 185000,
  reported_at: '2027-02-23T09:15:00+05:30', status: 'OPEN', cross_border: false, as_of: '2027-03-01T10:00:00+05:30',
  evidence: [item('E1', 'CUSTOMER'), item('E2', 'MULECATCH'), item('E3', 'AUTH_LOG')],
  replay: [
    step('E1', 'CUSTOMER', 'UNDETERMINED', 'UNPROVEN'),
    step('E2', 'MULECATCH', 'THIRD_PARTY_BREACH', 'ZERO_LIABILITY'),
    step('E3', 'AUTH_LOG', 'THIRD_PARTY_BREACH', 'ZERO_LIABILITY'),
  ],
  chain: { intact: true, broken_at: null },
  deadlines: {
    resolve_by: '2027-04-09T09:15:00+05:30', days_left: 39, overdue: false, resolution_limit_days: 45,
    shadow_credit_by: null, reported_after_days: 0, within_zero_liability_window: true, rules_in_force: true,
  },
  finding: { category: 'THIRD_PARTY_BREACH', reasons: [{ text: 'Beneficiary is a mule', evidence: ['E2'] }],
             checklist: [], proof_complete: false, flags: ['MULE_BENEFICIARY'] },
  liability: { outcome: 'ZERO_LIABILITY', customer_liability: 0, bank_liability: 185000,
               basis: 'Third-party breach reported within 5 calendar days: zero customer liability.' },
  compensation: { eligible: false, net_loss: 185000, amount: 0, split: {}, pay_by: null,
                  checks: [{ label: 'Loss came from customer negligence', met: false }, { label: 'Individual', met: true }] },
  mule_link: { evidence_id: 'E2', alert_id: 'ALT_7', account_id: 'AC_M', role: 'AGGREGATOR', risk_score: 0.99 },
  decision: null,
};
const NARRATIVE = { sentences: [{ text: 'The SIM was swapped.', evidence: ['E3'] }], source: 'template', dropped: 0 };

const respond = (data, status = 200) => Promise.resolve({
  ok: status < 400, status,
  json: () => Promise.resolve(status < 400 ? { success: true, data } : { success: false, error: { message: data } }),
});

let current;
beforeEach(() => {
  current = VIEW;
  useAuth.mockReturnValue({ user: { role: 'SUPERVISOR' } });
  apiFetch.mockImplementation((url, opts) => {
    if (url.endsWith('/narrative')) return respond(NARRATIVE);
    if (url.endsWith('/decision')) {
      const body = JSON.parse(opts.body);
      return respond({ ...current, status: 'RESOLVED', decision: { ...body, decided_by: 'supervisor',
        decided_at: VIEW.as_of, followed_recommendation: true, within_time_limit: true } });
    }
    return respond(current);
  });
});
afterEach(() => jest.useRealTimers());

const renderCase = () => render(
  <MemoryRouter initialEntries={['/complaints/FC-2027-000101']}>
    <Routes><Route path="/complaints/:complaintId" element={<CaseView />} /></Routes>
  </MemoryRouter>,
);

describe('CaseView', () => {
  it('shows the flow, the clock, the recommendation and the mule it paid', async () => {
    renderCase();
    expect(await screen.findByRole('heading', { name: 'Kavitha Raman' })).toBeInTheDocument();
    expect(screen.getByText('39 days left')).toBeInTheDocument();
    expect(screen.getAllByText('Customer pays nothing').length).toBeGreaterThan(0);
    expect(screen.getByText('Money went to a known mule')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'MuleCatch alert ALT_7' })).toHaveAttribute('href', '/alert/ALT_7');
    expect(screen.getByText('Hash chain intact')).toBeInTheDocument();
  });

  it('cites evidence in the narrative', async () => {
    renderCase();
    const narrative = await screen.findByRole('region', { name: 'Narrative' });
    expect(await within(narrative).findByText('The SIM was swapped.')).toBeInTheDocument();
    expect(within(narrative).getByRole('link', { name: 'E3' })).toHaveAttribute('href', '#ev-E3');
  });

  it('replays the case one item at a time, then returns to live', async () => {
    jest.useFakeTimers();
    renderCase();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    await user.click(await screen.findByRole('button', { name: 'Replay the case' }));
    const flow = screen.getByRole('region', { name: 'Live workflow' });
    expect(within(flow).getByText('Step 1 of 3')).toBeInTheDocument();
    expect(within(flow).getByText('Not clear yet')).toBeInTheDocument();
    expect(within(flow).queryByText('MULECATCH says E2')).not.toBeInTheDocument();
    act(() => jest.advanceTimersByTime(1400));
    expect(within(flow).getByText('Step 2 of 3')).toBeInTheDocument();
    expect(within(flow).getByText('MULECATCH says E2')).toBeInTheDocument();
    act(() => jest.advanceTimersByTime(1400));
    expect(within(flow).getByText('Live')).toBeInTheDocument();
  });

  it('shows evidence a partner posts while the case is open', async () => {
    jest.useFakeTimers();
    renderCase();
    await screen.findByRole('heading', { name: 'Kavitha Raman' });
    current = {
      ...VIEW,
      evidence: [...VIEW.evidence, item('E4', 'COURIER')],
      replay: [...VIEW.replay, step('E4', 'COURIER', 'THIRD_PARTY_BREACH', 'ZERO_LIABILITY')],
    };
    await act(async () => { jest.advanceTimersByTime(POLL_MS); });
    expect(await screen.findByText('COURIER says E4')).toBeInTheDocument();
    expect(toast).toHaveBeenCalledWith('New evidence from Courier', { description: 'COURIER says E4' });
  });

  it('lets a supervisor record the decision once', async () => {
    renderCase();
    await userEvent.type(await screen.findByLabelText('Reasons'), 'Money went to a mule.');
    await userEvent.click(screen.getByRole('button', { name: 'Record decision' }));
    expect(await screen.findByText('Followed the recommendation')).toBeInTheDocument();
    const [, opts] = apiFetch.mock.calls.find(([url]) => url.endsWith('/decision'));
    expect(JSON.parse(opts.body)).toEqual({ outcome: 'ZERO_LIABILITY', customer_liability: 0, notes: 'Money went to a mule.' });
    expect(screen.queryByRole('button', { name: 'Record decision' })).not.toBeInTheDocument();
  });

  it('gives guests a read-only case', async () => {
    useAuth.mockReturnValue({ user: { role: 'GUEST' } });
    renderCase();
    await screen.findByRole('heading', { name: 'Kavitha Raman' });
    expect(screen.queryByRole('button', { name: 'Record decision' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Evidence pack/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add to the chain' })).not.toBeInTheDocument();
    expect(screen.getByText(/Sign in as bank staff/)).toBeInTheDocument();
  });

  it('says so when the complaint does not exist', async () => {
    apiFetch.mockImplementation(() => respond('Complaint not found: FC-2027-000101', 404));
    renderCase();
    expect(await screen.findByRole('alert')).toHaveTextContent('Complaint not found');
  });
});
