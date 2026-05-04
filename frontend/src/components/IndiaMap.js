import React, { useState, useMemo } from 'react';
import { ComposableMap, Geographies, Geography, Marker, Line } from 'react-simple-maps';
import { motion } from 'framer-motion';
import { GlassCard } from './ui/GlassCard';

const INDIA_TOPO_URL = 'https://cdn.jsdelivr.net/npm/india-topojson@1.0.0/india.json';

// Major Indian city coordinates
const CITY_COORDS = {
  'Mumbai': [72.8777, 19.0760],
  'Delhi': [77.1025, 28.7041],
  'Bangalore': [77.5946, 12.9716],
  'Chennai': [80.2707, 13.0827],
  'Kolkata': [88.3639, 22.5726],
  'Hyderabad': [78.4867, 17.3850],
  'Pune': [73.8567, 18.5204],
  'Ahmedabad': [72.5714, 23.0225],
  'Jaipur': [75.7873, 26.9124],
  'Lucknow': [80.9462, 26.8467],
  'Surat': [72.8311, 21.1702],
  'Kochi': [76.2673, 9.9312],
  'Indore': [75.8577, 22.7196],
  'Coimbatore': [76.9558, 11.0168],
  'Nagpur': [79.0882, 21.1458],
  'Bhopal': [77.4126, 23.2599],
  'Patna': [85.1376, 25.6093],
  'Thiruvananthapuram': [76.9366, 8.5241],
  'Chandigarh': [76.7794, 30.7333],
  'Guwahati': [91.7362, 26.1445],
};

export default function IndiaMap({ nodes = [], edges = [] }) {
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

  if (cityData.length === 0) {
    return (
      <GlassCard className="p-5 text-center" hover={false}>
        <p className="text-xs font-mono text-[var(--text-muted)]">No geographic data available for this cluster.</p>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="overflow-hidden" style={{ padding: 0 }} hover={false}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>Transaction Flow Map — India</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{cityData.length} cities · {arcs.length} flows</span>
      </div>
      <div style={{ position: 'relative' }}>
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ scale: 1000, center: [80, 22] }}
          style={{ width: '100%', height: 350, background: 'transparent' }}
        >
          <Geographies geography={INDIA_TOPO_URL}>
            {({ geographies }) =>
              geographies.map(geo => (
                <Geography
                  key={geo.rpiKey || geo.properties.ST_NM}
                  geography={geo}
                  fill="#141824"
                  stroke="rgba(30,37,53,0.8)"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: 'none' },
                    hover: { fill: '#1a2030', outline: 'none' },
                    pressed: { outline: 'none' },
                  }}
                />
              ))
            }
          </Geographies>

          {/* Transaction arcs */}
          {arcs.map((arc, i) => (
            <Line
              key={i}
              from={arc.from}
              to={arc.to}
              stroke={arc.pattern === 'SMURFING' ? 'rgba(255,59,92,0.5)' : arc.pattern === 'CONSOLIDATION' ? 'rgba(245,158,11,0.5)' : 'rgba(6,182,212,0.4)'}
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
            return (
              <Marker
                key={city.name}
                coordinates={city.coords}
                onMouseEnter={() => setTooltip(city)}
                onMouseLeave={() => setTooltip(null)}
              >
                {/* Pulse ring for active cities */}
                <circle r={8} fill="none" stroke={hasHighRisk ? '#ff3b5c' : '#06b6d4'} strokeWidth={1} opacity={0.3}>
                  <animate attributeName="r" from="6" to="14" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.4" to="0" dur="2s" repeatCount="indefinite" />
                </circle>
                <circle
                  r={4 + city.count}
                  fill={hasHighRisk ? 'rgba(255,59,92,0.6)' : 'rgba(6,182,212,0.6)'}
                  stroke={hasHighRisk ? '#ff3b5c' : '#06b6d4'}
                  strokeWidth={1.5}
                  style={{ cursor: 'pointer' }}
                />
                <text
                  textAnchor="middle"
                  y={-10 - city.count}
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 9,
                    fill: 'rgba(136,149,176,0.8)',
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
              background: 'rgba(20,24,36,0.95)',
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
      <div style={{ padding: '8px 20px 12px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', gap: 16, fontSize: 11 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 20, height: 2, background: 'rgba(255,59,92,0.5)' }} />
          <span className="font-mono text-[var(--text-muted)]">Smurfing</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 20, height: 2, background: 'rgba(245,158,11,0.5)' }} />
          <span className="font-mono text-[var(--text-muted)]">Consolidation</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(255,59,92,0.6)', border: '1px solid #ff3b5c' }} />
          <span className="font-mono text-[var(--text-muted)]">High Risk</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(6,182,212,0.6)', border: '1px solid #06b6d4' }} />
          <span className="font-mono text-[var(--text-muted)]">Other</span>
        </div>
      </div>
    </GlassCard>
  );
}
