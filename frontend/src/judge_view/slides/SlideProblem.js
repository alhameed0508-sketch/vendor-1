import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../../components/ui/GlassCard';
import SlideTitle from './SlideTitle';

const THREAT_ITEMS = [
  'RBI reports mule accounts as #1 vector for UPI fraud',
  'Estimated 3-5% of new accounts show mule patterns',
  '\u20B92,145 Cr lost to digital payment fraud in FY24',
  'Average mule network operates across 3+ banks',
  'Manual detection takes 4-6 hours per case',
];

const FAILURE_ITEMS = [
  'Rule-only systems generate 60%+ false positives',
  'No graph analysis = miss coordinated networks',
  'Black-box ML models fail RBI explainability requirements',
  'MuleHunter.AI covers only 9 rules, no GNN layer',
  'No real-time behavioral profiling (BioCatch insights)',
];

export default function SlideProblem() {
  return (
    <div>
      <SlideTitle title="The Problem" subtitle="Money Mules in Indian Banking" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <GlassCard style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, color: 'var(--critical)' }}>
            Scale of Threat
          </h3>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {THREAT_ITEMS.map((item, i) => (
              <motion.li
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 * i }}
                style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 8 }}
              >
                <span style={{ color: 'var(--critical)', flexShrink: 0 }}>&#9656;</span>
                {item}
              </motion.li>
            ))}
          </ul>
        </GlassCard>
        <GlassCard style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, color: 'var(--accent-gold)' }}>
            Why Existing Tools Fail
          </h3>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {FAILURE_ITEMS.map((item, i) => (
              <motion.li
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 * i + 0.3 }}
                style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 8 }}
              >
                <span style={{ color: 'var(--accent-amber)', flexShrink: 0 }}>&#9656;</span>
                {item}
              </motion.li>
            ))}
          </ul>
        </GlassCard>
      </div>
    </div>
  );
}
