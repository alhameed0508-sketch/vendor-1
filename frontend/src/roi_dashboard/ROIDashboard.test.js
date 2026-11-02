import { render, screen } from '@testing-library/react';
import { apiFetch } from '../auth/api';
import ROIDashboard from './ROIDashboard';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const BODIES = {
  '/api/v1/kpi': { data: { fraud_prevented_crore: 1.79, total_alerts: 9 } },
  '/api/v1/feedback/stats': { data: null },
  '/api/v1/roi': { data: { detection_breakdown: [{ pattern: 'SMURF', count: 4 }, { pattern: 'FAN_OUT', count: 2 }] } },
};

beforeEach(() => {
  apiFetch.mockImplementation(url => Promise.resolve({ json: () => Promise.resolve(BODIES[url]) }));
});

afterEach(() => apiFetch.mockReset());

describe('ROIDashboard', () => {
  it('does not claim to be live, because it loads its figures once', async () => {
    render(<ROIDashboard />);
    expect(await screen.findByRole('heading', { name: 'ROI Analytics' })).toBeInTheDocument();
    expect(screen.queryByText(/^live$/i)).toBeNull();
  });

  it('lists detections by pattern with their counts', async () => {
    render(<ROIDashboard />);
    expect(await screen.findByText('SMURF')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('FAN_OUT')).toBeInTheDocument();
  });
});
