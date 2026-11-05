import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ModuleWorkspace from './ModuleWorkspace';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));
jest.mock('./LivePrevention', () => () => <div data-testid="live-prevention" />);

const MULE = {
  module_id: 'mule', name: 'Mule account detection', status: 'IMPLEMENTED', purpose: 'Find mule rings.',
  workspace_path: '/modules/mule', data_requirements: [],
  capabilities: [{ name: 'Ring detection', status: 'IMPLEMENTED', note: '' }],
};
const LOAN = {
  module_id: 'loan', name: 'Loan and lending fraud', status: 'PLANNED', purpose: 'Not built yet.',
  workspace_path: null, data_requirements: ['Loan application feed'],
  capabilities: [{ name: 'Disbursement monitoring', status: 'PLANNED', note: 'No loan data source.' }],
};
const AML = {
  module_id: 'transaction_aml', name: 'Transaction and AML intelligence', status: 'PARTIAL', purpose: 'Spot layering.',
  workspace_path: '/modules/transaction_aml', data_requirements: ['transactions'],
  capabilities: [{ name: 'Circular fund flow', status: 'IMPLEMENTED', note: 'CF01' }],
};
const FINDINGS = {
  mule: {
    kind: 'rules', data_source: 'live', live_payments: 400, findings_total: 9, accounts_flagged: 12, rows_considered: 400,
    cases: 2, signals_run: [], signals_skipped: [],
    by_rule: [{ rule_code: 'CC01', label: 'Dense transaction cluster', findings: 9, accounts: 12 }],
    findings: [{ account_id: 'bc1qmule', rule_code: 'CC01', explanation: 'CC01: Dense transaction cluster', score: null }],
  },
  loan: { kind: 'none', findings_total: null, data_source: 'live', live_payments: 400 },
  transaction_aml: {
    kind: 'rules', data_source: 'live', live_payments: 400, findings_total: 4, accounts_flagged: 3, rows_considered: 400,
    signals_run: ['R06', 'R12', 'R14', 'CF01'], signals_skipped: [],
    by_rule: [{ rule_code: 'CF01', label: 'Circular fund flow', findings: 3, accounts: 3 }, { rule_code: 'R06', label: 'Structuring', findings: 1, accounts: 1 }],
    findings: [{ account_id: 'bc1qloop', rule_code: 'CF01', explanation: 'CF01: Circular fund flow: A -> B -> C -> A within 9.0 h', score: null }],
  },
};
const SPECS = { mule: MULE, loan: LOAN, transaction_aml: AML };

function serve(found = true, findings = FINDINGS) {
  apiFetch.mockImplementation(url => {
    const m = url.match(/\/api\/v1\/modules\/([^/?]+)(\/findings)?(\?.*)?$/);
    if (!found) return Promise.resolve({ ok: false, json: () => Promise.resolve({ error: { message: 'not found' } }) });
    const data = m[2] ? findings[m[1]] : SPECS[m[1]];
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ data }) });
  });
}

const renderAt = id =>
  render(
    <MemoryRouter initialEntries={[`/modules/${id}`]}>
      <Routes><Route path="/modules/:moduleId" element={<ModuleWorkspace />} /></Routes>
    </MemoryRouter>
  );

beforeEach(() => apiFetch.mockReset());

test('workspaces ask for live findings only', async () => {
  serve();
  renderAt('transaction_aml');
  await screen.findByRole('region', { name: 'Findings by rule' });
  expect(apiFetch).toHaveBeenCalledWith('/api/v1/modules/transaction_aml/findings?source=live');
  expect(screen.getByText(/last 400 real public payments\. No synthetic data\./)).toBeInTheDocument();
});

test('the mule workspace shows the live panel, what the live scorer held by reason, and the cases opened', async () => {
  serve();
  renderAt('mule');
  expect(await screen.findByRole('heading', { level: 1, name: 'Mule account detection' })).toBeInTheDocument();
  expect(screen.getByTestId('live-prevention')).toBeInTheDocument();
  const byRule = await screen.findByRole('region', { name: 'Findings by rule' });
  expect(within(byRule).getByText('CC01 Dense transaction cluster')).toBeInTheDocument();
  expect(screen.getByText('Cases opened').closest('.premium-card')).toHaveTextContent('2');
  expect(screen.getByText('Payments held').closest('.premium-card')).toHaveTextContent('9');
});

test('the mule workspace keeps its existing pages one click away', async () => {
  serve();
  renderAt('mule');
  await screen.findByRole('heading', { level: 1, name: 'Mule account detection' });
  expect(screen.getByRole('link', { name: 'Alerts' })).toHaveAttribute('href', '/');
  expect(screen.getByRole('link', { name: 'Triage' })).toHaveAttribute('href', '/queue');
  expect(screen.getByRole('link', { name: 'Network' })).toHaveAttribute('href', '/network');
  expect(screen.getByRole('link', { name: 'Live stream' })).toHaveAttribute('href', '/live');
});

test('a rule module shows findings by rule and the flagged live accounts, which have no bank entity page', async () => {
  serve();
  renderAt('transaction_aml');
  const byRule = await screen.findByRole('region', { name: 'Findings by rule' });
  expect(within(byRule).getByText('CF01 Circular fund flow')).toBeInTheDocument();
  const table = screen.getByRole('region', { name: 'Flagged accounts' });
  expect(within(table).getByText('bc1qloop')).toBeInTheDocument();
  expect(within(table).queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('Live payments considered')).toBeInTheDocument();
  expect(screen.queryByTestId('live-prevention')).not.toBeInTheDocument();
});

test('before live payments arrive, a workspace says how to start the feed', async () => {
  serve(true, { ...FINDINGS, transaction_aml: { ...FINDINGS.transaction_aml, live_payments: 0, rows_considered: 0, by_rule: [], findings: [] } });
  renderAt('transaction_aml');
  expect(await screen.findByText(/open Detection modules to start the feed/)).toBeInTheDocument();
});

test('a planned module shows its status, its gaps and no working links', async () => {
  serve();
  renderAt('loan');
  expect(await screen.findByRole('heading', { level: 1, name: 'Loan and lending fraud' })).toBeInTheDocument();
  const header = screen.getByRole('heading', { level: 1 }).closest('.page-header');
  expect(within(header).getByText('Planned')).toBeInTheDocument();
  expect(await screen.findByText(/No findings source yet/)).toBeInTheDocument();
  expect(screen.getByText('No loan data source.')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Alerts' })).not.toBeInTheDocument();
});

test('an unknown module shows a message, not a blank page', async () => {
  serve(false);
  renderAt('nope');
  expect(await screen.findByRole('alert')).toHaveTextContent(/could not find/i);
});

test('the workspace leads back to Detection modules and keeps its long text folded', async () => {
  serve();
  renderAt('mule');
  await screen.findByRole('heading', { level: 1, name: 'Mule account detection' });
  expect(screen.getByRole('link', { name: /detection modules/i })).toHaveAttribute('href', '/modules');
  expect(screen.getByText('What it can do').closest('details')).not.toHaveAttribute('open');
});
