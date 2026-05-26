import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import RiskBar, { RISK_COLORS, RISK_BG } from './RiskBar';

export default function AssessmentResult({ result, aiExplanation, aiLoading, onExplainWithAI }) {
  return (
    <AnimateIn delay={0.15}>
      <GlassCard className="p-5" hover={false} style={{ minHeight: 400 }}>
        <p style={{
          fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
          letterSpacing: '2px', textTransform: 'uppercase', marginBottom: 16,
        }}>
          Assessment Result
        </p>

        {result && !result.error ? (
          <div>
            {/* Risk bar */}
            <RiskBar score={result.risk_score} level={result.risk_level} />

            {/* Risk level badge */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
              padding: '12px 16px', borderRadius: 8,
              background: RISK_BG[result.risk_level] || 'var(--bg-elevated)',
              border: `1px solid ${RISK_COLORS[result.risk_level]}40`,
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                color: RISK_COLORS[result.risk_level], letterSpacing: '1px',
              }}>
                {result.risk_level}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                {result.recommendation}
              </span>
            </div>

            {/* Assessment metadata */}
            <div style={{
              display: 'flex', gap: 16, marginBottom: 16, fontSize: 10,
              fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            }}>
              <span>ID: {result.assessment_id}</span>
              <span>Account: {result.account_id}</span>
            </div>

            {/* Reason codes */}
            {result.reason_codes?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                  letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8,
                }}>
                  Triggered Reason Codes
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {result.reason_codes.map((code, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      style={{
                        fontSize: 11, fontFamily: 'var(--font-mono)',
                        color: 'var(--text-secondary)', padding: '5px 10px',
                        background: 'var(--bg-elevated)', borderRadius: 4,
                        borderLeft: `2px solid ${RISK_COLORS[result.risk_level]}`,
                      }}
                    >
                      {code}
                    </motion.div>
                  ))}
                </div>
              </div>
            )}

            {/* Signal breakdown */}
            <p style={{
              fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8,
            }}>
              Signal Breakdown
            </p>
            <div style={{ maxHeight: 200, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Signal', 'Score', 'Weight', 'Weighted'].map(h => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '4px 8px', fontSize: 9,
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
                  {result.signals?.map((sig) => (
                    <tr key={sig.signal} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {sig.signal.replace(/_/g, ' ')}
                      </td>
                      <td style={{
                        padding: '4px 8px', fontSize: 11, fontFamily: 'var(--font-mono)',
                        color: sig.score >= 0.5 ? 'var(--critical)' : sig.score >= 0.3 ? 'var(--accent-amber)' : 'var(--accent-green)',
                        fontWeight: 600,
                      }}>
                        {sig.score.toFixed(2)}
                      </td>
                      <td style={{ padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {sig.weight}
                      </td>
                      <td style={{ padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {sig.weighted.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Explain with AI button */}
            <div style={{ marginTop: 16 }}>
              <motion.button
                className="btn btn-primary"
                onClick={onExplainWithAI}
                disabled={aiLoading}
                style={{
                  width: '100%', padding: '8px',
                  fontSize: 11, fontWeight: 600, letterSpacing: '0.5px',
                  background: aiExplanation ? 'rgba(62,231,255,0.08)' : undefined,
                  borderColor: 'var(--accent-cyan)',
                }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
              >
                {aiLoading ? 'Analyzing...' : aiExplanation ? 'Refresh AI Explanation' : 'Explain with AI'}
              </motion.button>
            </div>

            {/* AI Explanation */}
            {aiExplanation && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  marginTop: 12, padding: '12px 16px',
                  background: 'rgba(62,231,255,0.04)',
                  border: '1px solid rgba(62,231,255,0.15)',
                  borderRadius: 8,
                }}
              >
                <p style={{
                  fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)',
                  letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8,
                }}>
                  AI Explanation
                </p>
                <p style={{
                  fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                  lineHeight: 1.7, whiteSpace: 'pre-wrap',
                }}>
                  {typeof aiExplanation === 'string' ? aiExplanation : JSON.stringify(aiExplanation, null, 2)}
                </p>
              </motion.div>
            )}
          </div>
        ) : result?.error ? (
          <div style={{
            padding: 16, borderRadius: 8, background: 'rgba(255,92,122,0.08)',
            border: '1px solid rgba(255,92,122,0.2)', color: 'var(--critical)',
            fontSize: 12, fontFamily: 'var(--font-mono)',
          }}>
            {result.error}
          </div>
        ) : (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: '80%', color: 'var(--text-muted)',
          }}>
            <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.12 }}>&#x2B21;</div>
            <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              Submit an assessment to see results
            </p>
          </div>
        )}
      </GlassCard>
    </AnimateIn>
  );
}
