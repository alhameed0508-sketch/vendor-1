import React from 'react';
import { motion } from 'framer-motion';

const RISK_COLORS = {
  LOW: 'var(--accent-green)',
  MEDIUM: 'var(--accent-amber)',
  HIGH: 'var(--accent-red)',
  CRITICAL: 'var(--critical)',
};

export { RISK_COLORS };

export const RISK_BG = {
  LOW: 'rgba(22,199,132,0.10)',
  MEDIUM: 'rgba(255,176,32,0.10)',
  HIGH: 'rgba(255,92,122,0.10)',
  CRITICAL: 'rgba(255,92,122,0.15)',
};

export default function RiskBar({ score, level }) {
  const pct = Math.round(score * 100);
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
          Risk Score
        </span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700,
          color: RISK_COLORS[level] || 'var(--text-primary)',
        }}>
          {pct}%
        </span>
      </div>
      <div style={{ height: 10, background: 'var(--border)', borderRadius: 5, overflow: 'hidden', position: 'relative' }}>
        {/* Gradient track */}
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.15,
          background: 'linear-gradient(90deg, #16C784 0%, #FFB020 40%, #FF5C7A 70%, #FF5C7A 100%)',
          borderRadius: 5,
        }} />
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
          style={{
            height: '100%',
            background: `linear-gradient(90deg, #16C784 0%, #FFB020 40%, #FF5C7A 70%, #FF5C7A 100%)`,
            borderRadius: 5,
            position: 'relative',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
        <span>LOW</span><span>MEDIUM</span><span>HIGH</span><span>CRITICAL</span>
      </div>
    </div>
  );
}
