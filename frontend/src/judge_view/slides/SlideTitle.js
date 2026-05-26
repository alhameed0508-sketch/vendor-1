import React from 'react';
import { motion } from 'framer-motion';

export default function SlideTitle({ title, subtitle }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ textAlign: 'center', marginBottom: 32 }}
    >
      <h1 style={{
        fontFamily: 'var(--font-display)',
        fontSize: 36,
        fontWeight: 700,
        letterSpacing: '-1px',
        background: 'var(--gradient-brand)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        marginBottom: 8,
      }}>
        {title}
      </h1>
      {subtitle && (
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--text-muted)',
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}>
          // {subtitle}
        </p>
      )}
    </motion.div>
  );
}
