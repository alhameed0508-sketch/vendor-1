import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { RankBars, SplitBar } from './Bars';

test('the split bar gives each part its share and states the numbers for screen readers', () => {
  render(<SplitBar label="Money" format={v => `Rs${v}`} segments={[
    { label: 'Passed', value: 75, tone: 'ok' }, { label: 'Held', value: 25, tone: 'held' },
  ]} />);
  expect(screen.getByRole('img')).toHaveAccessibleName('Money: Passed Rs75 (75%), Held Rs25 (25%)');
  expect(screen.getByText('75%')).toBeInTheDocument();
});

test('an empty split bar renders without dividing by zero', () => {
  render(<SplitBar label="Money" segments={[{ label: 'Passed', value: 0, tone: 'ok' }]} />);
  expect(screen.getByRole('img')).toHaveAccessibleName('Money: Passed 0 (0%)');
});

test('ranked bars list every item with its value; nothing to show renders nothing', () => {
  const { container, rerender } = render(<RankBars label="By rule" items={[{ label: 'R14', value: 5 }, { label: 'R06', value: 1 }]} />);
  const list = screen.getByRole('list', { name: 'By rule' });
  expect(within(list).getAllByRole('listitem')).toHaveLength(2);
  expect(within(list).getByText('5')).toBeInTheDocument();
  rerender(<RankBars label="By rule" items={[]} />);
  expect(container).toBeEmptyDOMElement();
});
