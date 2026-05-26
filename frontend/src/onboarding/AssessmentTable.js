import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { RISK_COLORS, RISK_BG } from './RiskBar';

export default function AssessmentTable({ assessments }) {
  if (assessments.length === 0) return null;

  return (
    <AnimateIn delay={0.2}>
      <GlassCard style={{ padding: 0, overflow: 'hidden' }} hover={false}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
            letterSpacing: '2px', textTransform: 'uppercase',
          }}>
            Recent Assessments &middot; {assessments.length} results
          </span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Assessment ID</th>
              <th>Account</th>
              <th>Risk Score</th>
              <th>Risk Level</th>
              <th>Signals</th>
              <th>Recommendation</th>
              <th>Assessed At</th>
            </tr>
          </thead>
          <tbody>
            {assessments.map((a, idx) => (
              <motion.tr
                key={a.assessment_id || idx}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
              >
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                  {String(idx + 1).padStart(2, '0')}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-cyan)' }}>
                  {a.assessment_id}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                  {a.account_id}
                </td>
                <td>
                  <div className="risk-bar">
                    <div className="risk-track">
                      <motion.div
                        className={`risk-fill ${a.risk_level === 'CRITICAL' ? 'critical' : a.risk_level === 'HIGH' ? 'high' : 'medium'}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${a.risk_score * 100}%` }}
                        transition={{ duration: 0.6 }}
                      />
                    </div>
                    <span className="risk-val">{(a.risk_score * 100).toFixed(0)}%</span>
                  </div>
                </td>
                <td>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                    color: RISK_COLORS[a.risk_level], background: RISK_BG[a.risk_level],
                    padding: '2px 8px', borderRadius: 4, letterSpacing: '0.5px',
                  }}>
                    {a.risk_level}
                  </span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                  {a.reason_codes?.length || 0} triggered
                </td>
                <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', maxWidth: 180 }}>
                  {a.recommendation?.split('\u2014')[0]?.trim()}
                </td>
                <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {a.assessed_at ? new Date(a.assessed_at).toLocaleTimeString() : '-'}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </AnimateIn>
  );
}
