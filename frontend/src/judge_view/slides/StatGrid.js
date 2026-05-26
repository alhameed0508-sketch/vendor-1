import React from 'react';
import { motion } from 'framer-motion';
import { GlassCardMetric } from '../../components/ui/GlassCard';

export default function StatGrid({ stats }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, 1fr)`,
      gap: 16,
      marginBottom: 24,
    }}>
      {stats.map((s, i) => (
        <motion.div
          key={s.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 * i }}
        >
          <GlassCardMetric label={s.label} value={s.value} color={s.color} />
        </motion.div>
      ))}
    </div>
  );
}
