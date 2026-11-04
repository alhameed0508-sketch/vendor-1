import { render, screen } from '@testing-library/react';
import { apiFetch } from '../auth/api';
import ROIDashboard from './ROIDashboard';

jest.mock('../auth/api', () => ({ apiFetch: jest.fn() }));

const KPI = {
  fraud_prevented_inr: 25000000, fraud_flagged_inr: 25000000, fraud_prevented_verified_inr: 10000000,
  fraud_prevented_crore: 2.5, total_alerts: 9,
  hours_saved: 27, manpower_saved_lakh: 0, false_positive_reduction_pct: null,
  roi_assumptions: { analyst_hourly_cost_inr: 0 },
};

const mockBodies = kpi => apiFetch.mockImplementation(url => Promise.resolve({ json: () => Promise.resolve({
  '/api/v1/kpi': { data: kpi },
  '/api/v1/feedback/stats': { data: null },
  '/api/v1/roi': { data: { detection_breakdown: [{ pattern: 'SMURF', count: 4 }, { pattern: 'FAN_OUT', count: 2 }] } },
}[url]) }));

const tile = label => screen.getByText(label).closest('.stat-card');

beforeEach(() => mockBodies(KPI));

afterEach(() => apiFetch.mockReset());

describe('ROIDashboard', () => {
  it('does not claim to be live, because it loads its figures once', async () => {
    render(<ROIDashboard />);
    expect(await screen.findByRole('heading', { name: 'ROI Analytics' })).toBeInTheDocument();
    expect(screen.queryByText(/^live$/i)).toBeNull();
  });

  it('describes the page without middle dots', async () => {
    render(<ROIDashboard />);
    const heading = await screen.findByRole('heading', { name: 'ROI Analytics' });
    expect(heading.nextSibling.textContent).not.toMatch('·');
  });

  it('lists detections by pattern in words, with their counts', async () => {
    render(<ROIDashboard />);
    expect(await screen.findByText('Smurf')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('Fan out')).toBeInTheDocument();
  });

  it('says there is no data yet instead of showing demo figures', async () => {
    apiFetch.mockImplementation(url => Promise.resolve({ json: () => Promise.resolve(
      url === '/api/v1/kpi' ? { data: KPI } : { data: { monthly_trends: [], detection_breakdown: [] } }) }));
    render(<ROIDashboard />);
    expect(await screen.findByText('No detections yet.')).toBeInTheDocument();
    expect(screen.getAllByText('No monthly figures yet.')).toHaveLength(2);
    expect(screen.queryByText('Smurfing')).toBeNull();
  });

  it('puts the KPI tiles in the shared grid that folds to two columns on phones', async () => {
    render(<ROIDashboard />);
    await screen.findByText('Fraud Flagged');
    expect(tile('Fraud Flagged').closest('.stat-grid')).not.toBeNull();
    expect(tile('Manpower Saved').closest('.stat-grid')).not.toBeNull();
  });

  it('separates flagged rupees from the investigator-verified prevented figure', async () => {
    render(<ROIDashboard />);
    await screen.findByText('Fraud Flagged');
    expect(tile('Fraud Flagged')).toHaveTextContent('₹2.5Cr');
    expect(tile('Fraud Flagged')).toHaveTextContent('Not verified');
    expect(tile('Fraud Prevented (verified)')).toHaveTextContent('₹1Cr');
    expect(tile('Fraud Prevented (verified)')).toHaveTextContent('Confirmed by investigators');
    expect(screen.queryByText('Fraud Prevented')).toBeNull();
  });

  it('says a figure is not measured instead of showing a made-up percentage', async () => {
    render(<ROIDashboard />);
    await screen.findByText('False Positive Reduction');
    expect(tile('False Positive Reduction')).toHaveTextContent('Not measured');
    expect(screen.queryByText('40%')).toBeNull();
    expect(tile('Investigation Time Saved')).toHaveTextContent('—');
  });

  it('asks for the analyst hourly cost instead of showing ₹0 next to hours freed', async () => {
    render(<ROIDashboard />);
    await screen.findByText('Manpower Saved');
    expect(tile('Manpower Saved')).toHaveTextContent('Cost not set');
    expect(tile('Manpower Saved')).toHaveTextContent('27 hours freed');
  });

  it('shows manpower saved in rupees once a cost is set', async () => {
    mockBodies({ ...KPI, manpower_saved_lakh: 4.5, false_positive_reduction_pct: 38, investigation_time_reduction_pct: 75,
      roi_assumptions: { analyst_hourly_cost_inr: 1500 } });
    render(<ROIDashboard />);
    await screen.findByText('Manpower Saved');
    expect(tile('Manpower Saved')).toHaveTextContent('₹4.5L');
    expect(tile('False Positive Reduction')).toHaveTextContent('38%');
    expect(tile('Investigation Time Saved')).toHaveTextContent('75%');
  });
});
