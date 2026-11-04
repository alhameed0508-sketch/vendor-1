import { drawGraph } from './drawGraph';

const T10 = '2026-10-31T10:00:00Z';
const T12 = '2026-10-31T12:00:00Z';
const NODES = [
  { account_id: 'AC00001111', role: 'SOURCE', smurf_score: 0.9 },
  { account_id: 'AC00002222', role: 'AGGREGATOR', smurf_score: 0.8 },
  { account_id: 'AC00003333', role: 'MULE', smurf_score: 0.7 },
  { account_id: 'AC00004444', role: 'LEGITIMATE', smurf_score: 0.05 },
];
const EDGES = [
  { from_account: 'AC00001111', to_account: 'AC00002222', pattern: 'SMURFING', total_amount: 500000, timestamps: [T10] },
  { from_account: 'AC00002222', to_account: 'AC00003333', pattern: 'OBSERVED', total_amount: 100000, timestamps: [T12] },
  { from_account: 'AC00003333', to_account: 'AC00004444', pattern: 'NORMAL', total_amount: 20000, timestamps: [T12] },
];

let container;
let svgEl;
let graph;
const onSelect = jest.fn();
const onHop = jest.fn();

const draw = (nodes = NODES, edges = EDGES) => {
  graph = drawGraph({ svgEl, container, nodes, edges, onSelect, onHop });
  return graph;
};
const edgePaths = () => [...svgEl.querySelectorAll('path[marker-end]')];
const nodeEl = id => svgEl.querySelector(`.graph-node[aria-label*="${id}"]`);

beforeEach(() => {
  jest.useFakeTimers();
  onSelect.mockReset();
  onHop.mockReset();
  container = document.createElement('div');
  svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  container.appendChild(svgEl);
  document.body.appendChild(container);
});

afterEach(() => {
  graph?.destroy();
  graph = null;
  container.remove();
  delete window.matchMedia;
  jest.useRealTimers();
});

describe('drawGraph', () => {
  it('draws one focusable node per account, named by role and risk', () => {
    draw();
    const nodes = svgEl.querySelectorAll('.graph-node');
    expect(nodes).toHaveLength(4);
    expect(nodeEl('AC00001111').getAttribute('aria-label')).toBe('Source account AC00001111, risk 90%');
    expect(nodeEl('AC00001111').getAttribute('tabindex')).toBe('0');
  });

  it('labels only source accounts, by their last four digits', () => {
    draw();
    expect(nodeEl('AC00001111').querySelector('text').textContent).toBe('···1111');
    expect(nodeEl('AC00003333').querySelector('text')).toBeNull();
  });

  it('draws flagged transfers solid and other transfers dashed', () => {
    draw();
    const [smurf, observed, normal] = edgePaths();
    expect(smurf.getAttribute('stroke-dasharray')).toBeNull();
    expect(observed.getAttribute('stroke-dasharray')).toBeNull();
    expect(normal.getAttribute('stroke-dasharray')).toBe('4 4');
  });

  it('selects an account from the keyboard', () => {
    draw();
    nodeEl('AC00003333').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ account_id: 'AC00003333' }));
  });

  it('replays the money flow after opening, narrating each hop and then clearing', () => {
    draw();
    jest.advanceTimersByTime(5000);
    expect(onHop.mock.calls).toEqual([[{ current: 1, total: 2 }], [{ current: 2, total: 2 }], [null]]);
  });

  it('does not replay on its own when the viewer asks for reduced motion', () => {
    window.matchMedia = () => ({ matches: true });
    draw();
    jest.advanceTimersByTime(5000);
    expect(onHop).not.toHaveBeenCalled();
  });

  it('dims transfers outside the chosen time range', () => {
    const at10 = new Date(T10).getTime();
    draw().setTimeRange({ start: at10 - 1, end: at10 + 1 });
    const [inside, outside] = edgePaths();
    expect(inside.getAttribute('stroke-opacity')).toBe('0.8');
    expect(outside.getAttribute('stroke-opacity')).toBe('0.06');
  });

  it('shows account details in the tooltip as text, never as HTML', () => {
    const hostile = [{ account_id: '<img src=x onerror=alert(1)>', role: 'MULE', smurf_score: 0.6, city: '<b>x</b>' }];
    draw(hostile, []);
    svgEl.querySelector('.graph-node').dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    const tip = container.querySelector('.graph-tooltip');
    expect(tip.querySelector('img, b')).toBeNull();
    expect(tip.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it('stops its timers and removes the tooltip when destroyed', () => {
    draw().destroy();
    jest.advanceTimersByTime(5000);
    expect(onHop).not.toHaveBeenCalled();
    expect(container.querySelector('.graph-tooltip')).toBeNull();
  });
});
