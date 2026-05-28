import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';
import { apiFetch } from '../auth/api';

const MONTHLY_TREND = [
  { month: 'Aug', alerts: 12, prevented: 18.2, hours: 36 },
  { month: 'Sep', alerts: 18, prevented: 27.4, hours: 54 },
  { month: 'Oct', alerts: 14, prevented: 22.1, hours: 42 },
  { month: 'Nov', alerts: 22, prevented: 34.6, hours: 66 },
  { month: 'Dec', alerts: 19, prevented: 30.8, hours: 57 },
  { month: 'Jan', alerts: 28, prevented: 44.2, hours: 84 },
];

const DETECTION_BREAKDOWN = [
  { name: 'Smurfing',      count: 34, color: '#F43F5E', pct: 100 },
  { name: 'Consolidation', count: 21, color: '#FB923C', pct: 61.7 },
  { name: 'Shared Device', count: 18, color: '#38BDF8', pct: 52.9 },
  { name: 'Bot Pattern',   count: 12, color: '#10B981', pct: 35.3 },
  { name: 'Fan-out',       count: 9,  color: '#22D3EE', pct: 26.5 },
];

const chartTooltipStyle = {
  background: 'rgba(8, 12, 20, 0.95)',
  border: '1px solid rgba(16,185,129,0.25)',
  borderRadius: 6,
  padding: '10px 14px',
  boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={chartTooltipStyle}>
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4A5568', marginBottom: 6, letterSpacing: '1px', textTransform: 'uppercase' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: p.color, margin: 0, fontWeight: 600 }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
};

const cardAnim = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } };
const container = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };

function MetricCard({ label, value, sub, color, accent, index }) {
  return (
    <motion.div
      variants={cardAnim}
      style={{
        background: 'rgba(12, 18, 32, 0.65)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 12,
        padding: '22px 24px',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
        transition: 'border-color 0.25s, box-shadow 0.25s',
      }}
      whileHover={{
        borderColor: `${color}30`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${color}25, inset 0 1px 0 rgba(255,255,255,0.07)`,
        y: -2,
        transition: { duration: 0.2 },
      }}
    >
      {/* Accent top bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${color}, transparent)`,
        opacity: 0.7,
      }} />
      {/* Subtle corner glow */}
      <div style={{
        position: 'absolute', top: -30, left: -30, width: 80, height: 80,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${color}20 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 32,
        fontWeight: 800,
        color,
        letterSpacing: '-1px',
        lineHeight: 1,
        marginBottom: 10,
      }}>{value}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#EDF2F7', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 11, color: '#4A5568', fontFamily: 'var(--font-mono)', letterSpacing: '0.3px' }}>{sub}</div>
    </motion.div>
  );
}

function ChartPanel({ title, children }) {
  return (
    <div style={{
      background: 'rgba(12, 18, 32, 0.65)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 12,
      padding: '22px 24px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
    }}>
      <p style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: '#4A5568',
        textTransform: 'uppercase',
        letterSpacing: '1.5px',
        fontWeight: 700,
        marginBottom: 18,
      }}>// {title}</p>
      {children}
    </div>
  );
}

export default function ROIDashboard() {
  const [kpi, setKpi] = useState(null);
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/kpi').then(r => r.json()).then(body => body?.data || body),
      apiFetch('/api/v1/feedback/stats').then(r => r.json()).then(body => body?.data || body).catch(err => { console.error('[ROI] Feedback stats fetch failed:', err); return null; }),
    ]).then(([kpiData, fbData]) => {
      setKpi(kpiData);
      setFeedbackStats(fbData);
      setLoading(false);
    }).catch(err => {
      console.error('[ROI] Failed to load KPI data:', err);
      setLoading(false);
    });
  }, []);

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '1px', color: '#4A5568' }}>
        LOADING ANALYTICS...
      </span>
    </div>
  );

  return (
    <div style={{ padding: '32px 36px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ marginBottom: 32 }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <h1 className="gradient-text" style={{
            fontSize: 28,
            fontWeight: 700,
            letterSpacing: '-0.5px',
            margin: 0,
          }}>
            ROI Analytics
          </h1>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: '#10B981',
            letterSpacing: '1.5px',
            textTransform: 'uppercase',
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.2)',
            padding: '2px 8px',
            borderRadius: 4,
          }}>
            LIVE
          </span>
        </div>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A5568', letterSpacing: '0.5px' }}>
          // detection metrics · roi tracking · active learning feedback
        </p>
      </motion.div>

      {/* Primary KPI Cards */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14, marginBottom: 14 }}
      >
        <MetricCard
          label="Fraud Prevented"
          value={`₹${(kpi?.fraud_prevented_crore || 0).toFixed(2)}Cr`}
          sub="flagged cluster amounts"
          color="#FB923C"
          index={0}
        />
        <MetricCard
          label="Investigation Time Saved"
          value={`${kpi?.investigation_time_reduction_pct || 75}%`}
          sub="4h → 1h per alert"
          color="#22D3EE"
          index={1}
        />
        <MetricCard
          label="False Positive Reduction"
          value="40%"
          sub="vs. legacy rule-based AML"
          color="#10B981"
          index={2}
        />
      </motion.div>

      {/* Secondary KPI Cards */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14, marginBottom: 24 }}
      >
        <MetricCard
          label="Manpower Saved"
          value={`₹${(kpi?.manpower_saved_lakh || 0).toFixed(1)}L`}
          sub={kpi?.hours_saved ? `${kpi.hours_saved.toFixed(0)} hours freed` : '—'}
          color="#8B5CF6"
          index={3}
        />
        <MetricCard
          label="STRs Filed"
          value={kpi?.strs_filed || 0}
          sub="FIU-ready reports"
          color="#38BDF8"
          index={4}
        />
        <MetricCard
          label="Total Alerts"
          value={kpi?.total_alerts || 0}
          sub="this cycle"
          color="#F43F5E"
          index={5}
        />
      </motion.div>

      {/* Charts Row */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}
      >
        <ChartPanel title="Fraud Prevention Trend (₹ Lakh)">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={MONTHLY_TREND} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="prevGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#FB923C" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#FB923C" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="month" tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="prevented" name="₹ Lakh" stroke="#FB923C" strokeWidth={2} fill="url(#prevGrad)" dot={false} activeDot={{ r: 4, fill: '#FB923C', stroke: '#0A0A0F', strokeWidth: 2 }} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Hours Saved per Month">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={MONTHLY_TREND} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="hoursGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#22D3EE" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#22D3EE" stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="month" tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="hours" name="Hours" fill="url(#hoursGrad)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
      </motion.div>

      {/* Detection + Feedback */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45, duration: 0.4 }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}
      >
        <ChartPanel title="Detection by Pattern">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {DETECTION_BREAKDOWN.map(d => (
              <div key={d.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#94A3B8' }}>{d.name}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: d.color, fontWeight: 700 }}>{d.count}</span>
                </div>
                <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${d.pct}%` }}
                    transition={{ duration: 0.8, delay: 0.5, ease: 'easeOut' }}
                    style={{
                      height: '100%',
                      background: `linear-gradient(90deg, ${d.color}, ${d.color}80)`,
                      borderRadius: 2,
                      boxShadow: `0 0 8px ${d.color}40`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartPanel>

        <ChartPanel title="Active Learning Feedback">
          {feedbackStats ? (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
                {[
                  { v: feedbackStats.total_feedback, l: 'Total Feedback', c: '#22D3EE' },
                  { v: `${(feedbackStats.false_positive_rate * 100).toFixed(1)}%`, l: 'FP Rate', c: feedbackStats.false_positive_rate > 0.3 ? '#F43F5E' : '#10B981' },
                ].map(({ v, l, c }) => (
                  <div key={l} style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: 8,
                    padding: '14px 16px',
                  }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 800, color: c, letterSpacing: '-0.5px' }}>{v}</div>
                    <div style={{ fontSize: 11, color: '#4A5568', marginTop: 4, fontFamily: 'var(--font-mono)' }}>{l}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
                {[
                  { v: feedbackStats.true_positives,  l: 'Confirmed Mules',  c: '#10B981' },
                  { v: feedbackStats.false_positives, l: 'False Positives',  c: '#FB923C' },
                ].map(({ v, l, c }) => (
                  <div key={l} style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: 8,
                    padding: '12px 16px',
                  }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, color: c }}>{v}</div>
                    <div style={{ fontSize: 11, color: '#4A5568', marginTop: 3, fontFamily: 'var(--font-mono)' }}>{l}</div>
                  </div>
                ))}
              </div>
              <div style={{
                paddingTop: 12,
                borderTop: '1px solid rgba(255,255,255,0.05)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: '#4A5568',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}>
                <span>Smurf Threshold</span>
                <span style={{ color: '#10B981', fontWeight: 700 }}>{feedbackStats.current_smurf_threshold?.toFixed(3) || '0.550'}</span>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 180, flexDirection: 'column', gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: '#4A5568', fontSize: 14 }}>—</span>
              </div>
              <p style={{ color: '#4A5568', fontSize: 12, fontFamily: 'var(--font-mono)' }}>No feedback data yet.</p>
            </div>
          )}
        </ChartPanel>
      </motion.div>
    </div>
  );
}
