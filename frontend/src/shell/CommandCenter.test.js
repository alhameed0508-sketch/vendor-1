import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CommandCenter from './CommandCenter';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const MODULES = [
  { module_id: 'mule', name: 'Mule account detection', status: 'IMPLEMENTED', workspace_path: '/', findings: 4 },
  { module_id: 'upi', name: 'UPI and digital payments', status: 'PARTIAL', workspace_path: null, findings: 0, skipped_signals: [{ rule_code: 'R18', reason: "no transaction in this data carries 'device_id'" }] },
  { module_id: 'loan', name: 'Loan and lending fraud', status: 'PLANNED', workspace_path: null, findings: null },
];

const serve = data => apiFetch.mockResolvedValue({ json: () => Promise.resolve({ data }) });
const payload = (over = {}) => ({
  alerts: { total: 4, by_severity: { CRITICAL: 1, HIGH: 2, MEDIUM: 1 }, by_status: { OPEN: 3, RESOLVED: 1 } },
  escalations: { pending: 2 },
  modules: MODULES,
  ...over,
});
const renderPage = () => render(<MemoryRouter><CommandCenter /></MemoryRouter>);
const stat = label => screen.getByText(label, { selector: '.meta-label' }).closest('.premium-card');

beforeEach(() => apiFetch.mockReset());

test('shows alert and escalation counts from the API', async () => {
  serve(payload());
  renderPage();
  await screen.findByText('Mule account detection');
  expect(within(stat('Alerts')).getByText('4')).toBeInTheDocument();
  expect(within(stat('Critical')).getByText('1')).toBeInTheDocument();
  expect(within(stat('High')).getByText('2')).toBeInTheDocument();
  expect(within(stat('Pending escalations')).getByText('2')).toBeInTheDocument();
});

test('zero alerts shows zeros, not an error or a missing tile', async () => {
  serve(payload({ alerts: { total: 0, by_severity: {}, by_status: {} }, escalations: { pending: 0 } }));
  renderPage();
  await screen.findByText('Mule account detection');
  expect(within(stat('Critical')).getByText('0')).toBeInTheDocument();
  expect(within(stat('High')).getByText('0')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('only a module that has a workspace is a link', async () => {
  serve(payload());
  renderPage();
  const mule = (await screen.findByText('Mule account detection')).closest('article');
  expect(within(mule).getByRole('link', { name: /open workspace/i })).toHaveAttribute('href', '/');
  const upi = screen.getByText('UPI and digital payments').closest('article');
  expect(within(upi).queryByRole('link')).not.toBeInTheDocument();
});

test('every module shows its status as text, and a module without findings says so', async () => {
  serve(payload());
  renderPage();
  await screen.findByText('Mule account detection');
  const badge = text => screen.getByText(text, { selector: '.status-badge' });
  expect(badge('Implemented')).toBeInTheDocument();
  expect(badge('Partial')).toBeInTheDocument();
  expect(badge('Planned')).toBeInTheDocument();
  const loan = screen.getByText('Loan and lending fraud').closest('article');
  expect(within(loan).getByText(/no findings source yet/i)).toBeInTheDocument();
  expect(within(loan).queryByText('0')).not.toBeInTheDocument();
});

test('a module with zero findings shows 0, and names the signals that could not run', async () => {
  serve(payload());
  renderPage();
  await screen.findByText('Mule account detection');
  const upi = screen.getByText('UPI and digital payments').closest('article');
  expect(within(upi).getByText('0')).toBeInTheDocument();
  expect(within(upi).getByText(/R18/)).toBeInTheDocument();
  expect(within(upi).getByText(/device_id/)).toBeInTheDocument();
});

test('a failed request shows an error message, not a blank page', async () => {
  apiFetch.mockRejectedValue(new Error('network'));
  renderPage();
  expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
});

test('says so when the data is synthetic', async () => {
  serve(payload({ data_source: 'synthetic' }));
  renderPage();
  expect(await screen.findByRole('status')).toHaveTextContent(/synthetic demonstration data/i);
});

test('shows no synthetic notice for data that was loaded', async () => {
  serve(payload({ data_source: 'loaded' }));
  renderPage();
  await screen.findByText('Mule account detection');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
