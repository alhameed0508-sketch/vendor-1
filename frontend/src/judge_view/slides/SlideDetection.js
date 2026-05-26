import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../../components/ui/GlassCard';
import SlideTitle from './SlideTitle';
import StatGrid from './StatGrid';

export default function SlideDetection({ stats, alerts }) {
  return (
    <div>
      <SlideTitle title="Live Detection Results" subtitle="Running on synthetic IOB data" />
      {stats && (
        <StatGrid stats={[
          { label: 'Accounts Scanned', value: stats.total_accounts, color: 'var(--accent-gold)' },
          { label: 'Transactions Analyzed', value: stats.total_transactions?.toLocaleString(), color: 'var(--accent-blue)' },
          { label: 'Alerts Generated', value: stats.total_alerts, color: 'var(--accent-amber)' },
          { label: 'Critical Alerts', value: stats.critical, color: 'var(--critical)' },
        ]} />
      )}
      <GlassCard style={{ padding: 20, maxHeight: 260, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Alert ID', 'Severity', 'Risk', 'Accounts', 'Amount', 'Mule Type'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '8px 10px', fontSize: 9,
                  fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                  borderBottom: '1px solid var(--border)', letterSpacing: '1px',
                  textTransform: 'uppercase',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {alerts.slice(0, 8).map((a, i) => (
              <motion.tr
                key={a.alert_id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.08 * i }}
              >
                <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                  {a.alert_id}
                </td>
                <td style={{ padding: '8px 10px' }}>
                  <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                </td>
                <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {Math.round(a.risk_score * 100)}%
                </td>
                <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {a.account_count}
                </td>
                <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-amber)' }}>
                  {'\u20B9'}{(a.total_amount || 0).toLocaleString()}
                </td>
                <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                  {a.mule_classification?.cluster_classification || '\u2014'}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </div>
  );
}
