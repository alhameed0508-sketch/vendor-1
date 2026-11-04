import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ModuleWorkspace from './ModuleWorkspace';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

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
const renderAt = id =>
  render(
    <MemoryRouter initialEntries={[`/modules/${id}`]}>
      <Routes><Route path="/modules/:moduleId" element={<ModuleWorkspace />} /></Routes>
    </MemoryRouter>
  );

beforeEach(() => apiFetch.mockReset());

test('the mule workspace gathers its existing pages under one heading', async () => {
  apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: MULE }) });
  renderAt('mule');
  expect(await screen.findByRole('heading', { level: 1, name: 'Mule account detection' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Alerts' })).toHaveAttribute('href', '/');
  expect(screen.getByRole('link', { name: 'Triage' })).toHaveAttribute('href', '/queue');
  expect(screen.getByRole('link', { name: 'Network' })).toHaveAttribute('href', '/network');
  expect(screen.getByRole('link', { name: 'Live stream' })).toHaveAttribute('href', '/live');
});

test('a planned module shows its status, its gaps and no working links', async () => {
  apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: LOAN }) });
  renderAt('loan');
  expect(await screen.findByRole('heading', { level: 1, name: 'Loan and lending fraud' })).toBeInTheDocument();
  const header = screen.getByRole('heading', { level: 1 }).closest('.page-header');
  expect(within(header).getByText('Planned')).toBeInTheDocument();
  expect(screen.getByText('No loan data source.')).toBeInTheDocument();
  expect(screen.getByText('Loan application feed')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Alerts' })).not.toBeInTheDocument();
});

test('an unknown module shows a message, not a blank page', async () => {
  apiFetch.mockResolvedValue({ ok: false, json: () => Promise.resolve({ error: { message: 'not found' } }) });
  renderAt('nope');
  expect(await screen.findByRole('alert')).toHaveTextContent(/could not find/i);
});

test('the mule workspace has a visible way back and keeps its long text out of the way', async () => {
  apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: MULE }) });
  renderAt('mule');
  await screen.findByRole('heading', { level: 1, name: 'Mule account detection' });
  expect(screen.getByRole('link', { name: /command center/i })).toHaveAttribute('href', '/command-center');
  expect(screen.getByText('What it can do').closest('details')).not.toHaveAttribute('open');
});

test('a planned module keeps its gaps open, since it has nothing else to show', async () => {
  apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: LOAN }) });
  renderAt('loan');
  await screen.findByRole('heading', { level: 1, name: 'Loan and lending fraud' });
  expect(screen.getByText('What it can do').closest('details')).toHaveAttribute('open');
});
