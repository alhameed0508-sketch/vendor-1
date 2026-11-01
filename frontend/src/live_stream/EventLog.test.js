import React from 'react';
import { render, screen } from '@testing-library/react';
import EventLog from './EventLog';

const log = [
  { seq: 1, txnId: 'T1', from: 'A', to: 'B', amount: 1000, decision: 'PASS', caseId: null, latencyMs: 31.2 },
  { seq: 2, txnId: 'T2', from: 'B', to: 'C', amount: 900, decision: 'FLAG', caseId: 'CASE-1', latencyMs: 40 },
];

it('prints one line per payment and marks flagged lines', () => {
  const { container } = render(<EventLog log={log} />);
  expect(screen.getByRole('log')).toBeInTheDocument();
  expect(container.querySelectorAll('.live-log__line')).toHaveLength(2);
  expect(container.querySelectorAll('.live-log__line--flag')).toHaveLength(1);
  expect(screen.getByText(/CASE-1/)).toBeInTheDocument();
});

it('shows a waiting line when empty', () => {
  render(<EventLog log={[]} />);
  expect(screen.getByText(/waiting for payments/i)).toBeInTheDocument();
});
