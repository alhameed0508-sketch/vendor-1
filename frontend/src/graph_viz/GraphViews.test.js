import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import GraphVerdict from './GraphVerdict';
import AccountList from './AccountList';
import GraphLegend from './GraphLegend';

const NODES = [
  { account_id: 'ACC_0001', role: 'MULE', smurf_score: 0.7 },
  { account_id: 'ACC_0002', role: 'SOURCE', smurf_score: 0.9 },
];
const EDGES = [{ from_account: 'ACC_0002', to_account: 'ACC_0001', total_amount: 450000, pattern: 'SMURFING' }];

describe('GraphVerdict', () => {
  it('shows the headline as a heading and the figures beneath it', () => {
    render(<GraphVerdict verdict={{
      headline: 'Likely mule ring',
      figures: { accounts: 5, flaggedAmount: 700000, flaggedTransfers: 3, highestRisk: 0.9 },
    }} />);
    expect(screen.getByRole('heading', { name: 'Likely mule ring' })).toBeInTheDocument();
    expect(screen.getByText('₹7.0L')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();
    expect(screen.getByText('Flagged transfers')).toBeInTheDocument();
  });

  it('names the risk figure after the account, so it is not read as the alert score', () => {
    render(<GraphVerdict verdict={{
      headline: 'Likely mule ring',
      figures: { accounts: 5, flaggedAmount: 700000, flaggedTransfers: 3, highestRisk: 0.9 },
    }} />);
    expect(screen.getByText('Riskiest account')).toBeInTheDocument();
  });
});

describe('AccountList', () => {
  it('lists accounts riskiest first with full role names', () => {
    render(<AccountList nodes={NODES} edges={EDGES} onSelect={jest.fn()} />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Source')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Mule')).toBeInTheDocument();
    expect(within(rows[0]).getByText('₹4.5L')).toBeInTheDocument();
  });

  it('opens an account when its id is pressed', async () => {
    const onSelect = jest.fn();
    render(<AccountList nodes={NODES} edges={EDGES} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole('button', { name: 'ACC_0001' }));
    expect(onSelect).toHaveBeenCalledWith(NODES[0]);
  });
});

describe('GraphLegend', () => {
  it('names every role and both kinds of transfer', () => {
    render(<GraphLegend />);
    ['Source', 'Aggregator', 'Mule', 'Legitimate', 'Flagged transfer', 'Other transfer'].forEach(label =>
      expect(screen.getByText(label)).toBeInTheDocument());
  });
});
