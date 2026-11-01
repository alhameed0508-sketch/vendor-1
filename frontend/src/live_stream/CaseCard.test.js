import React from 'react';
import { render, screen } from '@testing-library/react';
import CaseCard from './CaseCard';

const ring = {
  caseId: 'CASE-AB12',
  members: ['A1', 'B1', 'C1'],
  reasons: ['A1: RAPID_PASS_THROUGH', 'CC01: dense ring'],
  risk: 0.82,
  openedAt: 4,
  payments: [
    { id: 'T1', from: 'A1', to: 'B1', amount: 25000, risk: 0.6 },
    { id: 'T2', from: 'B1', to: 'C1', amount: 24000, risk: 0.82 },
  ],
};

describe('CaseCard', () => {
  it('shows an empty state without a ring', () => {
    render(<CaseCard ring={null} />);
    expect(screen.getByText(/No case open yet/)).toBeInTheDocument();
  });

  it('shows band, reason chips and the flagged payment timeline', () => {
    render(<CaseCard ring={ring} />);
    expect(screen.getByText('CASE-AB12')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('A1: RAPID_PASS_THROUGH')).toBeInTheDocument();
    const rows = screen.getAllByRole('listitem').filter((li) => li.textContent.includes('→'));
    expect(rows).toHaveLength(2);
    expect(screen.getByText(/not blocked/)).toBeInTheDocument();
  });
});
