import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import LiveStream from './LiveStream';

jest.mock('../auth/api', () => ({ resolveUrl: (p) => p, getToken: () => null }));

class FakeEventSource {
  static last = null;
  constructor(url) {
    this.url = url;
    this.closed = false;
    FakeEventSource.last = this;
  }
  close() {
    this.closed = true;
  }
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
  global.EventSource = FakeEventSource;
});

test('labels the data as synthetic and starts idle', () => {
  render(<LiveStream />);
  expect(screen.getAllByText(/synthetic data/i).length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: /start stream/i })).toBeInTheDocument();
});

test('opens a case card when a flagged payment arrives', () => {
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  act(() => FakeEventSource.last.onmessage({ data: JSON.stringify(flagEvent) }));
  expect(screen.getByText('CASE-AB12')).toBeInTheDocument();
  expect(screen.getByText(/not blocked/i)).toBeInTheDocument();
  expect(screen.getByText('Genuine accounts flagged').nextSibling).toHaveTextContent('0');
});

test('shows an error, not fake data, when the stream fails before any payment', () => {
  render(<LiveStream />);
  fireEvent.click(screen.getByRole('button', { name: /start stream/i }));
  act(() => FakeEventSource.last.onerror());
  expect(screen.getByRole('alert')).toHaveTextContent(/unavailable/i);
  expect(FakeEventSource.last.closed).toBe(true);
});
