import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../../components/ui/GlassCard';
import SlideTitle from './SlideTitle';

const DEMO_LINKS = [
  { label: 'Alert Queue', path: '/', desc: 'Live detection results' },
  { label: 'ROI Analytics', path: '/analytics', desc: 'Impact metrics' },
  { label: 'Compliance', path: '/compliance', desc: 'STR generation' },
];

export default function SlideDemo() {
  return (
    <div style={{ textAlign: 'center', padding: '40px 0' }}>
      <SlideTitle title="Live Demo" subtitle="See MuleCatch in action" />
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        style={{ color: 'var(--text-secondary)', maxWidth: 500, margin: '0 auto 32px', lineHeight: 1.7 }}
      >
        Navigate to the <strong>Alert Queue</strong> to see live detection results,
        click any alert for the full network graph, explainability panel, and
        investigator workspace.
      </motion.p>
      <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
        {DEMO_LINKS.map((item, i) => (
          <motion.a
            key={item.path}
            href={item.path}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 * i }}
            style={{ textDecoration: 'none' }}
          >
            <GlassCard style={{ padding: '20px 32px', textAlign: 'center', cursor: 'pointer' }} glow>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{item.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.desc}</div>
            </GlassCard>
          </motion.a>
        ))}
      </div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        style={{
          marginTop: 48, fontFamily: 'var(--font-mono)',
          fontSize: 10, color: 'var(--text-muted)', letterSpacing: '1px',
        }}
      >
        // Thank you — Questions welcome
      </motion.div>
    </div>
  );
}
