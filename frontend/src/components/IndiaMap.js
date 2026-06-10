import React, { useState, useMemo } from 'react';
import { ComposableMap, Geographies, Geography, Marker, Line } from 'react-simple-maps';
import { motion } from 'framer-motion';
import { GlassCard } from './ui/GlassCard';
import { CITY_COORDS } from '../constants/cities';

// Bundled in public/ — no external CDN dependency
const INDIA_TOPO_URL = '/india-states.topo.json';

// State heatmap color scale: 0 alerts → base, more alerts → brighter
function stateHeatColor(count) {
  if (!count || count <= 0) return '#121A2B';
  if (count <= 2)  return '#1a2540';
  if (count <= 5)  return '#1e3050';
  if (count <= 10) return '#223b5e';
  if (count <= 20) return '#2a4a70';
  return '#345a85';
}

export default function IndiaMap({
  nodes = [],
  edges = [],
  onCityClick,
  selectedCity = null,
  stateAlertCounts = {},
}) {
  const [tooltip, setTooltip] = useState(null);

  // Build city data from nodes
  const cityData = useMemo(() => {
    const cities = {};
    nodes.forEach(n => {
      const city = n.city;
      if (!city || !CITY_COORDS[city]) return;
      if (!cities[city]) {
        cities[city] = { name: city, coords: CITY_COORDS[city], count: 0, amount: 0, roles: new Set() };
      }
      cities[city].count += 1;
      cities[city].roles.add(n.role);
    });
    return Object.values(cities);
  }, [nodes]);

  // Build arcs from edges
  const arcs = useMemo(() => {
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.account_id] = n; });

    return edges
      .map(e => {
        const from = nodeMap[e.from_account];
        const to = nodeMap[e.to_account];
        if (!from?.city || !to?.city || from.city === to.city) return null;
        const fromCoords = CITY_COORDS[from.city];
        const toCoords = CITY_COORDS[to.city];
        if (!fromCoords || !toCoords) return null;
        return {
          from: fromCoords,
          to: toCoords,
          pattern: e.pattern,
          amount: e.total_amount,
        };
      })
      .filter(Boolean);
  }, [nodes, edges]);

  return (
    <GlassCard className="overflow-hidden" style={{ padding: 0 }} hover={false}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>Transaction Flow Map — India</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
          {cityData.length > 0 ? `${cityData.length} cities · ${arcs.length} flows` : 'Awaiting data'}
        </span>
      </div>
      <div style={{ position: 'relative' }}>
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ scale: 1000, center: [80, 22] }}
          style={{ width: '100%', height: 400, background: 'transparent' }}
        >
          <Geographies geography={INDIA_TOPO_URL}>
            {({ geographies }) =>
              geographies.map(geo => {
                const stateName = geo.properties.st_nm;
                const alertCount = stateAlertCounts[stateName] || 0;
                return (
                  <Geography
                    key={geo.rsmKey || geo.properties.st_code || stateName}
                    geography={geo}
                    fill={stateHeatColor(alertCount)}
                    stroke="rgba(30,43,66,0.8)"
                    strokeWidth={0.5}
                    style={{
                      default: { outline: 'none' },
                      hover: { fill: alertCount > 0 ? '#2e5580' : '#1E2B42', outline: 'none' },
                      pressed: { outline: 'none' },
                    }}
                  />
                );
              })
            }
          </Geographies>

          {/* Transaction arcs */}
          {arcs.map((arc, i) => (
            <Line
              key={i}
              from={arc.from}
              to={arc.to}
              stroke={arc.pattern === 'SMURFING' ? 'rgba(255,92,122,0.5)' : arc.pattern === 'CONSOLIDATION' ? 'rgba(255,176,32,0.5)' : 'rgba(62,231,255,0.4)'}
              strokeWidth={1.5}
              strokeLinecap="round"
              style={{
                strokeDasharray: '6,3',
              }}
            />
          ))}

          {/* City markers */}
          {cityData.map(city => {
            const hasHighRisk = city.roles.has('SOURCE') || city.roles.has('AGGREGATOR');
            const isSelected = selectedCity === city.name;
            const baseColor = hasHighRisk ? '#FF5C7A' : '#3EE7FF';
            const markerRadius = isSelected ? 6 + city.count : 4 + city.count;

            return (
              <Marker
                key={city.name}
                coordinates={city.coords}
                onMouseEnter={() => setTooltip(city)}
                onMouseLeave={() => setTooltip(null)}
                onClick={() => onCityClick?.(city.name)}
                style={{ cursor: onCityClick ? 'pointer' : 'default' }}
              >
                {/* Pulse ring for active cities */}
                <circle r={8} fill="none" stroke={baseColor} strokeWidth={1} opacity={0.3}>
                  <animate attributeName="r" from="6" to="14" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.4" to="0" dur="2s" repeatCount="indefinite" />
                </circle>

                {/* Selection highlight ring */}
                {isSelected && (
                  <circle
                    r={markerRadius + 5}
                    fill="none"
                    stroke={baseColor}
                    strokeWidth={2}
                    opacity={0.8}
                  >
                    <animate attributeName="opacity" values="0.8;0.3;0.8" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                )}

                <circle
                  r={markerRadius}
                  fill={hasHighRisk ? 'rgba(255,92,122,0.6)' : 'rgba(62,231,255,0.6)'}
                  stroke={baseColor}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  style={{ cursor: onCityClick ? 'pointer' : 'default' }}
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
              </Marker>
            );
          })}
        </ComposableMap>

        {/* Tooltip */}
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
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4, color: '#e8edf5' }}>{tooltip.name}</div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#8895b0' }}>
              {tooltip.count} accounts · Roles: {[...tooltip.roles].join(', ')}
            </div>
          </motion.div>
        )}
      </div>

      {/* Legend */}
      <div style={{ padding: '8px 20px 12px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', gap: 16, fontSize: 11, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 20, height: 2, background: 'rgba(255,92,122,0.5)' }} />
          <span className="font-mono text-[var(--text-muted)]">Smurfing</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 20, height: 2, background: 'rgba(255,176,32,0.5)' }} />
          <span className="font-mono text-[var(--text-muted)]">Consolidation</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(255,92,122,0.6)', border: '1px solid #FF5C7A' }} />
          <span className="font-mono text-[var(--text-muted)]">High Risk</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(62,231,255,0.6)', border: '1px solid #3EE7FF' }} />
          <span className="font-mono text-[var(--text-muted)]">Other</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 40, height: 6, borderRadius: 3,
            background: 'linear-gradient(90deg, #121A2B, #345a85)',
          }} />
          <span className="font-mono text-[var(--text-muted)]">State Activity</span>
        </div>
      </div>
    </GlassCard>
  );
}
