import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BoardView from './BoardView';

const alerts = [
  { alert_id: 'A1', status: 'OPEN', severity: 'HIGH', risk_score: 0.9 },
  { alert_id: 'A2', status: 'OPEN', severity: 'LOW', risk_score: 0.2 },
  { alert_id: 'A3', status: 'RESOLVED', severity: 'LOW', risk_score: 0.1 },
];

const col = name => screen.getByRole('region', { name });

it('renders five columns with counts', () => {
  render(<BoardView alerts={alerts} onMove={jest.fn()} onOpen={jest.fn()} />);
  ['Open', 'Under Review', 'Resolved', 'False Positive', 'STR Filed'].forEach(n =>
    expect(col(n)).toBeInTheDocument());
  expect(within(col('Open')).getByText('2')).toBeInTheDocument();
  expect(within(col('Resolved')).getByText('A3')).toBeInTheDocument();
});

it('Move to select calls onMove with the target status', async () => {
  const onMove = jest.fn();
  render(<BoardView alerts={alerts} onMove={onMove} onOpen={jest.fn()} />);
  await userEvent.selectOptions(within(col('Open')).getAllByLabelText(/move to/i)[0], 'RESOLVED');
  expect(onMove).toHaveBeenCalledWith(alerts[0], 'RESOLVED');
});

it('dropping on the same column does not call onMove', () => {
  const onMove = jest.fn();
  render(<BoardView alerts={alerts} onMove={onMove} onOpen={jest.fn()} />);
  const card = screen.getByText('A1').closest('[draggable="true"]');
  const data = { setData: jest.fn(), getData: () => 'A1' };
  fireEvent.dragStart(card, { dataTransfer: data });
  fireEvent.drop(col('Open'), { dataTransfer: data });
  expect(onMove).not.toHaveBeenCalled();
});

it('dropping on another column calls onMove', () => {
  const onMove = jest.fn();
  render(<BoardView alerts={alerts} onMove={onMove} onOpen={jest.fn()} />);
  const card = screen.getByText('A1').closest('[draggable="true"]');
  const data = { setData: jest.fn(), getData: () => 'A1' };
  fireEvent.dragStart(card, { dataTransfer: data });
  fireEvent.drop(col('STR Filed'), { dataTransfer: data });
  expect(onMove).toHaveBeenCalledWith(alerts[0], 'STR_FILED');
});

it('shows legacy statuses in an Other column only when present', () => {
  const { rerender } = render(<BoardView alerts={alerts} onMove={jest.fn()} onOpen={jest.fn()} />);
  expect(screen.queryByRole('region', { name: 'Other' })).toBeNull();
  rerender(<BoardView alerts={[...alerts, { alert_id: 'A9', status: 'ESCALATED' }]}
                      onMove={jest.fn()} onOpen={jest.fn()} />);
  expect(within(col('Other')).getByText('A9')).toBeInTheDocument();
});
