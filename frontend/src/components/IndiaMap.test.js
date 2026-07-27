import { render, screen, waitFor } from '@testing-library/react';
import IndiaMap from './IndiaMap';

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
        {
          type: 'Polygon',
          arcs: [[0]],
          properties: { st_nm: 'Maharashtra', st_code: 'MH' },
        },
      ],
    },
  },
  arcs: [[[72, 8], [20, 0], [0, 28], [-20, 0], [0, -28]]],
};

describe('IndiaMap', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => topology,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders bundled geography and projects transaction cities', async () => {
    const { container } = render(
      <IndiaMap
        nodes={[
          { account_id: 'a1', city: 'Mumbai', role: 'SOURCE' },
          { account_id: 'a2', city: 'Delhi', role: 'BENEFICIARY' },
        ]}
        edges={[
          {
            from_account: 'a1',
            to_account: 'a2',
            pattern: 'SMURFING',
          },
        ]}
        stateAlertCounts={{ Maharashtra: 4 }}
      />
    );

    expect(screen.getByRole('img', { name: /India transaction flow map/i })).toBeInTheDocument();
    expect(screen.getByText('2 cities · 1 flows')).toBeInTheDocument();
    expect(screen.getByText('Mumbai')).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/india-states.topo.json',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
      expect(container.querySelector('path')).toBeInTheDocument();
    });
  });
});
