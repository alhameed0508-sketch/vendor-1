import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AlertDetail from './AlertDetail';
import { apiFetch } from '../auth/api';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn(), resolveUrl: u => u, getToken: () => null }));
jest.mock('../graph_viz/NetworkGraph', () => () => null);
jest.mock('../graph_viz/TimelineSlider', () => () => null);
jest.mock('../explainability/ExplainabilityPanel', () => () => null);
jest.mock('../genai/InvestigationChat', () => () => null);
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

// A link from a fraud complaint can outlive its alert, so the server answers with an error envelope.
const NOT_FOUND = {
  success: false, data: null,
  error: { code: 'NOT_FOUND', message: 'Alert not found: ALT_GONE', details: 'resource=Alert, id=ALT_GONE' },
};

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue({ ok: false, status: 404, json: () => Promise.resolve(NOT_FOUND) });
});

it('says the alert was not found instead of crashing when the server has no such alert', async () => {
  render(
    <MemoryRouter initialEntries={['/alert/ALT_GONE']}>
      <Routes><Route path="/alert/:alertId" element={<AlertDetail />} /></Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText('Alert not found.')).toBeInTheDocument();
});
