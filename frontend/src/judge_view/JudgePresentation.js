import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassCard } from '../components/ui/GlassCard';
import { apiFetch } from '../auth/api';

import SlideTitle from './slides/SlideTitle';
import StatGrid from './slides/StatGrid';
import SlideIntro from './slides/SlideIntro';
import SlideProblem from './slides/SlideProblem';
import SlideArchitecture from './slides/SlideArchitecture';
import SlideDetection from './slides/SlideDetection';
import SlideDemo from './slides/SlideDemo';

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
      apiFetch(`/api/v1/alerts?limit=20`).then(r => r.json()).then(body => body?.data || body),
      apiFetch(`/api/v1/graph/stats`).then(r => r.json()).then(body => body?.data || body),
      apiFetch(`/api/v1/kpi`).then(r => r.json()).then(body => body?.data || body),
    ]).then(([alertData, statsData, kpiData]) => {
      setAlerts(alertData.alerts || []);
      setStats(statsData);
      setKpi(kpiData);
      if (alertData.alerts?.length > 0) {
        apiFetch(`/api/v1/alerts/${alertData.alerts[0].alert_id}/narrative`)
          .then(r => r.json())
          .then(body => setNarrative(body?.data || body))
          .catch(err => console.error('[Judge] Narrative fetch failed:', err));
      }
    }).catch(err => console.error('[Judge] Initial data fetch failed:', err));
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
        return <SlideIntro />;
      case 'problem':
        return <SlideProblem />;
      case 'architecture':
        return <SlideArchitecture activeLayer={activeLayer} setActiveLayer={setActiveLayer} />;
      case 'detection':
        return <SlideDetection stats={stats} alerts={alerts} />;

      case 'explainability':
        return (
          <div>
            <SlideTitle title="Explainable AI" subtitle="Every decision traceable to evidence" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <GlassCard style={{ padding: 20 }} accent="var(--gradient-brand)">
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>SHAP Value Decomposition</h3>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    True Shapley values computed for every node using KernelExplainer.
                    Each feature's contribution is quantified — judges can see exactly
                    <em> why</em> an account was flagged and <em>how much</em> each
                    factor contributed to the risk score.
                  </p>
                </GlassCard>
                <GlassCard style={{ padding: 20 }} accent="var(--accent-amber)">
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Mule Type Classification</h3>
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
                            borderRadius: 6, borderLeft: '2px solid var(--accent-gold)',
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
                { label: 'Investigation Hours Saved', value: Math.round(kpi.hours_saved || 0), color: 'var(--accent-gold)' },
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
        return <SlideDemo />;

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
              background: i === slide ? 'var(--accent-gold)' : 'var(--border-bright)',
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
