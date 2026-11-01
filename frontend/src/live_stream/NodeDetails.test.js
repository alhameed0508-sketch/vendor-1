import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import NodeDetails from './NodeDetails';

const base = {
  id: 'A',
  stats: { inCount: 1, inAmount: 25000, outCount: 2, outAmount: 24000 },
  ring: { caseId: 'CASE-1', risk: 0.82, members: ['A', 'B'] },
  counterparties: ['B', 'C'],
  onClose: jest.fn(),
};

describe('NodeDetails', () => {
  it('shows status, case, money flow and counterparties', () => {
    render(<NodeDetails {...base} />);
    expect(screen.getByRole('dialog', { name: /account a/i })).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('CASE-1')).toBeInTheDocument();
    expect(screen.getByText('₹25,000')).toBeInTheDocument();
    expect(screen.getByText('B, C')).toBeInTheDocument();
  });

  it('says plainly when the account is not in a flagged ring', () => {
    render(<NodeDetails {...base} ring={null} />);
    expect(screen.getByText(/not in a flagged ring/i)).toBeInTheDocument();
  });

  it('closes with the button or Escape', () => {
    const onClose = jest.fn();
    render(<NodeDetails {...base} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
