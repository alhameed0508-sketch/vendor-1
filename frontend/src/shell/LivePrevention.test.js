import React from 'react';
import { render, screen, within } from '@testing-library/react';
import LivePrevention from './LivePrevention';
import useScoreStream from '../live_stream/useScoreStream';
import { initialState } from '../live_stream/streamReducer';

jest.mock('../live_stream/useScoreStream');

const LOG = [
  { seq: 1, txnId: 'T1', from: 'ACC-1', to: 'ACC-2', amount: 4000, decision: 'PASS', caseId: null, latencyMs: 12 },
  { seq: 2, txnId: 'T2', from: 'MULE-1', to: 'MULE-2', amount: 250000, decision: 'FLAG', caseId: 'CASE-1', latencyMs: 15 },
];
const STATE = {
  ...initialState,
  status: 'live',
  events: 2,
  counters: { ...initialState.counters, payments: 2, flagged: 1, mule_amount_flagged: 250000, genuine_amount_flagged: 4000 },
  amounts: { scored: 254000, held: 250000 },
  rings: { 'CASE-1': { caseId: 'CASE-1', held: 250000, risk: 0.91, members: ['MULE-1', 'MULE-2'], payments: [] } },
  reviews: {},
  log: LOG,
};
const hook = (state = STATE) => {
  const api = { state, start: jest.fn(), stop: jest.fn(), review: jest.fn() };
  useScoreStream.mockReturnValue(api);
  return api;
};
const tile = label => screen.getByText(label).closest('.live-prev__tile');

afterEach(() => useScoreStream.mockReset());

test('starts the stream on its own, so the page never opens empty', () => {
  const api = hook();
  render(<LivePrevention />);
  expect(api.start).toHaveBeenCalledTimes(1);
});

test('shows money scored, held, prevented against the ground truth, and genuine money wrongly held', () => {
  hook();
  render(<LivePrevention />);
  expect(within(tile('Payments scored')).getByText('2')).toBeInTheDocument();
  expect(within(tile('Money scored')).getByText('₹2.5L')).toBeInTheDocument();
  expect(within(tile('Held for review')).getByText('₹2.5L')).toBeInTheDocument();
  expect(within(tile('Prevented (verified)')).getByText('₹2.5L')).toBeInTheDocument();
  expect(within(tile('Genuine money wrongly held')).getByText('₹4K')).toBeInTheDocument();
});

test('without ground truth, prevented is only what a reviewer has confirmed', () => {
  const { mule_amount_flagged, genuine_amount_flagged, ...counters } = STATE.counters;
  hook({ ...STATE, counters });
  render(<LivePrevention />);
  expect(within(tile('Prevented (verified)')).getByText('₹0')).toBeInTheDocument();
  hook({ ...STATE, counters, reviews: { 'CASE-1': 'confirmed' } });
  render(<LivePrevention />);
  expect(within(screen.getAllByText('Prevented (verified)')[1].closest('.live-prev__tile')).getByText('₹2.5L')).toBeInTheDocument();
});

test('lists open cases with their held money, and lets a reviewer confirm one in place', () => {
  const api = hook();
  render(<LivePrevention />);
  const row = screen.getByRole('row', { name: /CASE-1/ });
  expect(row).toHaveTextContent('2 accounts');
  expect(row).toHaveTextContent('₹2.5L');
  within(row).getByRole('button', { name: 'Confirm' }).click();
  expect(api.review).toHaveBeenCalledWith('CASE-1', 'confirmed');
});

test('lists the latest payments newest first and marks held ones', () => {
  hook();
  render(<LivePrevention />);
  const rows = within(screen.getByRole('table', { name: 'Latest payments' })).getAllByRole('row').slice(1);
  expect(rows[0]).toHaveTextContent('MULE-1');
  expect(rows[0]).toHaveTextContent('Held');
  expect(rows[1]).toHaveTextContent('Passed');
});

test('says the data is synthetic and can be paused', () => {
  const api = hook();
  render(<LivePrevention />);
  expect(screen.getByText('Synthetic data')).toBeInTheDocument();
  screen.getByRole('button', { name: 'Pause' }).click();
  expect(api.stop).toHaveBeenCalled();
});

test('shows the stream error instead of a blank panel', () => {
  hook({ ...initialState, status: 'error', error: 'Stream unavailable: connection failed' });
  render(<LivePrevention />);
  expect(screen.getByRole('alert')).toHaveTextContent('Stream unavailable');
});
