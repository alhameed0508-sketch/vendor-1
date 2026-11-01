import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TimelineSlider from './TimelineSlider';

const at = hour => `2026-10-31T${String(hour).padStart(2, '0')}:00:00Z`;
const EDGES = [{ timestamps: [at(0)] }, { timestamps: [at(5)] }, { timestamps: [at(10)] }];
const ms = hour => new Date(at(hour)).getTime();

describe('TimelineSlider', () => {
  it('stays hidden when there is no time span to scrub', () => {
    const { container } = render(<TimelineSlider edges={[{ timestamps: [at(1)] }]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('counts the transfers inside the window', () => {
    render(<TimelineSlider edges={EDGES} />);
    expect(screen.getByText('3 of 3 transfers')).toBeInTheDocument();
  });

  it('narrows the window when the start handle moves', () => {
    const onChange = jest.fn();
    render(<TimelineSlider edges={EDGES} onChange={onChange} />);
    const [start] = screen.getAllByRole('slider');
    fireEvent.change(start, { target: { value: 60 } });
    expect(onChange).toHaveBeenLastCalledWith({ start: ms(6), end: ms(10) });
    expect(screen.getByText('1 of 3 transfers')).toBeInTheDocument();
  });

  it('resets to the full span', async () => {
    const onChange = jest.fn();
    render(<TimelineSlider edges={EDGES} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(onChange).toHaveBeenLastCalledWith({ start: ms(0), end: ms(10) });
  });

  it('plays a sliding window and returns to the full span at the end', () => {
    jest.useFakeTimers();
    const onChange = jest.fn();
    render(<TimelineSlider edges={EDGES} onChange={onChange} windowPct={50} stepPct={25} intervalMs={10} />);
    fireEvent.click(screen.getByRole('button', { name: 'Play timeline' }));
    expect(onChange).toHaveBeenLastCalledWith({ start: ms(0), end: ms(5) });
    act(() => { jest.advanceTimersByTime(100); });
    expect(onChange).toHaveBeenLastCalledWith({ start: ms(0), end: ms(10) });
    expect(screen.getByRole('button', { name: 'Play timeline' })).toBeInTheDocument();
    jest.useRealTimers();
  });
});
