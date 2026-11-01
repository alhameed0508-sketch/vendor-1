import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';
import { apiFetch } from '../auth/api';
import StatCard from '../components/StatCard';

const FALLBACK_MONTHLY_TREND = [
  { month: 'Aug', alerts: 12, prevented: 18.2, hours: 36 },
  { month: 'Sep', alerts: 18, prevented: 27.4, hours: 54 },
  { month: 'Oct', alerts: 14, prevented: 22.1, hours: 42 },
  { month: 'Nov', alerts: 22, prevented: 34.6, hours: 66 },
  { month: 'Dec', alerts: 19, prevented: 30.8, hours: 57 },
  { month: 'Jan', alerts: 28, prevented: 44.2, hours: 84 },
];

const FALLBACK_DETECTION_BREAKDOWN = [
  { name: 'Smurfing',      count: 34, color: '#F43F5E', pct: 100 },
  { name: 'Consolidation', count: 21, color: '#FB923C', pct: 61.7 },
  { name: 'Shared Device', count: 18, color: '#38BDF8', pct: 52.9 },
  { name: 'Bot Pattern',   count: 12, color: '#10B981', pct: 35.3 },
  { name: 'Fan-out',       count: 9,  color: '#22D3EE', pct: 26.5 },
];

const PATTERN_COLORS = {
  'Smurfing': '#F43F5E',
  'Consolidation': '#FB923C',
  'Shared Device': '#38BDF8',
  'Bot Pattern': '#10B981',
  'Fan-out': '#22D3EE',
  'SMURF': '#F43F5E',
  'CONSOLIDATION': '#FB923C',
  'SHARED_DEVICE': '#38BDF8',
  'BOT_PATTERN': '#10B981',
  'FAN_OUT': '#22D3EE',
};

const chartTooltipStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '10px 14px',
  boxShadow: 'var(--shadow)',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={chartTooltipStyle}>
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: p.color, margin: 0, fontWeight: 600 }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
};

function ChartPanel({ title, children }) {
  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      padding: '20px 0',
    }}>
      <p style={{
        fontFamily: 'var(--font-sans)',
        fontSize: 12,
        color: 'var(--text-muted)',
        fontWeight: 700,
        marginBottom: 18,
      }}>{title}</p>
      {children}
    </div>
  );
}

export default function ROIDashboard() {
  const [kpi, setKpi] = useState(null);
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [monthlyTrend, setMonthlyTrend] = useState(FALLBACK_MONTHLY_TREND);
  const [detectionBreakdown, setDetectionBreakdown] = useState(FALLBACK_DETECTION_BREAKDOWN);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/kpi').then(r => r.json()).then(body => body?.data || body),
      apiFetch('/api/v1/feedback/stats').then(r => r.json()).then(body => body?.data || body).catch(err => { console.error('[ROI] Feedback stats fetch failed:', err); return null; }),
      apiFetch('/api/v1/roi').then(r => r.json()).then(body => body?.data || body).catch(err => { console.error('[ROI] ROI data fetch failed:', err); return null; }),
    ]).then(([kpiData, fbData, roiData]) => {
      setKpi(kpiData);
      setFeedbackStats(fbData);
      // Use API data if available, fall back to hardcoded demo data
      if (roiData?.monthly_trends?.length) {
        setMonthlyTrend(roiData.monthly_trends);
      }
      if (roiData?.detection_breakdown?.length) {
        const maxCount = Math.max(...roiData.detection_breakdown.map(d => d.count));
        setDetectionBreakdown(roiData.detection_breakdown.map(d => ({
          name: d.pattern || d.name,
          count: d.count,
          color: PATTERN_COLORS[d.pattern || d.name] || '#94A3B8',
          pct: maxCount > 0 ? (d.count / maxCount) * 100 : 0,
        })));
      }
      setLoading(false);
    }).catch(err => {
      console.error('[ROI] Failed to load KPI data:', err);
      setLoading(false);
    });
  }, []);

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)' }}>
        LOADING ANALYTICS...
      </span>
    </div>
  );

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ marginBottom: 32 }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <h1 className="text-page-title" style={{ fontSize: 28, margin: 0 }}>
            ROI Analytics
          </h1>
          <span style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: '#10B981',
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.2)',
            padding: '2px 8px',
            borderRadius: 4,
          }}>
            LIVE
          </span>
        </div>
        <p className="text-mono-sm">
          Detection metrics · ROI tracking · Active learning feedback
        </p>
      </motion.div>

      {/* Primary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14, marginBottom: 14 }}>
        <StatCard label="Fraud Prevented"           value={`₹${(kpi?.fraud_prevented_crore || 0).toFixed(2)}Cr`} color="#FB923C" sub="flagged cluster amounts" />
        <StatCard label="Investigation Time Saved"  value={`${kpi?.investigation_time_reduction_pct || 75}%`}    color="#22D3EE" sub="4h → 1h per alert" />
        <StatCard label="False Positive Reduction"  value="40%"                                                   color="#10B981" sub="vs. legacy rule-based AML" />
      </div>

      {/* Secondary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14, marginBottom: 24 }}>
        <StatCard label="Manpower Saved" value={`₹${(kpi?.manpower_saved_lakh || 0).toFixed(1)}L`} color="#8B5CF6" sub={kpi?.hours_saved ? `${kpi.hours_saved.toFixed(0)} hours freed` : '—'} />
        <StatCard label="STRs Filed"     value={kpi?.strs_filed || 0}                                color="#38BDF8" sub="FIU-ready reports" />
        <StatCard label="Total Alerts"   value={kpi?.total_alerts || 0}                              color="#F43F5E" sub="this cycle" />
      </div>

      {/* Charts Row */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}
      >
        <ChartPanel title="Fraud Prevention Trend (₹ Lakh)">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={monthlyTrend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="prevGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#FB923C" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#FB923C" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="prevented" name="₹ Lakh" stroke="#FB923C" strokeWidth={2} fill="url(#prevGrad)" dot={false} activeDot={{ r: 4, fill: '#FB923C', stroke: '#0A0A0F', strokeWidth: 2 }} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Hours Saved per Month">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={monthlyTrend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="hoursGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#22D3EE" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#22D3EE" stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }} axisLine={false} tickLine={false} />
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
            {detectionBreakdown.map(d => (
              <div key={d.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: '#94A3B8' }}>{d.name}</span>
                  <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: d.color, fontWeight: 700 }}>{d.count}</span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-input)', borderRadius: 2, overflow: 'hidden' }}>
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
                    borderLeft: '2px solid var(--border)',
                    padding: '14px 16px',
                  }}>
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: 24, fontWeight: 600, color: 'var(--text-primary)' }}>{v}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'var(--font-sans)' }}>{l}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
                {[
                  { v: feedbackStats.true_positives,  l: 'Confirmed Mules',  c: '#10B981' },
                  { v: feedbackStats.false_positives, l: 'False Positives',  c: '#FB923C' },
                ].map(({ v, l, c }) => (
                  <div key={l} style={{
                    borderLeft: '2px solid var(--border)',
                    padding: '12px 16px',
                  }}>
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>{v}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3, fontFamily: 'var(--font-sans)' }}>{l}</div>
                  </div>
                ))}
              </div>
              <div style={{
                paddingTop: 12,
                borderTop: '1px solid var(--border)',
                fontFamily: 'var(--font-sans)',
                fontSize: 12,
                color: 'var(--text-muted)',
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
              <div style={{ width: 32, height: 32, borderRadius: '50%', border: '2px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>—</span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }}>No feedback data yet.</p>
            </div>
          )}
        </ChartPanel>
      </motion.div>
    </div>
  );
}
