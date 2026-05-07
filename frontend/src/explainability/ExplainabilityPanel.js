import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { apiFetch } from '../auth/api';

/**
 * ExplainabilityPanel
 * Shows a complete breakdown of WHY an alert was flagged:
 *   1. Score Decomposition — waterfall chart of feature contributions
 *   2. Fraud Chain — step-by-step money flow narrative
 *   3. Cycle Detection — round-trip ring visualization
 *   4. AI Summary — plain-English explanation + recommendation
 */
export default function ExplainabilityPanel({ alertId, explanation: propExplanation }) {
  const [explanation, setExplanation] = useState(propExplanation || null);
  const [loading, setLoading] = useState(!propExplanation);
  const [activeTab, setActiveTab] = useState('summary');

  useEffect(() => {
    if (propExplanation) {
      setExplanation(propExplanation);
      setLoading(false);
      return;
    }
    if (!alertId) return;
    apiFetch(`/api/v1/alerts/${alertId}/explanation`)
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setExplanation(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [alertId, propExplanation]);

  if (loading) {
    return (
      <GlassCard className="p-5" hover={false}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="spinner" />
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Generating explanation...
          </span>
        </div>
      </GlassCard>
    );
  }

  if (!explanation) {
    return (
      <GlassCard className="p-5" hover={false}>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          No explanation available for this alert.
        </p>
      </GlassCard>
    );
  }

  const tabs = [
    { key: 'summary', label: 'AI Summary' },
    { key: 'breakdown', label: 'Score Breakdown' },
    { key: 'chain', label: 'Money Flow' },
    { key: 'cycles', label: 'Cycles' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Section header */}
      <AnimateIn>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{
            width: 24, height: 24, borderRadius: 6,
            background: 'var(--gradient-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, color: '#fff', fontWeight: 700,
          }}>
            ?
          </div>
          <span style={{ fontWeight: 700, fontSize: 16 }}>Explainability Engine</span>
          <span style={{
            fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent-green)',
            background: 'rgba(52,199,89,0.1)', padding: '2px 8px', borderRadius: 4,
          }}>
            ACTIVE
          </span>
        </div>
      </AnimateIn>

      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: 4 }}>
        {tabs.map(tab => (
          <motion.button
            key={tab.key}
            className="btn btn-ghost"
            style={{
              fontSize: 11, padding: '5px 12px',
              ...(activeTab === tab.key ? {
                borderColor: 'var(--accent-gold)',
                color: 'var(--accent-gold)',
                background: 'rgba(245,158,11,0.08)',
              } : {}),
            }}
            onClick={() => setActiveTab(tab.key)}
            whileTap={{ scale: 0.97 }}
          >
            {tab.label}
            {tab.key === 'cycles' && explanation.cycles?.length > 0 && (
              <span style={{
                marginLeft: 4, fontSize: 9, background: 'var(--critical)',
                color: '#fff', padding: '1px 4px', borderRadius: 3,
              }}>
                {explanation.cycles.length}
              </span>
            )}
          </motion.button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === 'summary' && (
          <motion.div key="summary" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <SummaryTab explanation={explanation} />
          </motion.div>
        )}
        {activeTab === 'breakdown' && (
          <motion.div key="breakdown" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <ScoreBreakdownTab breakdown={explanation.score_breakdown || []} narrative={explanation.score_narrative} />
          </motion.div>
        )}
        {activeTab === 'chain' && (
          <motion.div key="chain" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <FraudChainTab chain={explanation.fraud_chain || []} narrative={explanation.chain_narrative} />
          </motion.div>
        )}
        {activeTab === 'cycles' && (
          <motion.div key="cycles" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <CyclesTab cycles={explanation.cycles || []} narrative={explanation.cycle_narrative} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


/* ── Summary Tab ──────────────────────────────────────────────────────── */

function SummaryTab({ explanation }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* AI Summary */}
      <GlassCard className="p-5" hover={false} style={{ borderLeft: '3px solid var(--accent-gold)', borderRadius: '0 var(--radius) var(--radius) 0' }}>
        <p className="section-title" style={{ fontSize: 11, marginBottom: 8 }}>AI Summary</p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)' }}>
          {explanation.summary}
        </p>
      </GlassCard>

      {/* Recommendation */}
      <GlassCard className="p-5" hover={false} style={{
        borderLeft: `3px solid ${explanation.severity === 'CRITICAL' ? 'var(--critical)' : explanation.severity === 'HIGH' ? 'var(--high)' : 'var(--accent-cyan)'}`,
        borderRadius: '0 var(--radius) var(--radius) 0',
      }}>
        <p className="section-title" style={{ fontSize: 11, marginBottom: 8 }}>Recommendation</p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)' }}>
          {explanation.recommendation}
        </p>
      </GlassCard>

      {/* Confidence Factors */}
      {explanation.confidence_factors?.length > 0 && (
        <GlassCard className="p-5" hover={false}>
          <p className="section-title" style={{ fontSize: 11, marginBottom: 10 }}>Confidence Factors</p>
          {explanation.confidence_factors.map((f, i) => (
            <motion.div
              key={i}
              style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <span style={{ color: 'var(--accent-green)', fontSize: 12, flexShrink: 0, marginTop: 2 }}>+</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{f}</span>
            </motion.div>
          ))}
        </GlassCard>
      )}
    </div>
  );
}


/* ── Score Breakdown Tab (Waterfall) ──────────────────────────────────── */

function ScoreBreakdownTab({ breakdown, narrative }) {
  const maxContribution = Math.max(...breakdown.map(b => b.contribution), 0.01);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Narrative */}
      <GlassCard className="p-4" hover={false} style={{ borderLeft: '3px solid var(--accent-cyan)', borderRadius: '0 var(--radius) var(--radius) 0' }}>
        <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          {narrative}
        </p>
      </GlassCard>

      {/* Waterfall bars */}
      <GlassCard className="p-5" hover={false}>
        <p className="section-title" style={{ fontSize: 11, marginBottom: 14 }}>Feature Contributions</p>
        {breakdown.map((item, i) => (
          <motion.div
            key={i}
            style={{ marginBottom: 14 }}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                {item.feature.replace(/_/g, ' ')}
              </span>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{
                  fontSize: 9, fontFamily: 'var(--font-mono)', padding: '1px 5px', borderRadius: 3,
                  background: item.severity === 'HIGH' ? 'rgba(255,59,48,0.12)' : 'rgba(255,149,0,0.12)',
                  color: item.severity === 'HIGH' ? 'var(--critical)' : 'var(--high)',
                }}>
                  {item.severity}
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>
                  +{(item.contribution * 100).toFixed(1)}%
                </span>
              </div>
            </div>
            {/* Bar */}
            <div style={{
              height: 6, borderRadius: 3,
              background: 'var(--bg-elevated)',
              overflow: 'hidden',
            }}>
              <motion.div
                style={{
                  height: '100%', borderRadius: 3,
                  background: item.severity === 'HIGH'
                    ? 'linear-gradient(90deg, var(--critical), var(--high))'
                    : 'linear-gradient(90deg, var(--high), var(--accent-amber))',
                }}
                initial={{ width: 0 }}
                animate={{ width: `${(item.contribution / maxContribution) * 100}%` }}
                transition={{ delay: 0.2 + i * 0.06, duration: 0.5, ease: 'easeOut' }}
              />
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.4 }}>
              {item.description}
            </p>
          </motion.div>
        ))}
      </GlassCard>
    </div>
  );
}


/* ── Fraud Chain Tab ──────────────────────────────────────────────────── */

function FraudChainTab({ chain, narrative }) {
  if (!chain.length) {
    return (
      <GlassCard className="p-5" hover={false}>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {narrative || 'No clear money flow chain could be traced.'}
        </p>
      </GlassCard>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Narrative */}
      <GlassCard className="p-4" hover={false} style={{ borderLeft: '3px solid var(--accent-amber)', borderRadius: '0 var(--radius) var(--radius) 0' }}>
        <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          {narrative}
        </p>
      </GlassCard>

      {/* Chain steps */}
      <GlassCard className="p-5" hover={false}>
        <p className="section-title" style={{ fontSize: 11, marginBottom: 14 }}>Money Flow Chain</p>
        <div style={{ position: 'relative', paddingLeft: 24 }}>
          {/* Vertical line */}
          <div style={{
            position: 'absolute', left: 8, top: 4, bottom: 4, width: 2,
            background: 'linear-gradient(to bottom, var(--accent-amber), var(--critical))',
            borderRadius: 1,
          }} />

          {chain.map((step, i) => (
            <motion.div
              key={i}
              style={{ position: 'relative', marginBottom: 16, paddingLeft: 8 }}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
            >
              {/* Dot */}
              <div style={{
                position: 'absolute', left: -20, top: 4,
                width: 10, height: 10, borderRadius: '50%',
                background: i === 0 ? 'var(--accent-amber)' : i === chain.length - 1 ? 'var(--critical)' : 'var(--accent-cyan)',
                border: '2px solid var(--bg-card)',
              }} />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    Step {step.step}
                  </span>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 2 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                      ...{step.from_account.slice(-8)}
                    </span>
                    <span style={{ color: 'var(--text-muted)', margin: '0 6px' }}>&rarr;</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                      ...{step.to_account.slice(-8)}
                    </span>
                  </div>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-amber)', fontWeight: 600 }}>
                  {'\u20B9'}{step.amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </span>
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.4 }}>
                {step.description}
              </p>
            </motion.div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}


/* ── Cycles Tab ──────────────────────────────────────────────────────── */

function CyclesTab({ cycles, narrative }) {
  if (!cycles.length) {
    return (
      <GlassCard className="p-5" hover={false}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--accent-green)', fontSize: 14 }}>{'\u2713'}</span>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {narrative || 'No circular money flows detected.'}
          </p>
        </div>
      </GlassCard>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Narrative */}
      <GlassCard className="p-4" hover={false} style={{ borderLeft: '3px solid var(--critical)', borderRadius: '0 var(--radius) var(--radius) 0' }}>
        <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          {narrative}
        </p>
      </GlassCard>

      {/* Individual cycles */}
      {cycles.map((cycle, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
        >
          <GlassCard className="p-5" hover={false} glow glowColor="rgba(255,59,48,0.08)">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 6px',
                  background: 'rgba(255,59,48,0.12)', color: 'var(--critical)', borderRadius: 3,
                }}>
                  RING {i + 1}
                </span>
                <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {cycle.cycle_length} accounts
                </span>
              </div>
              <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', color: 'var(--critical)', fontWeight: 700 }}>
                {'\u20B9'}{cycle.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
            </div>

            {/* Circular path visualization */}
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center',
              padding: '10px', borderRadius: 8, background: 'var(--bg-elevated)',
            }}>
              {cycle.accounts.map((acc, j) => (
                <React.Fragment key={j}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-cyan)',
                    padding: '2px 6px', background: 'rgba(90,200,250,0.08)', borderRadius: 4,
                  }}>
                    ...{acc.slice(-6)}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                    {j < cycle.accounts.length - 1 ? '\u2192' : '\u21BA'}
                  </span>
                </React.Fragment>
              ))}
            </div>

            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.4 }}>
              {cycle.description}
            </p>
          </GlassCard>
        </motion.div>
      ))}
    </div>
  );
}
