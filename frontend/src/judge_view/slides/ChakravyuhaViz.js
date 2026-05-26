import React from 'react';
import { motion } from 'framer-motion';

const LAYERS = [
  { label: 'Rules', color: '#FF5C7A', r: 140 },
  { label: 'Smurf', color: '#FFB020', r: 110 },
  { label: 'Louvain', color: '#38BDF8', r: 80 },
  { label: 'GNN', color: '#16C784', r: 50 },
];

export default function ChakravyuhaViz({ activeLayer }) {
  return (
    <svg viewBox="0 0 300 300" width="260" height="260" style={{ margin: '0 auto', display: 'block' }}>
      {LAYERS.map((layer, i) => {
        const isActive = activeLayer === i || activeLayer === -1;
        return (
          <g key={layer.label}>
            <motion.circle
              cx="150" cy="150" r={layer.r}
              fill="none"
              stroke={layer.color}
              strokeWidth={isActive ? 3 : 1.5}
              strokeDasharray={isActive ? 'none' : '6 4'}
              opacity={isActive ? 1 : 0.3}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: isActive ? 1 : 0.3 }}
              transition={{ duration: 1, delay: i * 0.3 }}
            />
            <text
              x={150 + layer.r - 10}
              y={150 - 6}
              fill={layer.color}
              fontSize="9"
              fontFamily="var(--font-mono)"
              opacity={isActive ? 1 : 0.4}
            >
              {layer.label}
            </text>
          </g>
        );
      })}
      <motion.circle
        cx="150" cy="150" r="18"
        fill="var(--accent-gold)"
        opacity={0.9}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 1.2, type: 'spring' }}
      />
      <text
        x="150" y="154"
        fill="#fff"
        fontSize="8"
        fontFamily="var(--font-mono)"
        textAnchor="middle"
        fontWeight="700"
      >
        MULE
      </text>
    </svg>
  );
}
