import React from 'react';
import { motion } from 'framer-motion';
import SlideTitle from './SlideTitle';

export default function SlideIntro() {
  return (
    <div style={{ textAlign: 'center', padding: '60px 0' }}>
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 200, damping: 15 }}
        style={{
          width: 100, height: 100, borderRadius: 24,
          background: 'var(--gradient-brand)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 24px',
          boxShadow: '0 0 60px var(--gradient-brand-glow)',
        }}
      >
        <span style={{ color: '#fff', fontSize: 36, fontWeight: 700 }}>MC</span>
      </motion.div>
      <SlideTitle
        title="MuleCatch"
        subtitle="Explainable Graph Intelligence for Mule Account Detection"
      />
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        style={{ color: 'var(--text-secondary)', maxWidth: 520, margin: '0 auto', lineHeight: 1.8 }}
      >
        A four-layer detection pipeline — Rules, Smurf-Weighting, Louvain Community Detection,
        and Graph Neural Networks — where each concentric layer of defense
        catches what the previous one missed.
      </motion.p>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        style={{
          fontFamily: 'var(--font-mono)', fontSize: 11,
          color: 'var(--text-muted)', marginTop: 24, letterSpacing: '1px',
        }}
      >
        Built for Indian Overseas Bank (IOB) | RBI-Compliant | FIU-IND v2.1
      </motion.p>
    </div>
  );
}
