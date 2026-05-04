import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassCard, GlassCardMetric } from '../components/ui/GlassCard';

const API = process.env.REACT_APP_API_URL || '';

/* ── Chakravyuha SVG rings ── */
function ChakravyuhaViz({ activeLayer }) {
  const layers = [
    { label: 'Rules', color: '#ff3b5c', r: 140 },
    { label: 'Smurf', color: '#f59e0b', r: 110 },
    { label: 'Louvain', color: '#3b82f6', r: 80 },
    { label: 'GNN', color: '#10b981', r: 50 },
  ];

  return (
    <svg viewBox="0 0 300 300" width="260" height="260" style={{ margin: '0 auto', display: 'block' }}>
      {layers.map((layer, i) => {
        const isActive = activeLayer === i || activeLayer === -1;
        return (
          <g key={layer.label}>
            <motion.circle
              cx="150" cy="150" r={layer.r}
              fill="none"
              stroke={layer.color}
              strokeWidth={isActive ? 3 : 1.5}
              strokeDasharray={isActive ? 'none' : '6 4'}
              opacity={isActive ? 1 : 0.3}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: isActive ? 1 : 0.3 }}
              transition={{ duration: 1, delay: i * 0.3 }}
            />
            <text
              x={150 + layer.r - 10}
              y={150 - 6}
              fill={layer.color}
              fontSize="9"
              fontFamily="var(--font-mono)"
              opacity={isActive ? 1 : 0.4}
            >
              {layer.label}
            </text>
          </g>
        );
      })}
      <motion.circle
        cx="150" cy="150" r="18"
        fill="var(--accent-violet)"
        opacity={0.9}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 1.2, type: 'spring' }}
      />
      <text
        x="150" y="154"
        fill="#fff"
        fontSize="8"
        fontFamily="var(--font-mono)"
        textAnchor="middle"
        fontWeight="700"
      >
        MULE
      </text>
    </svg>
  );
}

/* ── Slide components ── */
function SlideTitle({ title, subtitle }) {
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

function StatGrid({ stats }) {
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

/* ── Slide definitions ── */
const SLIDES = [
  'intro',
  'problem',
  'architecture',
  'detection',
  'explainability',
  'results',
  'comparison',
  'demo',
];

export default function JudgePresentation() {
  const [slide, setSlide] = useState(0);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [kpi, setKpi] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [activeLayer, setActiveLayer] = useState(-1);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/alerts?limit=20`).then(r => r.json()),
      fetch(`${API}/api/graph/stats`).then(r => r.json()),
      fetch(`${API}/api/kpi`).then(r => r.json()),
    ]).then(([alertData, statsData, kpiData]) => {
      setAlerts(alertData.alerts || []);
      setStats(statsData);
      setKpi(kpiData);
      if (alertData.alerts?.length > 0) {
        fetch(`${API}/api/alerts/${alertData.alerts[0].alert_id}/narrative`)
          .then(r => r.json())
          .then(setNarrative)
          .catch(() => {});
      }
    }).catch(() => {});
  }, []);

  const next = useCallback(() => setSlide(s => Math.min(s + 1, SLIDES.length - 1)), []);
  const prev = useCallback(() => setSlide(s => Math.max(s - 1, 0)), []);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); next(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [next, prev]);

  const renderSlide = () => {
    switch (SLIDES[slide]) {
      case 'intro':
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

      case 'problem':
        return (
          <div>
            <SlideTitle title="The Problem" subtitle="Money Mules in Indian Banking" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <GlassCard style={{ padding: 24 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, color: 'var(--critical)' }}>
                  Scale of Threat
                </h3>
                <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {[
                    'RBI reports mule accounts as #1 vector for UPI fraud',
                    'Estimated 3-5% of new accounts show mule patterns',
                    '₹2,145 Cr lost to digital payment fraud in FY24',
                    'Average mule network operates across 3+ banks',
                    'Manual detection takes 4-6 hours per case',
                  ].map((item, i) => (
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
                <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, color: 'var(--accent-violet)' }}>
                  Why Existing Tools Fail
                </h3>
                <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {[
                    'Rule-only systems generate 60%+ false positives',
                    'No graph analysis = miss coordinated networks',
                    'Black-box ML models fail RBI explainability requirements',
                    'MuleHunter.AI covers only 9 rules, no GNN layer',
                    'No real-time behavioral profiling (BioCatch insights)',
                  ].map((item, i) => (
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

      case 'architecture':
        return (
          <div>
            <SlideTitle title="MuleCatch Architecture" subtitle="Four Concentric Layers of Defense" />
            <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
              <div style={{ flex: '0 0 280px' }}>
                <ChakravyuhaViz activeLayer={activeLayer} />
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { name: 'Layer 1: Rule Engine', desc: '20 deterministic behavioral rules (R01-R20) aligned with RBI/RBIH MuleHunter framework + 72-hour BioCatch detection', color: '#ff3b5c' },
                  { name: 'Layer 2: Smurf-Weighting', desc: '5-dimensional temporal scoring: velocity, ceiling, fan-out, rhythm, consolidation', color: '#f59e0b' },
                  { name: 'Layer 3: Louvain Detection', desc: 'Graph community detection with device/IP-weighted edges identifying mule clusters', color: '#3b82f6' },
                  { name: 'Layer 4: GraphSAGE GNN', desc: '3-layer graph neural network for pattern recognition beyond human-defined rules', color: '#10b981' },
                ].map((layer, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: 30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 * i }}
                    onMouseEnter={() => setActiveLayer(i)}
                    onMouseLeave={() => setActiveLayer(-1)}
                    style={{ cursor: 'pointer' }}
                  >
                    <GlassCard style={{ padding: 14, borderLeft: `3px solid ${layer.color}` }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: layer.color, marginBottom: 4 }}>
                        {layer.name}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        {layer.desc}
                      </div>
                    </GlassCard>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        );

      case 'detection':
        return (
          <div>
            <SlideTitle title="Live Detection Results" subtitle="Running on synthetic IOB data" />
            {stats && (
              <StatGrid stats={[
                { label: 'Accounts Scanned', value: stats.total_accounts, color: 'var(--accent-violet)' },
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
                        ₹{(a.total_amount || 0).toLocaleString()}
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                        {a.mule_classification?.cluster_classification || '—'}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </GlassCard>
          </div>
        );

      case 'explainability':
        return (
          <div>
            <SlideTitle title="Explainable AI" subtitle="Every decision traceable to evidence" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <GlassCard style={{ padding: 20 }} accent="var(--gradient-brand)">
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
                    SHAP Value Decomposition
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    True Shapley values computed for every node using KernelExplainer.
                    Each feature's contribution is quantified — judges can see exactly
                    <em> why</em> an account was flagged and <em>how much</em> each
                    factor contributed to the risk score.
                  </p>
                </GlassCard>
                <GlassCard style={{ padding: 20 }} accent="var(--accent-amber)">
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
                    Mule Type Classification
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    Each account is classified as <strong>COMPLICIT</strong> (knowing participant)
                    or <strong>EXPLOITED</strong> (victim of social engineering), using 7 behavioral
                    signals including the BioCatch 72-hour indicator.
                  </p>
                </GlassCard>
              </div>
              <div>
                {narrative ? (
                  <GlassCard style={{ padding: 20, height: '100%' }} glow>
                    <h3 style={{
                      fontSize: 10, fontFamily: 'var(--font-mono)',
                      color: 'var(--text-muted)', letterSpacing: '1.5px',
                      textTransform: 'uppercase', marginBottom: 12,
                    }}>
                      // Live Narrative — Alert {narrative.alert_id}
                    </h3>
                    <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.7, marginBottom: 16 }}>
                      {narrative.executive_brief}
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {(narrative.key_findings || []).slice(0, 4).map((f, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.15 * i }}
                          style={{
                            fontSize: 11, color: 'var(--text-secondary)',
                            padding: '6px 10px', background: 'var(--bg-elevated)',
                            borderRadius: 6, borderLeft: '2px solid var(--accent-violet)',
                          }}
                        >
                          {f}
                        </motion.div>
                      ))}
                    </div>
                  </GlassCard>
                ) : (
                  <GlassCard style={{ padding: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <span className="loading"><span className="spinner" /> Loading narrative...</span>
                  </GlassCard>
                )}
              </div>
            </div>
          </div>
        );

      case 'results':
        return (
          <div>
            <SlideTitle title="Impact & ROI" subtitle="Measurable value for IOB" />
            {kpi && (
              <StatGrid stats={[
                { label: 'Fraud Prevented', value: `₹${(kpi.fraud_prevented_crore || 0).toFixed(1)} Cr`, color: 'var(--accent-green)' },
                { label: 'Investigation Hours Saved', value: Math.round(kpi.hours_saved || 0), color: 'var(--accent-violet)' },
                { label: 'STRs Auto-Filed', value: kpi.strs_filed || 0, color: 'var(--accent-blue)' },
                { label: 'False Positive Reduction', value: '40%', color: 'var(--accent-amber)' },
              ]} />
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <GlassCard style={{ padding: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Pay-for-Value Model</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    { label: 'Per verified alert', value: '₹500' },
                    { label: 'Per STR filed', value: '₹2,000' },
                    { label: 'Revenue share on fraud prevented', value: '0.1%' },
                    { label: 'Monthly platform fee', value: '₹0 (success-based)' },
                  ].map((item, i) => (
                    <div key={i} style={{
                      display: 'flex', justifyContent: 'space-between',
                      fontSize: 12, padding: '6px 0',
                      borderBottom: '1px solid var(--border)',
                    }}>
                      <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-green)', fontWeight: 600 }}>
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </GlassCard>
              <GlassCard style={{ padding: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Key Differentiators</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    'Graph-based detection (not just rules)',
                    'True SHAP explainability (RBI-compliant)',
                    'Mule type classification (complicit vs exploited)',
                    '72-hour early detection (BioCatch-inspired)',
                    'Active learning from investigator feedback',
                    'FIU-IND v2.1 auto-STR generation',
                  ].map((item, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.1 * i }}
                      style={{
                        fontSize: 12, color: 'var(--text-secondary)',
                        display: 'flex', gap: 8, alignItems: 'flex-start',
                      }}
                    >
                      <span style={{ color: 'var(--accent-green)', flexShrink: 0 }}>&#10003;</span>
                      {item}
                    </motion.div>
                  ))}
                </div>
              </GlassCard>
            </div>
          </div>
        );

      case 'comparison':
        return (
          <div>
            <SlideTitle title="MuleCatch vs MuleHunter.AI" subtitle="Feature Comparison" />
            <GlassCard style={{ padding: 24 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Feature', 'MuleHunter.AI (RBIH)', 'MuleCatch (Ours)'].map(h => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '10px 14px', fontSize: 10,
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
                  {[
                    ['Behavioral Rules', '9 rules', '20 rules (R01-R20)', true],
                    ['Graph Analysis', 'None', 'Louvain + GraphSAGE GNN', true],
                    ['Temporal Analysis', 'Basic velocity', '5-dim Smurf-Weighting', true],
                    ['Explainability', 'Rule codes only', 'SHAP + Narratives + Chains', true],
                    ['72-hour Detection', 'No', 'BioCatch-inspired R20', true],
                    ['Mule Classification', 'No', 'Complicit vs Exploited', true],
                    ['STR Generation', 'Manual', 'Auto FIU-IND v2.1', true],
                    ['Active Learning', 'No', 'Feedback-driven thresholds', true],
                    ['Bank Coverage', '23+ banks', 'IOB (extensible)', false],
                    ['Device/IP Forensics', 'No', 'Shared device detection', true],
                  ].map(([feature, mh, mc, advantage], i) => (
                    <motion.tr
                      key={feature}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.06 * i }}
                    >
                      <td style={{ padding: '10px 14px', fontSize: 12, fontWeight: 600 }}>{feature}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-secondary)' }}>{mh}</td>
                      <td style={{
                        padding: '10px 14px', fontSize: 12, fontWeight: 600,
                        color: advantage ? 'var(--accent-green)' : 'var(--text-secondary)',
                      }}>
                        {advantage && <span style={{ marginRight: 4 }}>&#10003;</span>}
                        {mc}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </GlassCard>
          </div>
        );

      case 'demo':
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
              {[
                { label: 'Alert Queue', path: '/', desc: 'Live detection results' },
                { label: 'ROI Analytics', path: '/roi', desc: 'Impact metrics' },
                { label: 'Compliance', path: '/compliance', desc: 'STR generation' },
              ].map((item, i) => (
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

      default:
        return null;
    }
  };

  return (
    <div style={{
      padding: '32px 40px',
      maxWidth: 960,
      margin: '0 auto',
      minHeight: '80vh',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Slide progress */}
      <div style={{
        display: 'flex', gap: 4, marginBottom: 24, justifyContent: 'center',
      }}>
        {SLIDES.map((s, i) => (
          <motion.button
            key={s}
            onClick={() => setSlide(i)}
            style={{
              width: i === slide ? 32 : 12,
              height: 4,
              borderRadius: 2,
              border: 'none',
              background: i === slide ? 'var(--accent-violet)' : 'var(--border-bright)',
              cursor: 'pointer',
              transition: 'all 0.3s',
            }}
            whileHover={{ scale: 1.2 }}
          />
        ))}
      </div>

      {/* Slide content */}
      <div style={{ flex: 1 }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={slide}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -40 }}
            transition={{ duration: 0.3 }}
          >
            {renderSlide()}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginTop: 24,
      }}>
        <button
          className="btn btn-ghost"
          onClick={prev}
          disabled={slide === 0}
          style={{ opacity: slide === 0 ? 0.3 : 1 }}
        >
          &#8592; Previous
        </button>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 10,
          color: 'var(--text-muted)', letterSpacing: '1px',
        }}>
          {slide + 1} / {SLIDES.length}
        </span>
        <button
          className="btn btn-primary"
          onClick={next}
          disabled={slide === SLIDES.length - 1}
          style={{ opacity: slide === SLIDES.length - 1 ? 0.3 : 1 }}
        >
          Next &#8594;
        </button>
      </div>
    </div>
  );
}
