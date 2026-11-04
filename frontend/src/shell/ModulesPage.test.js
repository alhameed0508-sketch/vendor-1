import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ModulesPage from './ModulesPage';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('./LivePrevention', () => () => <div data-testid="live-prevention" />);

const MODULES = [
  {
    module_id: 'upi', name: 'UPI and digital payments', purpose: 'Spot suspicious UPI payments.', status: 'PARTIAL',
    workspace_path: '/modules/upi', data_requirements: ['upi_id per account'],
    capabilities: [
      { name: 'Velocity and split-payment rules', status: 'IMPLEMENTED', note: '' },
      { name: 'High-risk UPI handle pattern', status: 'PARTIAL', note: 'Needs a upi_id on each account.' },
    ],
  },
  {
    module_id: 'loan', name: 'Loan and lending fraud', purpose: 'Not built yet.', status: 'PLANNED',
    workspace_path: null, data_requirements: ['loan applications'],
    capabilities: [{ name: 'Fund diversion', status: 'PLANNED', note: 'Needs disbursement data.' }],
  },
];
const FINDINGS = {
  upi: {
    kind: 'rules', data_source: 'synthetic', findings_total: 7, accounts_flagged: 5, rows_considered: 120,
    by_rule: [{ rule_code: 'R14', label: 'Velocity spike', findings: 5, accounts: 4 }, { rule_code: 'R17', label: 'Split payments', findings: 2, accounts: 2 }],
    signals_skipped: [{ rule_code: 'R15', reason: "no account in this data carries 'upi_id'" }],
  },
  loan: { kind: 'none', findings_total: null, data_source: 'synthetic' },
};

const respond = data => ({ ok: true, json: () => Promise.resolve({ data }) });

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockImplementation(url => {
    const m = url.match(/\/api\/v1\/modules\/([^/]+)\/findings$/);
    return Promise.resolve(m ? respond(FINDINGS[m[1]]) : respond({ modules: MODULES }));
  });
});

const renderPage = () => render(<MemoryRouter><ModulesPage /></MemoryRouter>);

test('opens with the live payment panel, then the modules', async () => {
  renderPage();
  await screen.findByText('UPI and digital payments');
  const live = screen.getByTestId('live-prevention');
  expect(live.compareDocumentPosition(screen.getByRole('heading', { name: 'Modules' }))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
});

test('each module shows what it found, broken down by rule, instead of a wall of text', async () => {
  renderPage();
  const card = await screen.findByRole('article', { name: 'UPI and digital payments' });
  expect(await within(card).findByText('7')).toBeInTheDocument();
  expect(within(card).getByText(/5 accounts across 120 payments/)).toBeInTheDocument();
  const bars = within(card).getByRole('list', { name: /findings breakdown/ });
  expect(within(bars).getByText('R14 Velocity spike')).toBeInTheDocument();
  expect(within(card).getByText(/could not run on this data \(R15\)/)).toBeInTheDocument();
  expect(within(card).getByText('1 implemented', { exact: false })).toBeInTheDocument();
});

test('capability notes are still there, folded away', async () => {
  renderPage();
  const card = await screen.findByRole('article', { name: 'UPI and digital payments' });
  expect(within(card).getByText('Needs a upi_id on each account.').closest('details')).not.toHaveAttribute('open');
  expect(within(card).getByText('upi_id per account')).toBeInTheDocument();
});

test('a module with a workspace links to it; one without has no link', async () => {
  renderPage();
  const upi = await screen.findByRole('article', { name: 'UPI and digital payments' });
  expect(within(upi).getByRole('link', { name: /open workspace/i })).toHaveAttribute('href', '/modules/upi');
  const loan = screen.getByRole('article', { name: 'Loan and lending fraud' });
  expect(await within(loan).findByText(/No findings source yet/)).toBeInTheDocument();
  expect(within(loan).queryByRole('link', { name: /open workspace/i })).not.toBeInTheDocument();
});

test('says when the findings come from synthetic data', async () => {
  renderPage();
  expect(await screen.findByText(/synthetic demonstration data/i)).toBeInTheDocument();
});


test('a module with nothing in its scope says so instead of "0 accounts across 0 payments"', async () => {
  apiFetch.mockImplementation(url => {
    const m = url.match(/\/api\/v1\/modules\/([^/]+)\/findings$/);
    const empty = { ...FINDINGS.upi, findings_total: 0, accounts_flagged: 0, rows_considered: 0, by_rule: [] };
    return Promise.resolve(m ? respond(m[1] === 'upi' ? empty : FINDINGS[m[1]]) : respond({ modules: MODULES }));
  });
  renderPage();
  const card = await screen.findByRole('article', { name: 'UPI and digital payments' });
  expect(await within(card).findByText(/no payments in its scope/)).toBeInTheDocument();
  expect(within(card).queryByText(/across 0 payments/)).not.toBeInTheDocument();
});
