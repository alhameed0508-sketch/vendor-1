import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../../components/ui/GlassCard';
import SlideTitle from './SlideTitle';
import ChakravyuhaViz from './ChakravyuhaViz';

const DETECTION_LAYERS = [
  { name: 'Layer 1: Rule Engine', desc: '20 deterministic behavioral rules (R01-R20) aligned with RBI/RBIH MuleHunter framework + 72-hour BioCatch detection', color: '#FF5C7A' },
  { name: 'Layer 2: Smurf-Weighting', desc: '5-dimensional temporal scoring: velocity, ceiling, fan-out, rhythm, consolidation', color: '#FFB020' },
  { name: 'Layer 3: Louvain Detection', desc: 'Graph community detection with device/IP-weighted edges identifying mule clusters', color: '#38BDF8' },
  { name: 'Layer 4: GraphSAGE GNN', desc: '3-layer graph neural network for pattern recognition beyond human-defined rules', color: '#16C784' },
];

export default function SlideArchitecture({ activeLayer, setActiveLayer }) {
  return (
    <div>
      <SlideTitle title="MuleCatch Architecture" subtitle="Four Concentric Layers of Defense" />
      <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
        <div style={{ flex: '0 0 280px' }}>
          <ChakravyuhaViz activeLayer={activeLayer} />
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {DETECTION_LAYERS.map((layer, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 * i }}
              onMouseEnter={() => setActiveLayer(i)}
              onMouseLeave={() => setActiveLayer(-1)}
              style={{ cursor: 'pointer' }}
            >
              <GlassCard style={{ padding: 14, borderLeft: `3px solid ${layer.color}` }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: layer.color, marginBottom: 4 }}>
                  {layer.name}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {layer.desc}
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
