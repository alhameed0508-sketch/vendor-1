import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import IndiaMap, { cityRadius } from './IndiaMap';

jest.mock('d3', () => ({
  geoMercator: () => {
    const projection = coordinates => coordinates;
    projection.center = () => projection;
    projection.scale = () => projection;
    projection.translate = () => projection;
    return projection;
  },
  geoPath: () => () => 'M0,0Z',
}));

jest.mock('topojson-client', () => ({
  feature: (_topology, object) => ({
    type: 'FeatureCollection',
    features: object.geometries.map(geometry => ({
      type: 'Feature',
      properties: geometry.properties,
      geometry: { type: geometry.type, coordinates: [] },
    })),
  }),
}));

const topology = {
  type: 'Topology',
  objects: {
    states: {
      type: 'GeometryCollection',
      geometries: [
        { type: 'Polygon', arcs: [[0]], properties: { st_nm: 'Maharashtra', st_code: 'MH' } },
        { type: 'Polygon', arcs: [[0]], properties: { st_nm: 'Kerala', st_code: 'KL' } },
      ],
    },
  },
  arcs: [[[72, 8], [20, 0], [0, 28], [-20, 0], [0, -28]]],
};

const NODES = [
  { account_id: 'a1', city: 'Mumbai', role: 'SOURCE' },
  { account_id: 'a2', city: 'Delhi', role: 'MULE' },
  { account_id: 'a3', city: 'Chennai', role: 'LEGITIMATE' },
  { account_id: 'a4', city: 'Chennai', role: 'LEGITIMATE' },
];
const EDGES = [
  { from_account: 'a1', to_account: 'a2', pattern: 'SMURFING' },
  { from_account: 'a1', to_account: 'a2', pattern: 'SMURFING' },
  { from_account: 'a2', to_account: 'a3', pattern: 'NORMAL' },
];

const renderMap = props =>
  render(<IndiaMap nodes={NODES} edges={EDGES} stateAlertCounts={{ Maharashtra: 4 }} {...props} />);
const city = (container, name) => container.querySelector(`[aria-label^="${name},"]`);

describe('IndiaMap', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => topology });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('loads the bundled geography and draws each state', async () => {
    const { container } = renderMap();
    expect(screen.getByRole('img', { name: /India transaction flow map/i })).toBeInTheDocument();
    await waitFor(() => expect(container.querySelectorAll('.map-state')).toHaveLength(2));
    expect(global.fetch).toHaveBeenCalledWith(
      '/india-states.topo.json',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('counts cities and the transfers between them in plain words', () => {
    renderMap();
    expect(screen.getByText('3 cities, 3 transfers')).toBeInTheDocument();
  });

  it('marks each city with the shape and colour of its riskiest role', () => {
    const { container } = renderMap();
    expect(city(container, 'Mumbai').getAttribute('aria-label')).toBe('Mumbai, 1 account, Source');
    expect(city(container, 'Mumbai').querySelector('path').getAttribute('fill')).toBe('var(--role-source)');
    expect(city(container, 'Chennai').getAttribute('aria-label')).toBe('Chennai, 2 accounts, Legitimate');
    expect(city(container, 'Chennai').querySelector('path').getAttribute('fill')).toBe('var(--role-neutral)');
  });

  it('draws one line per city pair, solid when a transfer is flagged and dashed otherwise', () => {
    const { container } = renderMap();
    const flows = [...container.querySelectorAll('.map-flow')];
    expect(flows).toHaveLength(2);
    expect(flows[0].getAttribute('stroke-dasharray')).toBeNull();
    expect(flows[1].getAttribute('stroke-dasharray')).toBe('4 4');
  });

  it('shades states in one ink that deepens with more alerts', async () => {
    const { container } = renderMap();
    await waitFor(() => expect(container.querySelectorAll('.map-state')).toHaveLength(2));
    const [busy, quiet] = container.querySelectorAll('.map-state');
    expect(busy.getAttribute('fill')).toBe('var(--text-primary)');
    expect(Number(busy.getAttribute('fill-opacity'))).toBeGreaterThan(Number(quiet.getAttribute('fill-opacity')));
  });

  it('keeps markers readable for busy cities', () => {
    expect(cityRadius(1)).toBeLessThan(cityRadius(20));
    expect(cityRadius(500)).toBe(cityRadius(5000));
  });

  it('moves a label below its marker when it would hit a neighbouring label', () => {
    const { container } = renderMap({
      nodes: [{ account_id: 'p', city: 'Pune', role: 'MULE' }, { account_id: 'm', city: 'Mumbai', role: 'MULE' }],
      edges: [],
    });
    const labelY = name => Number(city(container, name).querySelector('text').getAttribute('y'));
    expect(labelY('Pune')).toBeLessThan(0);
    expect(labelY('Mumbai')).toBeGreaterThan(0);
  });

  it('stays still unless the viewer acts', () => {
    const { container } = renderMap({ selectedCity: 'Mumbai' });
    expect(container.querySelector('animate')).toBeNull();
  });

  it('selects a city from the keyboard', () => {
    const onCityClick = jest.fn();
    const { container } = renderMap({ onCityClick });
    fireEvent.keyDown(city(container, 'Delhi'), { key: 'Enter' });
    expect(onCityClick).toHaveBeenCalledWith('Delhi');
  });

  it('explains shapes, lines and shading in the key', () => {
    renderMap();
    ['Source', 'Mule', 'Flagged transfer', 'Other transfer', 'More alerts'].forEach(label =>
      expect(screen.getByText(label)).toBeInTheDocument()
    );
  });
});
