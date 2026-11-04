import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import EntityView from './EntityView';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const DATA = {
  entity: { kind: 'account', entity_id: 'ACC-7' },
  modules: [
    { module_id: 'mule', score: 0.87, evidence: ['AL1: Cluster of 3 accounts'] },
    { module_id: 'upi', score: null, evidence: ['R18: Shared device across multiple accounts'] },
  ],
  links: [
    { other: { kind: 'account', entity_id: 'ACC-9' }, basis: 'same CIF_ID C1', confidence: 'VERIFIED' },
    { other: { kind: 'account', entity_id: 'ACC-3' }, basis: 'similar holder name, no shared verified identifier', confidence: 'POSSIBLE' },
  ],
};

const renderAt = () =>
  render(
    <MemoryRouter initialEntries={['/entities/ACC-7']}>
      <Routes><Route path="/entities/:entityId" element={<EntityView />} /></Routes>
    </MemoryRouter>
  );

beforeEach(() => apiFetch.mockReset());

test('shows each module as its own panel with its own score and evidence', async () => {
  apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: DATA }) });
  renderAt();
  const mule = (await screen.findByText('mule', { selector: '.entity-module__name' })).closest('section');
  expect(within(mule).getByText('0.87')).toBeInTheDocument();
  expect(within(mule).getByText(/Cluster of 3 accounts/)).toBeInTheDocument();
  const upi = screen.getByText('upi', { selector: '.entity-module__name' }).closest('section');
  expect(within(upi).getByText(/no score/i)).toBeInTheDocument();
  expect(screen.queryByText(/combined|overall|average/i)).not.toBeInTheDocument();
});

test('links show their confidence as text and are never described as the same party', async () => {
  apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: DATA }) });
  renderAt();
  expect(await screen.findByText('Verified')).toBeInTheDocument();
  expect(screen.getByText('Possible')).toBeInTheDocument();
  expect(screen.getByText(/similar holder name/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'ACC-9' })).toHaveAttribute('href', '/entities/ACC-9');
});

test('an entity with no findings says so instead of showing an empty page', async () => {
  apiFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ data: { ...DATA, modules: [], links: [] } }),
  });
  renderAt();
  expect(await screen.findByText(/no module has flagged this account/i)).toBeInTheDocument();
});

test('a failed request shows an error message', async () => {
  apiFetch.mockRejectedValue(new Error('network'));
  renderAt();
  expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
});
