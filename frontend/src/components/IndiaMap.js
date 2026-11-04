import React, { useEffect, useMemo, useState } from 'react';
import { geoMercator, geoPath } from 'd3';
import { feature } from 'topojson-client';
import { GlassCard } from './ui/GlassCard';
import { CITY_COORDS } from '../constants/cities';
import GraphLegend from '../graph_viz/GraphLegend';
import { curvedEdgePath } from '../graph_viz/graphGeometry';
import { isFlaggedEdge, roleLabel } from '../graph_viz/graphModel';
import { edgeStyle, roleStyle, shapePath } from '../graph_viz/graphStyle';

const INDIA_TOPO_URL = '/india-states.topo.json';
const MAP_WIDTH = 560;
const MAP_HEIGHT = 640;
// Fits Kashmir to the Nicobar Islands inside the frame with a small margin.
const MAP_CENTER = [82.75, 22.8];
const MAP_SCALE = 1040;
const MAP_UID = 'india-map';
const LABEL_GAP = 6;
const LABEL_HEIGHT = 12;
const LABEL_WIDTH = 60;

// A city takes the hue and shape of the riskiest role among its accounts, as in the graph.
const ROLE_PRIORITY = ['SOURCE', 'AGGREGATOR', 'MULE'];
const MAX_CITY_RADIUS = 14;
// States: one ink that deepens with alert count, so both themes read the same way.
const STATE_STEPS = [[20, 0.36], [10, 0.28], [5, 0.2], [2, 0.14], [1, 0.1]];
const QUIET_STATE_OPACITY = 0.04;

const plural = (count, one, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;

/** Grows with the square root of the account count, capped so busy cities stay readable. */
export const cityRadius = count => Math.min(MAX_CITY_RADIUS, 4 + 1.5 * Math.sqrt(count));

function stateOpacity(count) {
  const step = STATE_STEPS.find(([min]) => count >= min);
  return step ? step[1] : QUIET_STATE_OPACITY;
}

const cityRole = roles => ROLE_PRIORITY.find(role => roles.has(role)) || 'LEGITIMATE';

/** Labels sit above their marker unless that hits a label already placed; then they go below. */
function placeLabels(cities) {
  const placed = [];
  return cities.map(city => {
    const above = -city.radius - LABEL_GAP;
    const clashes = placed.some(([x, y]) =>
      Math.abs(x - city.x) < LABEL_WIDTH && Math.abs(y - (city.y + above)) < LABEL_HEIGHT);
    const labelY = clashes ? city.radius + LABEL_GAP + LABEL_HEIGHT - 2 : above;
    placed.push([city.x, city.y + labelY]);
    return { ...city, labelY };
  });
}

function useIndiaGeography() {
  const [geographies, setGeographies] = useState([]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadGeography() {
      try {
        const response = await fetch(INDIA_TOPO_URL, { signal: controller.signal });
        if (!response.ok) throw new Error(`Map data request failed: ${response.status}`);

        const topology = await response.json();
        const objectName = Object.keys(topology.objects || {})[0];
        if (!objectName) throw new Error('Map data does not contain a TopoJSON object');

        const collection = feature(topology, topology.objects[objectName]);
        setGeographies(collection.features || [collection]);
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error('Unable to load bundled India map data', error);
        }
      }
    }

    loadGeography();
    return () => controller.abort();
  }, []);

  return geographies;
}

function summariseCities(nodes, projection) {
  const cities = new Map();
  nodes.forEach(node => {
    const coords = CITY_COORDS[node.city];
    if (!coords) return;
    const city = cities.get(node.city) || { name: node.city, count: 0, roles: new Set() };
    cities.set(node.city, { ...city, count: city.count + 1, roles: new Set([...city.roles, node.role]) });
  });
  return placeLabels([...cities.values()].map(city => {
    const [x, y] = projection(CITY_COORDS[city.name]);
    const role = cityRole(city.roles);
    return { ...city, x, y, role, radius: cityRadius(city.count) };
  }));
}

/** One line per direction between two cities; it is flagged when any transfer on it is. */
function summariseFlows(nodes, edges, cityByName) {
  const nodeById = new Map(nodes.map(node => [node.account_id, node]));
  const flows = new Map();
  let transfers = 0;
  edges.forEach(edge => {
    const from = cityByName.get(nodeById.get(edge.from_account)?.city);
    const to = cityByName.get(nodeById.get(edge.to_account)?.city);
    if (!from || !to || from === to) return;
    transfers += 1;
    const key = `${from.name}->${to.name}`;
    const flagged = Boolean(flows.get(key)?.flagged) || isFlaggedEdge(edge, nodeById);
    flows.set(key, { key, source: { id: from.name, x: from.x, y: from.y }, target: { id: to.name, x: to.x, y: to.y }, flagged });
  });
  return { flows: [...flows.values()], transfers };
}

function MapMarkers() {
  return (
    <defs>
      {[['flagged', true], ['other', false]].map(([name, flagged]) => (
        <marker key={name} id={`${MAP_UID}-${name}`} viewBox="0 -4 8 8" refX={8} refY={0}
          markerWidth={5} markerHeight={5} orient="auto">
          <path d="M0,-4L8,0L0,4" fill={edgeStyle(flagged).stroke} />
        </marker>
      ))}
    </defs>
  );
}

function CityMarker({ city, isSelected, onCityClick, onHover }) {
  const { color, shape, fill } = roleStyle(city.role);
  const select = () => onCityClick?.(city.name);
  return (
    <g
      className="map-city"
      transform={`translate(${city.x}, ${city.y})`}
      aria-label={`${city.name}, ${plural(city.count, 'account')}, ${roleLabel(city.role)}`}
      role={onCityClick ? 'button' : undefined}
      tabIndex={onCityClick ? 0 : undefined}
      onMouseEnter={() => onHover(city)}
      onMouseLeave={() => onHover(null)}
      onClick={select}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          select();
        }
      }}
      style={{ cursor: onCityClick ? 'pointer' : 'default' }}
    >
      <path d={shapePath(shape, city.radius)} fill={color} fillOpacity={fill} stroke={color}
        strokeWidth={isSelected ? 2.5 : 1.5} />
      {isSelected && (
        <circle r={city.radius + 6} fill="none" stroke="var(--text-primary)" strokeWidth={1.5} />
      )}
      <text className="map-city-label" textAnchor="middle" y={city.labelY}
        fontWeight={isSelected ? 600 : 400}>
        {city.name}
      </text>
    </g>
  );
}

export default function IndiaMap({
  nodes = [],
  edges = [],
  onCityClick,
  selectedCity = null,
  stateAlertCounts = {},
}) {
  const [hovered, setHovered] = useState(null);
  const geographies = useIndiaGeography();

  const projection = useMemo(
    () =>
      geoMercator()
        .center(MAP_CENTER)
        .scale(MAP_SCALE)
        .translate([MAP_WIDTH / 2, MAP_HEIGHT / 2]),
    []
  );
  const path = useMemo(() => geoPath(projection), [projection]);
  const cities = useMemo(() => summariseCities(nodes, projection), [nodes, projection]);
  const { flows, transfers } = useMemo(
    () => summariseFlows(nodes, edges, new Map(cities.map(city => [city.name, city]))),
    [nodes, edges, cities]
  );
  const radii = useMemo(() => new Map(cities.map(city => [city.name, city.radius])), [cities]);

  return (
    <GlassCard className="india-map" style={{ padding: 0 }} hover={false}>
      <div className="india-map-head">
        <span className="india-map-title">Money flow across India</span>
        <span className="india-map-meta">
          {cities.length > 0
            ? `${plural(cities.length, 'city', 'cities')}, ${plural(transfers, 'transfer')}`
            : 'No city data yet'}
        </span>
      </div>

      <div className="india-map-stage">
        <svg viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`} role="img" aria-label="India transaction flow map">
          <MapMarkers />
          {geographies.map((geography, index) => {
            const stateName = geography.properties?.st_nm || geography.properties?.name || `state-${index}`;
            const statePath = path(geography);
            if (!statePath) return null;
            return (
              <path
                key={geography.id || geography.properties?.st_code || stateName}
                className="map-state"
                d={statePath}
                fill="var(--text-primary)"
                fillOpacity={stateOpacity(stateAlertCounts[stateName] || 0)}
                stroke="var(--border-strong)"
                strokeWidth={0.5}
              />
            );
          })}

          {flows.map(flow => {
            const { stroke, opacity, dash } = edgeStyle(flow.flagged);
            return (
              <path
                key={flow.key}
                className="map-flow"
                d={curvedEdgePath(flow, radii)}
                fill="none"
                stroke={stroke}
                strokeOpacity={opacity}
                strokeWidth={1.25}
                strokeDasharray={dash || undefined}
                markerEnd={`url(#${MAP_UID}-${flow.flagged ? 'flagged' : 'other'})`}
              />
            );
          })}

          {cities.map(city => (
            <CityMarker key={city.name} city={city} isSelected={selectedCity === city.name}
              onCityClick={onCityClick} onHover={setHovered} />
          ))}
        </svg>

        {hovered && (
          <div className="graph-tooltip is-visible india-map-tooltip" aria-hidden="true">
            <strong>{hovered.name}</strong>
            <span>{plural(hovered.count, 'account')}</span>
            <span>Riskiest role: {roleLabel(hovered.role)}</span>
          </div>
        )}
      </div>

      <GraphLegend ring={false}>
        <span className="graph-legend-item">
          <span className="india-map-ramp" aria-hidden="true" />
          More alerts
        </span>
      </GraphLegend>
    </GlassCard>
  );
}
