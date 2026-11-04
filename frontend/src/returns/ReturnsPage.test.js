import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import ReturnsPage, { summarise } from './ReturnsPage';
import { apiFetch } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { clearLastGood } from './lastGood';
import { LIST, OVERVIEW, ok } from './fixtures';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('../auth/AuthContext', () => ({ useAuth: jest.fn() }));

const renderPage = () => render(<MemoryRouter><ReturnsPage /></MemoryRouter>);
const serve = (overview = OVERVIEW, list = LIST) => apiFetch.mockImplementation(url =>
  Promise.resolve(ok(url.endsWith('/overview') ? overview : list)));

describe('summarise', () => {
  it('says how many need a person, how many go to the desk, and the money in question', () => {
    expect(summarise(OVERVIEW.summary)).toBe('2 returns need a person. 1 is headed for the fraud desk. ₹73K is in question.');
  });
  it('says so when nothing is waiting', () => {
    expect(summarise({ needs_review: 0, by_tier: { BLOCK: 0 }, amount_in_question: 0 })).toBe('No returns need a person right now.');
  });
  it('uses the singular for one return', () => {
    expect(summarise({ needs_review: 1, by_tier: { BLOCK: 0 }, amount_in_question: 5000 })).toBe('1 return needs a person. ₹5K is in question.');
  });
});

describe('ReturnsPage', () => {
  beforeEach(() => { clearLastGood(); apiFetch.mockReset(); useAuth.mockReturnValue({ user: { username: 'asha', role: 'SUPERVISOR' } }); });

  it('opens with the summary and three ways in', async () => {
    serve();
    renderPage();
    expect(await screen.findByText(/2 returns need a person/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /See it work/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Review what needs a person/ })).toHaveAttribute('href', '/returns/RC-8');
    expect(screen.getByRole('link', { name: /Check a return in the field/ })).toHaveAttribute('href', '/returns/capture');
  });

  it('lists every claim with a word for its recommendation and what is left to do', async () => {
    serve();
    renderPage();
    const row = (await screen.findByRole('link', { name: 'RC-8' })).closest('tr');
    expect(within(row).getByText(/Send to fraud desk/)).toBeInTheDocument();
    expect(within(row).getByText('Needs a person')).toBeInTheDocument();
    expect(within(screen.getByRole('link', { name: 'RC-2' }).closest('tr')).getByText('Reviewed')).toBeInTheDocument();
    expect(within(screen.getByRole('link', { name: 'RC-9' }).closest('tr')).getByText('No action')).toBeInTheDocument();
  });

  it('points at a detected ring', async () => {
    serve();
    renderPage();
    expect(await screen.findByText(/A ring of 3 customers/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the ring' })).toHaveAttribute('href', '/returns/RC-3');
  });

  it('shows how far each check reaches and says the image check is simulated', async () => {
    serve();
    renderPage();
    expect(await screen.findByText('Receipt file')).toBeInTheDocument();
    expect(screen.getByText(/Simulated: it reads labels, not pixels/)).toBeInTheDocument();
  });

  it('explains how to read the page in a help chip', async () => {
    serve();
    renderPage();
    await screen.findByText(/2 returns need a person/);
    expect(screen.getByText('How to read this')).toBeInTheDocument();
    expect(screen.getByText(/One loud check never sends a case to the fraud desk/)).toBeInTheDocument();
  });

  it('says what to do when there are no claims', async () => {
    serve({ ...OVERVIEW, rings: [], summary: { ...OVERVIEW.summary, total: 0, needs_review: 0 } }, { claims: [] });
    renderPage();
    expect(await screen.findByText(/No return claims yet/)).toBeInTheDocument();
    expect(screen.getByText('Nothing is waiting.')).toBeInTheDocument();
  });

  it('says why when it cannot load', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 403, json: () => Promise.resolve({ success: false, error: { message: "Permission 'returns:read' not granted" } }) });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent("Permission 'returns:read' not granted");
  });

  it('runs the tour from the first card to a summary', async () => {
    serve();
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /See it work/ }));
    expect(screen.getByRole('progressbar', { name: 'Tour progress' })).toHaveAttribute('aria-valuenow', '1');
    expect(screen.getByText('Case 1 of 2')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next case' }));
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '2');
    await userEvent.click(screen.getByRole('button', { name: 'Finish' }));
    expect(screen.getByText('What you saw')).toBeInTheDocument();
    expect(screen.getByText(/Not one was refunded or blocked automatically/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Review claims' }));
    expect(screen.getByRole('button', { name: /See it work/ })).toBeInTheDocument();
  });

  it('shows the last overview with its time when the service cannot be reached', async () => {
    serve();
    const first = renderPage();
    await screen.findByText(/2 returns need a person/);
    first.unmount();
    apiFetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent(/Showing the last result from \d\d:\d\d IST/);
    expect(screen.getByText(/2 returns need a person/)).toBeInTheDocument();
  });

  it("never shows one person's last result to another person", async () => {
    serve();
    const first = renderPage();
    await screen.findByText(/2 returns need a person/);
    first.unmount();
    useAuth.mockReturnValue({ user: { username: 'ravi', role: 'SUPERVISOR' } });
    apiFetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch');
    expect(screen.queryByText(/2 returns need a person/)).not.toBeInTheDocument();
  });

  it('offers a retry when there is nothing earlier to show', async () => {
    apiFetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Failed to fetch');
    serve();
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText(/2 returns need a person/)).toBeInTheDocument();
  });
});
