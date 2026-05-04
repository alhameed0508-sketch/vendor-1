import React, { useState, useEffect, useRef } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';
import gsap from 'gsap';
import AnimatedCounter from '../components/AnimatedCounter';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';
import { SkeletonCard } from '../components/Skeleton';

const MONTHLY_TREND = [
  { month: 'Aug', alerts: 12, prevented: 18.2, hours: 36 },
  { month: 'Sep', alerts: 18, prevented: 27.4, hours: 54 },
  { month: 'Oct', alerts: 14, prevented: 22.1, hours: 42 },
  { month: 'Nov', alerts: 22, prevented: 34.6, hours: 66 },
  { month: 'Dec', alerts: 19, prevented: 30.8, hours: 57 },
  { month: 'Jan', alerts: 28, prevented: 44.2, hours: 84 },
];

const DETECTION_BREAKDOWN = [
  { name: 'Smurfing', count: 34, color: '#ff3b5c' },
  { name: 'Consolidation', count: 21, color: '#f59e0b' },
  { name: 'Shared Device', count: 18, color: '#3b82f6' },
  { name: 'Bot Pattern', count: 12, color: '#10b981' },
  { name: 'Fan-out', count: 9, color: '#06b6d4' },
];

const customTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ padding: '10px 14px', background: 'var(--tooltip-bg)', border: '1px solid var(--tooltip-border)', borderRadius: 'var(--radius)', backdropFilter: 'blur(12px)' }}>
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--tooltip-muted)', marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
};

function DetectionBars() {
  const barsRef = useRef(null);

  useEffect(() => {
    if (!barsRef.current) return;
    const fills = barsRef.current.querySelectorAll('.detection-fill');
    gsap.fromTo(fills,
      { width: 0 },
      { width: (i) => `${(DETECTION_BREAKDOWN[i].count / 34) * 100}%`, duration: 0.8, stagger: 0.1, delay: 0.3, ease: 'power2.out' }
    );
  }, []);

  return (
    <div ref={barsRef}>
      {DETECTION_BREAKDOWN.map((d) => (
        <div key={d.name} style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="text-xs font-mono">{d.name}</span>
            <span className="text-xs font-mono" style={{ color: d.color }}>
              <AnimatedCounter end={d.count} style={{ color: d.color }} />
            </span>
          </div>
          <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
            <div className="detection-fill" style={{ height: '100%', width: 0, background: d.color, borderRadius: 2 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ROIDashboard() {
  const [kpi, setKpi] = useState(null);
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retraining, setRetraining] = useState(false);
  const [retrained, setRetrained] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch('/api/kpi').then(r => r.json()),
      fetch('/api/feedback/stats').then(r => r.json()).catch(() => null),
    ]).then(([kpiData, fbData]) => {
      setKpi(kpiData);
      setFeedbackStats(fbData);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        {[0,1,2,3,4,5].map(i => <SkeletonCard key={i} style={{ height: 120 }} />)}
      </div>
    </div>
  );

  const kpiCards = [
    { label: 'Investigation Time Reduction', rawValue: kpi?.investigation_time_reduction_pct || 75, suffix: '%', sub: 'from 4h → 1h per alert', color: 'var(--accent-cyan)', desc: 'Methodology: baseline 4h avg × alerts resolved' },
    { label: 'False Positive Reduction', rawValue: 40, suffix: '%', sub: 'vs. legacy rule-based AML', color: 'var(--accent-green)', desc: 'Measured vs. synthetic dataset baseline' },
    { label: 'Estimated Fraud Prevented', rawValue: kpi?.fraud_prevented_crore || 0, prefix: '₹', suffix: 'Cr', decimals: 2, sub: 'current detection cycle', color: 'var(--accent-amber)', desc: 'Sum of flagged cluster amounts' },
    { label: 'Manpower Saved', rawValue: kpi?.manpower_saved_lakh || 0, prefix: '₹', suffix: 'L', decimals: 1, subValue: kpi?.hours_saved ? `${kpi.hours_saved.toFixed(0)} hours freed` : '0 hours freed', color: 'var(--accent-blue)', desc: '@ ₹500/hr fully-loaded investigator cost' },
    { label: 'STRs Filed', rawValue: kpi?.strs_filed || 0, sub: 'FIU-ready reports', color: '#a78bfa', desc: 'Alerts with risk_score > 0.7' },
    { label: 'Total Alerts', rawValue: kpi?.total_alerts || 0, sub: 'this cycle', color: 'var(--text-primary)', desc: 'Louvain + Smurf-weighting combined' },
  ];

  return (
    <div style={{ padding: 24 }}>
      <AnimateIn>
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>ROI Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Quantified value metrics for IOB leadership · Pay-for-Value model tracking
          </p>
        </div>
      </AnimateIn>

      {/* KPI cards with animated counters */}
      <StaggerContainer className="kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        {kpiCards.map((k) => (
          <StaggerItem key={k.label}>
            <GlassCard className="p-5">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: 32, fontWeight: 800, fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
                    <AnimatedCounter
                      end={k.rawValue}
                      prefix={k.prefix || ''}
                      suffix={k.suffix || ''}
                      decimals={k.decimals || 0}
                      style={{ fontSize: 32, fontWeight: 800, color: k.color, fontFamily: 'var(--font-mono)' }}
                    />
                  </div>
                  <div style={{ fontWeight: 700, marginTop: 8, fontSize: 13 }}>{k.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{k.subValue || k.sub}</div>
                </div>
              </div>
              <div style={{
                marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border)',
                fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                display: 'flex', alignItems: 'center', gap: 6
              }}>
                <span style={{ color: 'var(--accent-cyan)' }}>ℹ</span> {k.desc}
              </div>
            </GlassCard>
          </StaggerItem>
        ))}
      </StaggerContainer>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <AnimateIn delay={0.2}>
          <GlassCard className="p-5" hover={false}>
            <p className="section-title">Monthly Fraud Prevention Trend (₹ Lakh)</p>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={MONTHLY_TREND} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="prevGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="month" tick={{ fill: 'var(--chart-axis)', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--chart-axis)', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                <Tooltip content={customTooltip} />
                <Area type="monotone" dataKey="prevented" name="₹ Lakh prevented" stroke="#f59e0b" strokeWidth={2} fill="url(#prevGrad)" isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              </AreaChart>
            </ResponsiveContainer>
          </GlassCard>
        </AnimateIn>

        <AnimateIn delay={0.25}>
          <GlassCard className="p-5" hover={false}>
            <p className="section-title">Investigator Hours Saved per Month</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={MONTHLY_TREND} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="month" tick={{ fill: 'var(--chart-axis)', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--chart-axis)', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                <Tooltip content={customTooltip} />
                <Bar dataKey="hours" name="Hours saved" fill="#06b6d4" radius={[3, 3, 0, 0]} fillOpacity={0.8} isAnimationActive={true} animationDuration={1200} animationEasing="ease-out" />
              </BarChart>
            </ResponsiveContainer>
          </GlassCard>
        </AnimateIn>
      </div>

      {/* Detection breakdown + Feedback + Pay-for-Value model */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        {/* Pattern breakdown - GSAP animated bars */}
        <AnimateIn delay={0.3}>
          <GlassCard className="p-5" hover={false}>
            <p className="section-title">Detection by Pattern Type</p>
            <DetectionBars />
          </GlassCard>
        </AnimateIn>

        {/* Feedback & Active Learning Stats */}
        <AnimateIn delay={0.35}>
          <GlassCard className="p-5" hover={false}>
            <p className="section-title">Active Learning Feedback</p>
            {feedbackStats ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <div className="text-2xl font-extrabold font-mono">
                      <AnimatedCounter
                        end={feedbackStats.total_feedback}
                        style={{ color: 'var(--accent-cyan)', fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-mono)' }}
                      />
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">Total Feedback</div>
                  </div>
                  <div>
                    <div className="text-2xl font-extrabold font-mono">
                      <AnimatedCounter
                        end={parseFloat((feedbackStats.false_positive_rate * 100).toFixed(1))}
                        suffix="%"
                        decimals={1}
                        style={{ color: feedbackStats.false_positive_rate > 0.3 ? 'var(--critical)' : 'var(--accent-green)', fontSize: 24, fontWeight: 800, fontFamily: 'var(--font-mono)' }}
                      />
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">False Positive Rate</div>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <div className="text-base font-bold font-mono">
                      <AnimatedCounter
                        end={feedbackStats.true_positives}
                        style={{ color: 'var(--accent-green)', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}
                      />
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">Confirmed Mules</div>
                  </div>
                  <div>
                    <div className="text-base font-bold font-mono">
                      <AnimatedCounter
                        end={feedbackStats.false_positives}
                        style={{ color: 'var(--accent-amber)', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}
                      />
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">False Positives</div>
                  </div>
                </div>
                {/* FP rate bar */}
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
                  <div className="text-xs font-mono text-[var(--text-muted)] mb-1.5">False Positive Rate</div>
                  <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                    <motion.div
                      style={{
                        height: '100%',
                        background: feedbackStats.false_positive_rate > 0.3 ? 'var(--critical)' : 'var(--accent-green)',
                        borderRadius: 3,
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: `${feedbackStats.false_positive_rate * 100}%` }}
                      transition={{ duration: 1, delay: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
                    />
                  </div>
                  <div className="mt-2 text-xs font-mono text-[var(--text-muted)]">
                    Smurf Threshold: <span style={{ color: 'var(--accent-cyan)' }}>{feedbackStats.current_smurf_threshold?.toFixed(3) || '0.550'}</span>
                    {feedbackStats.recommended_threshold_delta !== 0 && (
                      <span style={{ color: feedbackStats.recommended_threshold_delta > 0 ? 'var(--critical)' : 'var(--accent-green)', marginLeft: 8 }}>
                        ({feedbackStats.recommended_threshold_delta > 0 ? '+' : ''}{feedbackStats.recommended_threshold_delta})
                      </span>
                    )}
                  </div>
                  {feedbackStats.retraining_recommended && (
                    <div className="mt-2" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="text-xs text-[var(--accent-amber)] font-mono">
                        Retraining recommended ({feedbackStats.total_feedback} items)
                      </span>
                      <motion.button
                        className={`btn ${retrained ? 'btn-success' : 'btn-primary'}`}
                        style={{ fontSize: 11, padding: '3px 10px' }}
                        disabled={retraining || retrained}
                        whileHover={{ scale: 1.03 }}
                        whileTap={{ scale: 0.97 }}
                        onClick={async () => {
                          setRetraining(true);
                          try {
                            await fetch('/api/feedback/retrain', { method: 'POST' });
                            setRetraining(false);
                            setRetrained(true);
                          } catch {
                            setRetraining(false);
                          }
                        }}
                      >
                        {retraining ? 'Retraining...' : retrained ? '✓ Retrained' : 'Trigger Retrain'}
                      </motion.button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No feedback data available yet.</p>
            )}
          </GlassCard>
        </AnimateIn>

        {/* Pay-for-Value model */}
        <AnimateIn delay={0.4}>
          <GlassCard className="p-5" hover={false}>
            <p className="section-title">Pay-for-Value Subscription Model</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { phase: 'Phase 1', title: 'Pilot (0 cost)', desc: 'Limited-scope R&D on UPI transactions. Zero financial commitment for IOB.', color: 'var(--accent-green)', active: true },
                { phase: 'Phase 2', title: 'Pay-for-Value', desc: 'X% of verified fraud losses prevented per quarter. OpEx, not CapEx.', color: 'var(--accent-cyan)', active: false },
                { phase: 'Phase 3', title: 'Strategic Partnership', desc: 'Co-development, full CBS integration, cross-bank federated intelligence.', color: '#a78bfa', active: false },
              ].map((p, i) => (
                <motion.div
                  key={p.phase}
                  initial={{ opacity: 0, x: 30 }}
                  animate={{ opacity: p.active ? 1 : 0.7, x: 0 }}
                  transition={{ delay: 0.8 + i * 0.15, type: 'spring', stiffness: 200, damping: 25 }}
                  style={{
                    padding: '12px 14px',
                    border: `1px solid ${p.active ? p.color : 'var(--border)'}`,
                    borderLeft: `3px solid ${p.color}`,
                    borderRadius: '0 6px 6px 0',
                    background: p.active ? `${p.color}10` : 'var(--bg-elevated)',
                    boxShadow: p.active ? `0 0 16px ${p.color}20` : 'none',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span className="font-mono text-[10px]" style={{ color: p.color }}>{p.phase}</span>
                    {p.active && <span className="font-mono text-[10px] text-accent-green">● ACTIVE</span>}
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 3 }}>{p.title}</div>
                  <div className="text-xs text-[var(--text-muted)]">{p.desc}</div>
                </motion.div>
              ))}
            </div>
          </GlassCard>
        </AnimateIn>
      </div>
    </div>
  );
}
