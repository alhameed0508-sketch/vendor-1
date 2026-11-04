import React from 'react';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InvestigationsPage from './InvestigationsPage';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const inv = (over = {}) => ({
  investigation_id: 'INV_1',
  source: 'alert',
  source_id: 'AL1',
  status: 'NEW',
  assignee: null,
  outcome: null,
  allowed_next: ['UNDER_REVIEW'],
  history: [],
  ...over,
});
const reply = (data, ok = true) => ({ ok, json: () => Promise.resolve(ok ? { data } : { error: { message: data } }) });

beforeEach(() => apiFetch.mockReset());

test('lists investigations with their status as text', async () => {
  apiFetch.mockResolvedValue(reply({ investigations: [inv()] }));
  render(<InvestigationsPage />);
  const card = (await screen.findByText('AL1')).closest('article');
  expect(within(card).getByText('New')).toBeInTheDocument();
  expect(within(card).getByText(/unassigned/i)).toBeInTheDocument();
});

test('only the moves the server allows are offered, and a move updates the card', async () => {
  apiFetch
    .mockResolvedValueOnce(reply({ investigations: [inv()] }))
    .mockResolvedValueOnce(reply(inv({ status: 'UNDER_REVIEW', allowed_next: ['INVESTIGATING'] })));
  render(<InvestigationsPage />);
  const card = (await screen.findByText('AL1')).closest('article');
  expect(within(within(card).getByRole('group', { name: /move to/i })).getAllByRole('button')).toHaveLength(1);
  await userEvent.click(within(card).getByRole('button', { name: /under review/i }));
  expect(await within(card).findByRole('button', { name: /investigating/i })).toBeInTheDocument();
  expect(JSON.parse(apiFetch.mock.calls[1][1].body)).toEqual({ to: 'UNDER_REVIEW' });
});

test('resolving asks for an outcome before sending', async () => {
  apiFetch
    .mockResolvedValueOnce(reply({ investigations: [inv({ status: 'INVESTIGATING', allowed_next: ['ESCALATED', 'RESOLVED'] })] }))
    .mockResolvedValueOnce(reply(inv({ status: 'RESOLVED', outcome: 'FALSE_POSITIVE', allowed_next: ['CLOSED', 'INVESTIGATING'] })));
  render(<InvestigationsPage />);
  const card = (await screen.findByText('AL1')).closest('article');
  expect(within(card).getByRole('button', { name: /resolved/i })).toBeDisabled();
  await userEvent.selectOptions(within(card).getByLabelText(/outcome/i), 'FALSE_POSITIVE');
  await userEvent.click(within(card).getByRole('button', { name: /resolved/i }));
  await waitFor(() => expect(JSON.parse(apiFetch.mock.calls[1][1].body)).toEqual({ to: 'RESOLVED', outcome: 'FALSE_POSITIVE' }));
});

test('an intervention request shows the simulated label from the server', async () => {
  apiFetch
    .mockResolvedValueOnce(reply({ investigations: [inv()] }))
    .mockResolvedValueOnce(reply({ simulated: true, label: 'SIMULATED: no bank system connected', status: 'RECORDED_ONLY' }));
  render(<InvestigationsPage />);
  const card = (await screen.findByText('AL1')).closest('article');
  await userEvent.type(within(card).getByLabelText(/account/i), 'ACC-7');
  await userEvent.click(within(card).getByRole('button', { name: /request hold/i }));
  expect(await within(card).findByText('SIMULATED: no bank system connected')).toBeInTheDocument();
});

test('a server error is shown, not swallowed', async () => {
  apiFetch
    .mockResolvedValueOnce(reply({ investigations: [inv()] }))
    .mockResolvedValueOnce(reply('Cannot move from NEW to RESOLVED', false));
  render(<InvestigationsPage />);
  const card = (await screen.findByText('AL1')).closest('article');
  await userEvent.click(within(card).getByRole('button', { name: /under review/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot move from NEW to RESOLVED');
});

test('opening an investigation adds it to the list', async () => {
  apiFetch
    .mockResolvedValueOnce(reply({ investigations: [] }))
    .mockResolvedValueOnce(reply(inv({ source_id: 'AL9' })));
  render(<InvestigationsPage />);
  await userEvent.type(await screen.findByLabelText(/case id/i), 'AL9');
  await userEvent.click(screen.getByRole('button', { name: /open investigation/i }));
  expect(await screen.findByText('AL9')).toBeInTheDocument();
});
