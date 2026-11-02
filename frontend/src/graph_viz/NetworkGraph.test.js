import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import NetworkGraph from './NetworkGraph';
import { drawGraph } from './drawGraph';

// d3 zoom needs SVG layout APIs jsdom lacks; the drawing itself is checked in the browser.
jest.mock('./drawGraph', () => ({ drawGraph: jest.fn() }));

const NODES = [
  { account_id: 'ACC_S', role: 'SOURCE', smurf_score: 0.45 },
  { account_id: 'ACC_A', role: 'AGGREGATOR', smurf_score: 0.48 },
  { account_id: 'ACC_M', role: 'MULE', smurf_score: 0.47 },
];
const EDGES = [
  { from_account: 'ACC_S', to_account: 'ACC_A', total_amount: 300000, pattern: 'OBSERVED' },
  { from_account: 'ACC_A', to_account: 'ACC_M', total_amount: 200000, pattern: 'OBSERVED' },
];

let controls;
beforeEach(() => {
  controls = {
    zoomBy: jest.fn(), showAll: jest.fn(), focusRiskiest: jest.fn(),
    replay: jest.fn(), setTimeRange: jest.fn(), destroy: jest.fn(),
  };
  drawGraph.mockReset().mockReturnValue(controls);
});

const renderGraph = props =>
  render(<MemoryRouter><NetworkGraph nodes={NODES} edges={EDGES} {...props} /></MemoryRouter>);

describe('NetworkGraph', () => {
  it('leads with the verdict for the accounts it is given', () => {
    renderGraph();
    expect(screen.getByRole('heading', { name: 'Likely mule ring' })).toBeInTheDocument();
    expect(screen.getByText('₹5L')).toBeInTheDocument();
  });

  it('replays the money flow on request', async () => {
    renderGraph();
    await userEvent.click(screen.getByRole('button', { name: 'Replay money flow' }));
    expect(controls.replay).toHaveBeenCalled();
  });

  it('wires the zoom buttons to the drawing', async () => {
    renderGraph();
    await userEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
    await userEvent.click(screen.getByRole('button', { name: 'Show all' }));
    expect(controls.zoomBy).toHaveBeenCalledWith(1.3);
    expect(controls.showAll).toHaveBeenCalled();
  });

  it('switches to a table of the same accounts and opens one with its reasons', async () => {
    renderGraph();
    await userEvent.click(screen.getByRole('button', { name: 'List' }));
    expect(screen.queryByRole('button', { name: 'Replay money flow' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'ACC_M' }));
    expect(screen.getByText('Mule account')).toBeInTheDocument();
    expect(screen.getByText('Why flagged')).toBeInTheDocument();
  });

  it('passes the time range through and tears the drawing down on unmount', () => {
    const range = { start: 1, end: 2 };
    const { rerender, unmount } = renderGraph();
    rerender(<MemoryRouter><NetworkGraph nodes={NODES} edges={EDGES} timeRange={range} /></MemoryRouter>);
    expect(controls.setTimeRange).toHaveBeenLastCalledWith(range);
    unmount();
    expect(controls.destroy).toHaveBeenCalled();
  });

  it('falls back to the demo graph when no accounts are given', () => {
    render(<MemoryRouter><NetworkGraph nodes={[]} edges={[]} /></MemoryRouter>);
    expect(drawGraph.mock.calls[0][0].nodes.length).toBeGreaterThan(0);
  });
});
