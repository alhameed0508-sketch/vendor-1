import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

describe('CaseCard review actions', () => {
  it('calls onReview with the case id and decision', () => {
    const onReview = jest.fn();
    render(<CaseCard ring={ring} onReview={onReview} />);
    fireEvent.click(screen.getByRole('button', { name: /confirm mule ring/i }));
    expect(onReview).toHaveBeenCalledWith('CASE-AB12', 'confirmed');
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(onReview).toHaveBeenCalledWith('CASE-AB12', 'dismissed');
  });

  it('shows the recorded decision and says it is not saved', () => {
    render(<CaseCard ring={ring} decision="confirmed" onReview={() => {}} />);
    expect(screen.getByText(/Confirmed by reviewer/)).toBeInTheDocument();
    expect(screen.getByText(/demo only/i)).toBeInTheDocument();
  });
});
