import React, { useEffect, useMemo, useState } from 'react';
import { geoMercator, geoPath } from 'd3';
import { feature } from 'topojson-client';
import { motion } from 'framer-motion';
import { GlassCard } from './ui/GlassCard';
import { CITY_COORDS } from '../constants/cities';

const INDIA_TOPO_URL = '/india-states.topo.json';
const MAP_WIDTH = 800;
const MAP_HEIGHT = 400;

function stateHeatColor(count) {
  if (!count || count <= 0) return '#121A2B';
  if (count <= 2) return '#1a2540';
  if (count <= 5) return '#1e3050';
  if (count <= 10) return '#223b5e';
  if (count <= 20) return '#2a4a70';
  return '#345a85';
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

export default function IndiaMap({
  nodes = [],
  edges = [],
  onCityClick,
  selectedCity = null,
  stateAlertCounts = {},
}) {
  const [tooltip, setTooltip] = useState(null);
  const [hoveredState, setHoveredState] = useState(null);
  const geographies = useIndiaGeography();

  const projection = useMemo(
    () =>
      geoMercator()
        .center([80, 22])
        .scale(1000)
        .translate([MAP_WIDTH / 2, MAP_HEIGHT / 2]),
    []
  );
  const path = useMemo(() => geoPath(projection), [projection]);

  const cityData = useMemo(() => {
    const cities = {};
    nodes.forEach(node => {
      const city = node.city;
      if (!city || !CITY_COORDS[city]) return;
      if (!cities[city]) {
        cities[city] = {
          name: city,
          coords: CITY_COORDS[city],
          count: 0,
          roles: new Set(),
        };
      }
      cities[city].count += 1;
      cities[city].roles.add(node.role);
    });
    return Object.values(cities);
  }, [nodes]);

  const arcs = useMemo(() => {
    const nodeMap = Object.fromEntries(nodes.map(node => [node.account_id, node]));
    return edges
      .map(edge => {
        const from = nodeMap[edge.from_account];
        const to = nodeMap[edge.to_account];
        if (!from?.city || !to?.city || from.city === to.city) return null;
        const fromCoords = CITY_COORDS[from.city];
        const toCoords = CITY_COORDS[to.city];
        if (!fromCoords || !toCoords) return null;
        return {
          from: projection(fromCoords),
          to: projection(toCoords),
          pattern: edge.pattern,
        };
      })
      .filter(Boolean);
  }, [edges, nodes, projection]);

  return (
    <GlassCard className="overflow-hidden" style={{ padding: 0 }} hover={false}>
      <div
        style={{
          padding: '14px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 14 }}>Transaction Flow Map — India</span>
        <span
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 11,
            color: 'var(--text-muted)',
          }}
        >
          {cityData.length > 0
            ? `${cityData.length} cities · ${arcs.length} flows`
            : 'Awaiting data'}
        </span>
      </div>

      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          role="img"
          aria-label="India transaction flow map"
          style={{
            display: 'block',
            width: '100%',
            height: 400,
            background: 'transparent',
          }}
        >
          {geographies.map((geography, index) => {
            const stateName =
              geography.properties?.st_nm ||
              geography.properties?.name ||
              `state-${index}`;
            const alertCount = stateAlertCounts[stateName] || 0;
            const statePath = path(geography);
            if (!statePath) return null;
            return (
              <path
                key={geography.id || geography.properties?.st_code || stateName}
                d={statePath}
                fill={
                  hoveredState === stateName
                    ? alertCount > 0
                      ? '#2e5580'
                      : '#1E2B42'
                    : stateHeatColor(alertCount)
                }
                stroke="rgba(30,43,66,0.8)"
                strokeWidth={0.5}
                onMouseEnter={() => setHoveredState(stateName)}
                onMouseLeave={() => setHoveredState(null)}
              />
            );
          })}

          {arcs.map((arc, index) => (
            <line
              key={`${arc.from.join('-')}-${arc.to.join('-')}-${index}`}
              x1={arc.from[0]}
              y1={arc.from[1]}
              x2={arc.to[0]}
              y2={arc.to[1]}
              stroke={
                arc.pattern === 'SMURFING'
                  ? 'rgba(255,92,122,0.5)'
                  : arc.pattern === 'CONSOLIDATION'
                    ? 'rgba(255,176,32,0.5)'
                    : 'rgba(62,231,255,0.4)'
              }
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeDasharray="6,3"
            />
          ))}

          {cityData.map(city => {
            const [x, y] = projection(city.coords);
            const hasHighRisk = city.roles.has('SOURCE') || city.roles.has('AGGREGATOR');
            const isSelected = selectedCity === city.name;
            const baseColor = hasHighRisk ? '#FF5C7A' : '#3EE7FF';
            const markerRadius = (isSelected ? 6 : 4) + city.count;

            return (
              <g
                key={city.name}
                transform={`translate(${x}, ${y})`}
                onMouseEnter={() => setTooltip(city)}
                onMouseLeave={() => setTooltip(null)}
                onClick={() => onCityClick?.(city.name)}
                role={onCityClick ? 'button' : undefined}
                tabIndex={onCityClick ? 0 : undefined}
                onKeyDown={event => {
                  if (onCityClick && (event.key === 'Enter' || event.key === ' ')) {
                    event.preventDefault();
                    onCityClick(city.name);
                  }
                }}
                style={{ cursor: onCityClick ? 'pointer' : 'default' }}
              >
                <circle r={8} fill="none" stroke={baseColor} strokeWidth={1} opacity={0.3}>
                  <animate
                    attributeName="r"
                    from="6"
                    to="14"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    from="0.4"
                    to="0"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
                {isSelected && (
                  <circle
                    r={markerRadius + 5}
                    fill="none"
                    stroke={baseColor}
                    strokeWidth={2}
                    opacity={0.8}
                  >
                    <animate
                      attributeName="opacity"
                      values="0.8;0.3;0.8"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                <circle
                  r={markerRadius}
                  fill={
                    hasHighRisk ? 'rgba(255,92,122,0.6)' : 'rgba(62,231,255,0.6)'
                  }
                  stroke={baseColor}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                />
                <text
                  textAnchor="middle"
                  y={-10 - markerRadius}
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: isSelected ? 10 : 9,
                    fontWeight: isSelected ? 700 : 400,
                    fill: isSelected ? '#e8edf5' : 'rgba(136,149,176,0.8)',
                  }}
                >
                  {city.name}
                </text>
              </g>
            );
          })}
        </svg>

        {tooltip && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              position: 'absolute',
              bottom: 16,
              left: 16,
              background: 'rgba(18,26,43,0.95)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              padding: '10px 14px',
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 13,
                marginBottom: 4,
                color: '#e8edf5',
              }}
            >
              {tooltip.name}
            </div>
            <div
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 11,
                color: '#8895b0',
              }}
            >
              {tooltip.count} accounts · Roles: {[...tooltip.roles].join(', ')}
            </div>
          </motion.div>
        )}
      </div>

      <div
        style={{
          padding: '8px 20px 12px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          gap: 16,
          fontSize: 11,
          flexWrap: 'wrap',
        }}
      >
        {[
          ['rgba(255,92,122,0.5)', 'Smurfing'],
          ['rgba(255,176,32,0.5)', 'Consolidation'],
        ].map(([color, label]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: color }} />
            <span className="font-mono text-[var(--text-muted)]">{label}</span>
          </div>
        ))}
        {[
          ['rgba(255,92,122,0.6)', '#FF5C7A', 'High Risk'],
          ['rgba(62,231,255,0.6)', '#3EE7FF', 'Other'],
        ].map(([background, border, label]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background,
                border: `1px solid ${border}`,
              }}
            />
            <span className="font-mono text-[var(--text-muted)]">{label}</span>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 40,
              height: 6,
              borderRadius: 3,
              background: 'linear-gradient(90deg, #121A2B, #345a85)',
            }}
          />
          <span className="font-mono text-[var(--text-muted)]">State Activity</span>
        </div>
      </div>
    </GlassCard>
  );
}
