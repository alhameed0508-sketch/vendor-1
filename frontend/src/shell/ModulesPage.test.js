import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ModulesPage from './ModulesPage';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const MODULES = [
  {
    module_id: 'upi', name: 'UPI and digital payments', purpose: 'Spot suspicious UPI payments.', status: 'PARTIAL',
    workspace_path: null, data_requirements: ['upi_id per account'],
    capabilities: [
      { name: 'Velocity and split-payment rules', status: 'IMPLEMENTED', note: '' },
      { name: 'Session and IP anomalies', status: 'PLANNED', note: 'No session or IP fields in any data source.' },
    ],
  },
];

beforeEach(() => apiFetch.mockResolvedValue({ json: () => Promise.resolve({ data: { modules: MODULES } }) }));

test('lists each capability with its status and, when missing, why', async () => {
  render(<MemoryRouter><ModulesPage /></MemoryRouter>);
  const card = (await screen.findByText('UPI and digital payments')).closest('article');
  expect(within(card).getByText('Velocity and split-payment rules')).toBeInTheDocument();
  expect(within(card).getByText('No session or IP fields in any data source.')).toBeInTheDocument();
  expect(within(card).getByText('upi_id per account')).toBeInTheDocument();
});

test('does not offer a workspace link for a module that has none', async () => {
  render(<MemoryRouter><ModulesPage /></MemoryRouter>);
  await screen.findByText('UPI and digital payments');
  expect(screen.queryByRole('link', { name: /open workspace/i })).not.toBeInTheDocument();
});
