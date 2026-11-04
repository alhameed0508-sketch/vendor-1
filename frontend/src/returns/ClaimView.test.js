import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ClaimView from './ClaimView';
import { apiFetch } from '../auth/api';
import { clearLastGood } from './lastGood';
import { useAuth } from '../auth/AuthContext';
import { claimView, ok } from './fixtures';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('../auth/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('sonner', () => ({ toast: Object.assign(jest.fn(), { error: jest.fn() }) }));

const ring = ['RC-1', 'RC-2', 'RC-3'];
const ringView = id => {
  const v = claimView(id, { claim: { customer_id: `C-${id}`, customer_name: `Person ${id}` } });
  v.signals = v.signals.map(s => (s.name === 'graph' ? { ...s, detail: { ring_claims: ring, ring_size: 3 } } : s));
  return v;
};

const renderView = (id = 'RC-1') => render(
  <MemoryRouter initialEntries={[`/returns/${id}`]}>
    <Routes><Route path="/returns/:claimId" element={<ClaimView />} /></Routes>
  </MemoryRouter>,
);
const serve = (views = {}) => apiFetch.mockImplementation(url => {
  const id = decodeURIComponent(url.split('/').pop());
  return Promise.resolve(views[id] ? ok(views[id]) : { ok: false, status: 404, json: () => Promise.resolve({ success: false, error: { message: `Return claim not found: ${id}` } }) });
});

describe('ClaimView', () => {
  beforeEach(() => { clearLastGood(); apiFetch.mockReset(); useAuth.mockReturnValue({ user: { role: 'SUPERVISOR' } }); });

  it('opens with the three-part case strip', async () => {
    serve({ 'RC-1': ringView('RC-1'), 'RC-2': ringView('RC-2'), 'RC-3': ringView('RC-3') });
    renderView();
    const strip = await screen.findByLabelText('Case summary');
    expect(within(strip).getByText('Person returned a phone.')).toBeInTheDocument();
    expect(within(strip).getByText('The device is shared.')).toBeInTheDocument();
    expect(within(strip).getByText('Send to the fraud desk.')).toBeInTheDocument();
  });

  it('shows the three layers: timeline, heatmap and linked customers', async () => {
    serve({ 'RC-1': ringView('RC-1'), 'RC-2': ringView('RC-2'), 'RC-3': ringView('RC-3') });
    renderView();
    expect(await screen.findByLabelText(/Move through the case/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Shared device' })).toBeInTheDocument();
    expect(await screen.findByRole('img', { name: '3 customers linked through 3 shared identifiers' })).toBeInTheDocument();
    expect(screen.getByText(/These 3 customers share device, address, card/)).toBeInTheDocument();
  });

  it('focuses a check across the layers when its row is selected', async () => {
    serve({ 'RC-1': ringView('RC-1'), 'RC-2': ringView('RC-2'), 'RC-3': ringView('RC-3') });
    renderView();
    const device = await screen.findByRole('button', { name: 'Shared device' });
    await userEvent.click(device);
    expect(device).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(device);
    expect(device).toHaveAttribute('aria-pressed', 'false');
  });

  it('moves the scrubber through the events', async () => {
    serve({ 'RC-1': claimView('RC-1') });
    renderView();
    const scrub = await screen.findByLabelText(/Move through the case/);
    expect(scrub).toHaveAttribute('max', '1');
    fireEvent.change(scrub, { target: { value: '0' } });
    expect(screen.getByText(/event 1 of 2/)).toBeInTheDocument();
  });

  it('lists every check in the ledger and says why a high score stayed capped', async () => {
    const view = claimView('RC-1');
    view.fusion = { ...view.fusion, tier: 'VERIFY', score: 64, capped_from: 'CHALLENGE', corroborating: 1 };
    serve({ 'RC-1': view });
    renderView();
    const table = (await screen.findByRole('heading', { name: 'Evidence ledger' })).parentElement.querySelector('table');
    expect(within(table).getAllByRole('row')).toHaveLength(7);
    expect(screen.getByText(/too few checks agree, so it stays at verify/)).toBeInTheDocument();
    expect(screen.getByText('Organised return-fraud ring')).toBeInTheDocument();
  });

  it('downloads the bank package as PDF', async () => {
    const createUrl = jest.fn(() => 'blob:x');
    global.URL.createObjectURL = createUrl;
    global.URL.revokeObjectURL = jest.fn();
    apiFetch.mockImplementation(url => (url.endsWith('package.pdf')
      ? Promise.resolve({ ok: true, blob: () => Promise.resolve(new Blob(['%PDF'])) })
      : Promise.resolve(ok(claimView('RC-1')))));
    renderView();
    await userEvent.click(await screen.findByRole('button', { name: 'Download bank package (PDF)' }));
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/returns/RC-1/package.pdf');
    expect(createUrl).toHaveBeenCalled();
  });

  it('lets a supervisor record an outcome once', async () => {
    const reviewed = claimView('RC-1', { review: { outcome: 'escalate', notes: 'ring', reviewed_by: 'supervisor', reviewed_at: '2027-03-01T10:00:00+05:30' } });
    apiFetch.mockImplementation((url, opts) => Promise.resolve(ok(opts?.method === 'POST' ? reviewed : claimView('RC-1'))));
    renderView();
    await userEvent.selectOptions(await screen.findByLabelText('Outcome'), 'escalate');
    await userEvent.click(screen.getByRole('button', { name: 'Record outcome' }));
    expect(await screen.findByText(/recorded by supervisor/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record outcome' })).not.toBeInTheDocument();
  });

  it('tells everyone else that only a supervisor decides', async () => {
    useAuth.mockReturnValue({ user: { role: 'GUEST' } });
    serve({ 'RC-1': claimView('RC-1') });
    renderView();
    expect(await screen.findByText(/Only a supervisor records the outcome/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Outcome')).not.toBeInTheDocument();
  });

  it('says when the claim does not exist', async () => {
    serve({});
    renderView('RC-0');
    expect(await screen.findByRole('alert')).toHaveTextContent('Return claim not found: RC-0');
  });

  it('shows how the score adds up, from the biggest share down, ending at the combined score', async () => {
    serve({ 'RC-1': claimView('RC-1') });
    renderView();
    const panel = (await screen.findByRole('heading', { name: 'How the score adds up' })).parentElement;
    const rows = within(panel).getAllByRole('listitem').map(li => li.textContent);
    expect(rows[0]).toMatch(/Photo details\+30\.0|Receipt file\+30\.0/);
    expect(rows[rows.length - 1]).toBe('Combined score100.0');
    expect(within(panel).getByText(/Adds nothing: photo against the claim, return habits/)).toBeInTheDocument();
  });

  it('says why the shown score differs from the combined one', async () => {
    const view = claimView('RC-1');
    view.fusion = { ...view.fusion, tier: 'VERIFY', score: 64, raw_score: 91.4, capped_from: 'BLOCK', corroborating: 1 };
    serve({ 'RC-1': view });
    renderView();
    expect(await screen.findByText(/Shown as 64, not 91, because too few checks above 60 agree for the block band/)).toBeInTheDocument();
  });

  it('states how many checks agree and how many it takes', async () => {
    serve({ 'RC-1': claimView('RC-1') });
    renderView();
    expect(await screen.findByText('4 of 6 checks agree. 3 needed to send to the fraud desk.')).toBeInTheDocument();
  });

  it('puts source, evidence time and agreeing checks in the ledger, and keeps raw data folded away', async () => {
    const view = claimView('RC-1');
    view.signals = view.signals.map(s => (s.name === 'exif'
      ? { ...s, source: 'Photo metadata', detail: { taken_at: '2027-02-01T10:00:00+05:30' }, corroborated_by: ['receipt', 'device'] }
      : s));
    serve({ 'RC-1': view });
    renderView();
    const row = (await screen.findByRole('cell', { name: 'Photo details' })).closest('tr');
    expect(within(row).getByText('Photo metadata')).toBeInTheDocument();
    expect(within(row).getByText('Receipt file, Shared device')).toBeInTheDocument();
    expect(within(row).getByText(/1 Feb/)).toBeInTheDocument();
    expect(screen.getByText('Raw data, for debugging, not for review').closest('details')).not.toHaveAttribute('open');
  });

  it('puts the review and download actions beside the recommendation', async () => {
    serve({ 'RC-1': claimView('RC-1') });
    renderView();
    const strip = await screen.findByLabelText('Case summary');
    expect(within(strip).getByRole('link', { name: 'Open for review' })).toHaveAttribute('href', '#outcome');
    expect(within(strip).getByRole('button', { name: 'Download evidence package' })).toBeInTheDocument();
  });

  it('shows the last result with its time when the service cannot be reached', async () => {
    serve({ 'RC-1': claimView('RC-1') });
    const first = renderView();
    await screen.findByLabelText('Case summary');
    first.unmount();
    apiFetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    renderView();
    expect(await screen.findByRole('alert')).toHaveTextContent(/We couldn't reach the signal service. Showing the last result from \d\d:\d\d IST/);
    expect(screen.getByLabelText('Case summary')).toBeInTheDocument();
    serve({ 'RC-1': claimView('RC-1') });
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(screen.queryByText(/We couldn't reach/)).not.toBeInTheDocument();
  });

  it('does not hide a refusal behind an old result', async () => {
    serve({ 'RC-1': claimView('RC-1') });
    const first = renderView();
    await screen.findByLabelText('Case summary');
    first.unmount();
    apiFetch.mockResolvedValue({ ok: false, status: 403, json: () => Promise.resolve({ success: false, error: { message: "Permission 'returns:read' not granted" } }) });
    renderView();
    expect(await screen.findByRole('alert')).toHaveTextContent("Permission 'returns:read' not granted");
    expect(screen.queryByLabelText('Case summary')).not.toBeInTheDocument();
  });

  it('keeps the claim when the linked claims cannot be loaded and offers a retry', async () => {
    apiFetch.mockImplementation(url => (url.endsWith('/RC-1')
      ? Promise.resolve(ok(ringView('RC-1')))
      : Promise.reject(new TypeError('Failed to fetch'))));
    renderView();
    expect(await screen.findByText(/The linked claims could not be loaded, so only this claim is shown/)).toBeInTheDocument();
    expect(screen.getByLabelText('Case summary')).toBeInTheDocument();
    serve({ 'RC-1': ringView('RC-1'), 'RC-2': ringView('RC-2'), 'RC-3': ringView('RC-3') });
    await userEvent.click(screen.getAllByRole('button', { name: 'Retry' })[0]);
    expect(await screen.findByRole('img', { name: '3 customers linked through 3 shared identifiers' })).toBeInTheDocument();
  });

  it('explains an empty heatmap and an unlinked claim in words', async () => {
    const view = claimView('RC-1');
    view.signals = view.signals.map(s => ({ ...s, available: false, score: 0 }));
    serve({ 'RC-1': view });
    renderView();
    expect(await screen.findByText(/No checks have run yet/)).toBeInTheDocument();
    expect(screen.getByText(/No connected customers found/)).toBeInTheDocument();
  });
});
