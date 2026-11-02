import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import NodeDetailPanel, { riskLabel } from './NodeDetailPanel';

const renderPanel = props => render(<MemoryRouter><NodeDetailPanel onClose={jest.fn()} {...props} /></MemoryRouter>);

describe('riskLabel', () => {
  it.each([[0.24, 'Low'], [0.25, 'Medium'], [0.44, 'Medium'], [0.45, 'High'], [0.64, 'High'], [0.65, 'Critical']])(
    '%s -> %s', (score, label) => expect(riskLabel(score)).toBe(label));
  it('treats missing score as Low', () => expect(riskLabel(undefined)).toBe('Low'));
});

describe('NodeDetailPanel', () => {
  it('renders nothing without a node', () => {
    const { container } = renderPanel({ node: null });
    expect(container).toBeEmptyDOMElement();
  });

  it('shows account, role and risk label', () => {
    renderPanel({ node: { account_id: 'ACC_12345', role: 'MULE', smurf_score: 0.7 } });
    expect(screen.getByText('ACC_12345')).toBeInTheDocument();
    expect(screen.getByText('Mule account')).toBeInTheDocument();
    expect(screen.getByText(/Critical/)).toBeInTheDocument();
  });

  it('lists the reasons the account was flagged', () => {
    renderPanel({ node: { account_id: 'A', role: 'MULE' }, reasons: ['Account opened 12 days ago', 'KYC is pending'] });
    expect(screen.getByRole('heading', { name: 'Why flagged' })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('hides the reasons section when there are none', () => {
    renderPanel({ node: { account_id: 'A', role: 'LEGITIMATE' } });
    expect(screen.queryByRole('heading', { name: 'Why flagged' })).toBeNull();
  });

  it('links to the alert only when alert_id is present', () => {
    const { rerender } = renderPanel({ node: { account_id: 'A', smurf_score: 0.1 } });
    expect(screen.queryByRole('link')).toBeNull();
    rerender(<MemoryRouter><NodeDetailPanel onClose={jest.fn()} node={{ account_id: 'A', alert_id: 'ALT-9' }} /></MemoryRouter>);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/alert/ALT-9');
  });

  it('close button and Escape call onClose', async () => {
    const onClose = jest.fn();
    renderPanel({ node: { account_id: 'A' }, onClose });
    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
