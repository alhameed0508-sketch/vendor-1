import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import LiveStream from './LiveStream';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
// eslint-disable-next-line import/first
import { apiFetch } from '../auth/api';

if (typeof global.TextDecoder === 'undefined') {
  // eslint-disable-next-line global-require
  global.TextDecoder = require('util').TextDecoder;
}

function sseResponse(frames, { hold = false } = {}) {
  const bytes = frames.map((f) => new TextEncoder().encode(`data: ${JSON.stringify(f)}\n\n`));
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: () =>
          i < bytes.length
            ? Promise.resolve({ done: false, value: bytes[i++] })
            : hold
              ? new Promise(() => {})
              : Promise.resolve({ done: true }),
      }),
    },
  };
}

const flagEvent = {
  payment: { txn_id: 'T1', from_account: 'A1', to_account: 'B1', amount: 4900 },
  decision: 'FLAG',
  case_id: 'CASE-AB12',
  ring_members: ['A1', 'B1', 'C1'],
  reasons: ['CC01: dense ring'],
  risk_score: 0.88,
  latency_ms: 31,
  counters: { payments: 1, flagged: 1, mule_payments_flagged: 1, genuine_accounts_flagged: 0 },
};

beforeEach(() => {
  apiFetch.mockReset();
  if (typeof global.TextEncoder === 'undefined') {
    // eslint-disable-next-line global-require
    global.TextEncoder = require('util').TextEncoder;
  }
});

test('labels the data as synthetic and starts idle', () => {
  render(<LiveStream />);
  expect(screen.getAllByText(/synthetic data/i).length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: /start stream/i })).toBeInTheDocument();
});

test('opens a case card when a flagged payment arrives', async () => {
  apiFetch.mockResolvedValue(sseResponse([flagEvent], { hold: true }));
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  expect(await screen.findByText('CASE-AB12')).toBeInTheDocument();
  expect(screen.getByText(/not blocked/i)).toBeInTheDocument();
  expect(screen.getByText('Genuine accounts flagged').nextSibling).toHaveTextContent('0');
});

test('sends no token in the URL', async () => {
  apiFetch.mockResolvedValue(sseResponse([flagEvent], { hold: true }));
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  await screen.findByText('CASE-AB12');
  const [url] = apiFetch.mock.calls[0];
  expect(url).not.toMatch(/token/i);
});

test('shows an error, not fake data, when the request fails before any payment', async () => {
  apiFetch.mockResolvedValue({ ok: false, status: 500, body: null });
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable/i);
});

test('Stop ends a live stream', async () => {
  apiFetch.mockResolvedValue(sseResponse([flagEvent], { hold: true }));
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  await screen.findByText('CASE-AB12');
  fireEvent.click(screen.getByRole('button', { name: /stop/i }));
  expect(await screen.findByRole('button', { name: /replay/i })).toBeInTheDocument();
});

test('clicking an account opens its details and logs the payment', async () => {
  apiFetch.mockResolvedValue(sseResponse([flagEvent], { hold: true }));
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  await screen.findByText('CASE-AB12');
  expect(screen.getByRole('log')).toHaveTextContent(/A1 → B1/);
  fireEvent.click(screen.getByRole('button', { name: 'Account A1' }));
  const details = screen.getByRole('dialog', { name: 'Account A1' });
  expect(details).toHaveTextContent('B1');
  fireEvent.click(screen.getByRole('button', { name: /close/i }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('lets a reviewer confirm the open case on this page only', async () => {
  apiFetch.mockResolvedValue(sseResponse([flagEvent], { hold: true }));
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  await screen.findByText('CASE-AB12');
  fireEvent.click(screen.getByRole('button', { name: /confirm mule ring/i }));
  expect(await screen.findByText(/Confirmed by reviewer/)).toBeInTheDocument();
  expect(screen.getByText(/demo only/i)).toBeInTheDocument();
});
