import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';
import { apiFetch } from '../auth/api';
import StatCard from '../components/StatCard';
import { formatAmount } from '../utils/formatAmount';
import { statusLabel } from '../utils/statusLabel';

const AXIS_TICK = { fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' };

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
        <p key={i} style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-primary)', margin: 0, fontWeight: 600 }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
};

const percentOr = (value, missing) => (value == null ? missing : `${value}%`);

const EmptyNote = ({ children }) => (
  <p style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }}>{children}</p>
);

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
  const [monthlyTrend, setMonthlyTrend] = useState([]);
  const [detectionBreakdown, setDetectionBreakdown] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/kpi').then(r => r.json()).then(body => body?.data || body),
      apiFetch('/api/v1/feedback/stats').then(r => r.json()).then(body => body?.data || body).catch(err => { console.error('[ROI] Feedback stats fetch failed:', err); return null; }),
      apiFetch('/api/v1/roi').then(r => r.json()).then(body => body?.data || body).catch(err => { console.error('[ROI] ROI data fetch failed:', err); return null; }),
    ]).then(([kpiData, fbData, roiData]) => {
      setKpi(kpiData);
      setFeedbackStats(fbData);
      if (roiData?.monthly_trends?.length) {
        setMonthlyTrend(roiData.monthly_trends);
      }
      if (roiData?.detection_breakdown?.length) {
        const maxCount = Math.max(...roiData.detection_breakdown.map(d => d.count));
        setDetectionBreakdown(roiData.detection_breakdown.map(d => ({
          name: statusLabel(d.pattern || d.name || ''),
          count: d.count,
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
        Loading analytics…
      </span>
    </div>
  );

  return (
    <div className="page">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ marginBottom: 32 }}
      >
        <h1 className="text-page-title" style={{ fontSize: 28, margin: '0 0 6px' }}>
          ROI Analytics
        </h1>
        <p className="text-mono-sm">
          What detection has saved, and how investigator feedback tunes it.
        </p>
      </motion.div>

      {/* Primary KPI Cards */}
      <div className="stat-grid" style={{ marginBottom: 14 }}>
        <StatCard label="Fraud Flagged"             value={formatAmount(kpi?.fraud_flagged_inr ?? kpi?.fraud_prevented_inr)} sub="In flagged clusters. Not verified" />
        <StatCard label="Fraud Prevented (verified)" value={formatAmount(kpi?.fraud_prevented_verified_inr)} sub="Confirmed by investigators" />
        <StatCard label="Investigation Time Saved"  value={percentOr(kpi?.investigation_time_reduction_pct, '—')} sub="Per alert, against manual review" />
        <StatCard label="False Positive Reduction"  value={percentOr(kpi?.false_positive_reduction_pct, 'Not measured')} sub="Against rule-based AML" />
      </div>

      {/* Secondary KPI Cards */}
      <div className="stat-grid stat-grid--3">
        <StatCard label="Manpower Saved" value={kpi?.roi_assumptions?.analyst_hourly_cost_inr ? formatAmount(kpi.manpower_saved_lakh * 100000) : 'Cost not set'} sub={kpi?.hours_saved ? `${kpi.hours_saved.toFixed(0)} hours freed` : '—'} />
        <StatCard label="STRs Filed"     value={kpi?.strs_filed || 0} sub="FIU-ready reports" />
        <StatCard label="Total Alerts"   value={kpi?.total_alerts || 0} sub="this cycle" />
      </div>

      {/* Charts Row */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}
      >
        <ChartPanel title="Fraud Flagged Trend (₹ Lakh)">
          {monthlyTrend.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={monthlyTrend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="prevGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--accent)" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="month" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'var(--border-strong)' }} />
                <Area type="monotone" dataKey="prevented" name="₹ Lakh" stroke="var(--accent)" strokeWidth={2} fill="url(#prevGrad)" dot={false} activeDot={{ r: 4, fill: 'var(--accent)', stroke: 'var(--bg-base)', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <EmptyNote>No monthly figures yet.</EmptyNote>}
        </ChartPanel>

        <ChartPanel title="Hours Saved per Month">
          {monthlyTrend.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={monthlyTrend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="month" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--accent-tint)' }} />
                <Bar dataKey="hours" name="Hours" fill="var(--accent)" radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyNote>No monthly figures yet.</EmptyNote>}
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
            {detectionBreakdown.length === 0 && <EmptyNote>No detections yet.</EmptyNote>}
            {detectionBreakdown.map(d => (
              <div key={d.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-secondary)' }}>{d.name}</span>
                  <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{d.count}</span>
                </div>
                <div style={{ height: 6, background: 'var(--bg-input)', borderRadius: 3, overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${d.pct}%` }}
                    transition={{ duration: 0.8, delay: 0.5, ease: 'easeOut' }}
                    style={{ height: '100%', background: 'var(--accent)', borderRadius: 3 }}
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
                  { v: feedbackStats.total_feedback, l: 'Total Feedback' },
                  { v: `${(feedbackStats.false_positive_rate * 100).toFixed(1)}%`, l: 'FP Rate' },
                ].map(({ v, l }) => (
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
                  { v: feedbackStats.true_positives,  l: 'Confirmed Mules' },
                  { v: feedbackStats.false_positives, l: 'False Positives' },
                ].map(({ v, l }) => (
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
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{feedbackStats.current_smurf_threshold?.toFixed(3) || '0.550'}</span>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 180, flexDirection: 'column', gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', border: '2px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>—</span>
              </div>
              <EmptyNote>No feedback data yet.</EmptyNote>
            </div>
          )}
        </ChartPanel>
      </motion.div>
    </div>
  );
}
