import React from 'react';
import { render, screen } from '@testing-library/react';
import FlowView from './FlowView';

const payments = [
  { id: 'T1', from: 'S', to: 'M', amount: 1000 },
  { id: 'T2', from: 'M', to: 'A', amount: 900 },
];

it('draws one labelled arc per payment and one label per account', () => {
  const { container } = render(<FlowView payments={payments} />);
  expect(container.querySelectorAll('path.live-stream__flow-link')).toHaveLength(2);
  ['S', 'M', 'A'].forEach((id) => expect(screen.getByText(id)).toBeInTheDocument());
  expect(screen.getByRole('img')).toHaveAccessibleName(/money flow/i);
});

it('renders nothing for an empty case', () => {
  const { container } = render(<FlowView payments={[]} />);
  expect(container).toBeEmptyDOMElement();
});
