import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import GraphCanvas from './GraphCanvas';

const props = {
  edges: [
    { id: 'T1', from: 'A', to: 'B', flagged: true },
    { id: 'T2', from: 'C', to: 'D', flagged: false },
  ],
  rings: { 'CASE-1': { caseId: 'CASE-1', members: ['A', 'B', 'E'], risk: 0.6 } },
  stats: {},
  selected: null,
  onSelect: jest.fn(),
};

describe('GraphCanvas', () => {
  it('draws a focusable node per account and a legend', () => {
    render(<GraphCanvas {...props} />);
    expect(screen.getAllByRole('button', { name: /account/i })).toHaveLength(5);
    expect(screen.getByText('Ring, high risk')).toBeInTheDocument();
    expect(screen.getByText('Ring, review')).toBeInTheDocument();
  });

  it('selects an account by click or keyboard', () => {
    const onSelect = jest.fn();
    render(<GraphCanvas {...props} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: 'Account A' }));
    expect(onSelect).toHaveBeenCalledWith('A');
    fireEvent.keyDown(screen.getByRole('button', { name: 'Account C' }), { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('C');
  });

  it('highlights links of the selected account and dims the rest', () => {
    const { container } = render(<GraphCanvas {...props} selected="A" />);
    expect(container.querySelectorAll('.live-graph__link--active')).toHaveLength(1);
    expect(container.querySelectorAll('.live-graph__link--dim')).toHaveLength(1);
  });
});
