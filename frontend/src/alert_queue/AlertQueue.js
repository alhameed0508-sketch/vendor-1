import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/* ═══════════════════════════════════════════════════════════════
   AlertQueue — Priority-ranked investigation triage queue
   Connects to GET /api/v1/alerts  +  POST /api/v1/alerts/:id
   Falls back to inline demo data if API unavailable.
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

/* ── Demo data (mirrors _StubRepo in alert_service.py) ─────────── */

const DEMO_ALERTS = [
  {
    alert_id: 'ALT-0001', severity: 'CRITICAL', status: 'OPEN',
    risk_score: 0.91, total_amount: 1850000, account_count: 6,
    txn_count: 24, priority_score: 0.88, sar_filing_probability: 0.92,
    investigation_complexity: 'HIGH',
    score_breakdown: { risk_score: 0.91, amount_factor: 1.0, network_centrality: 0.78, evidence_diversity: 0.40, time_sensitivity: 0.90 },
    reason_codes: ['R01: Rapid fund aggregation', 'R02: Structured deposits below ₹2L', 'R03: Shared device fingerprint', 'R04: New account (<7 days)'],
    nodes: [
      { account_id: 'AC001', role: 'SOURCE',      smurf_score: 0.93, betweenness_centrality: 0.62, account_age_days: 3,   bank: 'IOB',  city: 'Chennai',     kyc_status: 'PARTIAL'  },
      { account_id: 'AC002', role: 'AGGREGATOR',  smurf_score: 0.88, betweenness_centrality: 0.78, account_age_days: 5,   bank: 'IOB',  city: 'Chennai',     kyc_status: 'PARTIAL'  },
      { account_id: 'AC003', role: 'MULE',        smurf_score: 0.76, betweenness_centrality: 0.31, account_age_days: 12,  bank: 'SBI',  city: 'Coimbatore',  kyc_status: 'PENDING'  },
      { account_id: 'AC004', role: 'MULE',        smurf_score: 0.71, betweenness_centrality: 0.22, account_age_days: 8,   bank: 'SBI',  city: 'Madurai',     kyc_status: 'PENDING'  },
      { account_id: 'AC005', role: 'MULE',        smurf_score: 0.68, betweenness_centrality: 0.18, account_age_days: 6,   bank: 'BOI',  city: 'Trichy',      kyc_status: 'PENDING'  },
      { account_id: 'AC006', role: 'LEGITIMATE',  smurf_score: 0.12, betweenness_centrality: 0.05, account_age_days: 420, bank: 'IOB',  city: 'Chennai',     kyc_status: 'COMPLETE' },
    ],
    edges: [
      { from_account: 'AC001', to_account: 'AC002', total_amount: 750000, txn_count: 8, pattern: 'SMURFING'      },
      { from_account: 'AC001', to_account: 'AC003', total_amount: 450000, txn_count: 5, pattern: 'SMURFING'      },
      { from_account: 'AC002', to_account: 'AC004', total_amount: 380000, txn_count: 6, pattern: 'CONSOLIDATION' },
      { from_account: 'AC002', to_account: 'AC005', total_amount: 270000, txn_count: 5, pattern: 'SMURFING'      },
    ],
  },
  {
    alert_id: 'ALT-0002', severity: 'HIGH', status: 'OPEN',
    risk_score: 0.74, total_amount: 620000, account_count: 4,
    txn_count: 11, priority_score: 0.67, sar_filing_probability: 0.64,
    investigation_complexity: 'MEDIUM',
    score_breakdown: { risk_score: 0.74, amount_factor: 0.82, network_centrality: 0.55, evidence_diversity: 0.20, time_sensitivity: 0.60 },
    reason_codes: ['R02: Structured deposits below ₹2L', 'R05: UPI velocity spike'],
    nodes: [
      { account_id: 'AC010', role: 'SOURCE', smurf_score: 0.77, betweenness_centrality: 0.55, account_age_days: 14, bank: 'IOB',  city: 'Bangalore', kyc_status: 'PARTIAL'  },
      { account_id: 'AC011', role: 'MULE',   smurf_score: 0.65, betweenness_centrality: 0.33, account_age_days: 21, bank: 'HDFC', city: 'Bangalore', kyc_status: 'PENDING'  },
      { account_id: 'AC012', role: 'MULE',   smurf_score: 0.59, betweenness_centrality: 0.28, account_age_days: 18, bank: 'HDFC', city: 'Mysore',    kyc_status: 'PENDING'  },
      { account_id: 'AC013', role: 'LEGITIMATE', smurf_score: 0.08, betweenness_centrality: 0.04, account_age_days: 730, bank: 'IOB', city: 'Bangalore', kyc_status: 'COMPLETE' },
    ],
    edges: [
      { from_account: 'AC010', to_account: 'AC011', total_amount: 320000, txn_count: 6, pattern: 'SMURFING' },
      { from_account: 'AC010', to_account: 'AC012', total_amount: 300000, txn_count: 5, pattern: 'SMURFING' },
    ],
  },
  {
    alert_id: 'ALT-0003', severity: 'MEDIUM', status: 'UNDER_REVIEW',
    risk_score: 0.52, total_amount: 210000, account_count: 3,
    txn_count: 7, priority_score: 0.44, sar_filing_probability: 0.34,
    investigation_complexity: 'LOW',
    score_breakdown: { risk_score: 0.52, amount_factor: 0.61, network_centrality: 0.40, evidence_diversity: 0.10, time_sensitivity: 0.50 },
    reason_codes: ['R03: Shared device fingerprint'],
    nodes: [
      { account_id: 'AC020', role: 'SOURCE', smurf_score: 0.54, betweenness_centrality: 0.40, account_age_days: 30, bank: 'IOB', city: 'Mumbai', kyc_status: 'COMPLETE' },
      { account_id: 'AC021', role: 'MULE',   smurf_score: 0.48, betweenness_centrality: 0.22, account_age_days: 45, bank: 'PNB', city: 'Pune',   kyc_status: 'PARTIAL'  },
      { account_id: 'AC022', role: 'MULE',   smurf_score: 0.44, betweenness_centrality: 0.18, account_age_days: 60, bank: 'PNB', city: 'Nagpur', kyc_status: 'PARTIAL'  },
    ],
    edges: [
      { from_account: 'AC020', to_account: 'AC021', total_amount: 120000, txn_count: 4, pattern: 'CONSOLIDATION' },
      { from_account: 'AC020', to_account: 'AC022', total_amount: 90000,  txn_count: 3, pattern: 'CONSOLIDATION' },
    ],
  },
  {
    alert_id: 'ALT-0004', severity: 'HIGH', status: 'RESOLVED',
    risk_score: 0.69, total_amount: 430000, account_count: 3,
    txn_count: 9, priority_score: 0.58, sar_filing_probability: 0.62,
    investigation_complexity: 'MEDIUM',
    score_breakdown: { risk_score: 0.69, amount_factor: 0.74, network_centrality: 0.48, evidence_diversity: 0.20, time_sensitivity: 0.55 },
    reason_codes: ['R01: Rapid fund aggregation', 'R04: New account (<7 days)'],
    nodes: [
      { account_id: 'AC030', role: 'SOURCE', smurf_score: 0.71, betweenness_centrality: 0.50, account_age_days: 6,  bank: 'IOB', city: 'Hyderabad', kyc_status: 'PARTIAL' },
      { account_id: 'AC031', role: 'MULE',   smurf_score: 0.60, betweenness_centrality: 0.30, account_age_days: 9,  bank: 'SBI', city: 'Hyderabad', kyc_status: 'PENDING' },
      { account_id: 'AC032', role: 'MULE',   smurf_score: 0.55, betweenness_centrality: 0.25, account_age_days: 11, bank: 'SBI', city: 'Warangal',  kyc_status: 'PENDING' },
    ],
    edges: [
      { from_account: 'AC030', to_account: 'AC031', total_amount: 230000, txn_count: 5, pattern: 'SMURFING' },
      { from_account: 'AC030', to_account: 'AC032', total_amount: 200000, txn_count: 4, pattern: 'SMURFING' },
    ],
  },
];

/* ── Helpers ────────────────────────────────────────────────────── */

function formatAmount(v) {
  if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
  if (v >= 100000)   return `₹${(v / 100000).toFixed(1)}L`;
  if (v >= 1000)     return `₹${(v / 1000).toFixed(0)}K`;
  return `₹${Math.round(v)}`;
}

const SEV_COLORS = {
  CRITICAL:     { bg: 'rgba(228,50,50,0.10)',  border: '#E43232', text: '#C42020' },
  HIGH:         { bg: 'rgba(245,127,23,0.10)', border: '#F57F17', text: '#BF5F00' },
  MEDIUM:       { bg: 'rgba(249,168,37,0.10)', border: '#F9A825', text: '#9C6E00' },
  LOW:          { bg: 'rgba(30,150,100,0.10)', border: '#1E9664', text: '#0D6B46' },
};

const STATUS_COLORS = {
  OPEN:         { bg: 'rgba(33,150,243,0.10)', text: '#0D47A1', border: '#1565C0' },
  UNDER_REVIEW: { bg: 'rgba(156,39,176,0.10)', text: '#6A1B9A', border: '#7B1FA2' },
  RESOLVED:     { bg: 'rgba(76,175,80,0.10)',  text: '#1B5E20', border: '#2E7D32' },
  ESCALATED:    { bg: 'rgba(244,67,54,0.10)',  text: '#B71C1C', border: '#C62828' },
};

const COMPLEXITY_COLORS = { HIGH: '#E43232', MEDIUM: '#F57F17', LOW: '#1E9664' };

const BREAKDOWN_LABELS = {
  risk_score:          'Risk',
  amount_factor:       'Amount',
  network_centrality:  'Network',
  evidence_diversity:  'Evidence',
  time_sensitivity:    'Recency',
};

function ScoreBar({ value, color = '#378ADD' }) {
  return (
    <div style={{ flex: 1, height: 4, background: 'rgba(0,0,0,0.08)', borderRadius: 2, overflow: 'hidden' }}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.round(value * 100)}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        style={{ height: '100%', background: color, borderRadius: 2 }}
      />
    </div>
  );
}

function SeverityBadge({ severity }) {
  const c = SEV_COLORS[severity] || SEV_COLORS.LOW;
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, letterSpacing: '0.5px',
      padding: '2px 8px', borderRadius: 4,
      background: c.bg, border: `1px solid ${c.border}`, color: c.text,
      fontFamily: 'var(--font-mono)',
    }}>
      {severity}
    </span>
  );
}

function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.OPEN;
  return (
    <span style={{
      fontSize: 10, fontWeight: 500, letterSpacing: '0.3px',
      padding: '2px 8px', borderRadius: 4,
      background: c.bg, border: `1px solid ${c.border}`, color: c.text,
      fontFamily: 'var(--font-mono)',
    }}>
      {status.replace('_', ' ')}
    </span>
  );
}

function PriorityRing({ score, rank }) {
  const r = 22, circ = 2 * Math.PI * r;
  const fill = score >= 0.75 ? '#E43232' : score >= 0.5 ? '#F57F17' : '#1E9664';
  return (
    <div style={{ position: 'relative', width: 56, height: 56, flexShrink: 0 }}>
      <svg width={56} height={56} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={28} cy={28} r={r} fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth={4} />
        <motion.circle
          cx={28} cy={28} r={r} fill="none"
          stroke={fill} strokeWidth={4} strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ * (1 - score) }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)' }}>#{rank}</span>
        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-mono)', color: fill, lineHeight: 1 }}>
          {Math.round(score * 100)}
        </span>
      </div>
    </div>
  );
}

/* ── Expanded detail panel ─────────────────────────────────────── */

function AlertDetail({ alert, onStatusChange, statusLoading }) {
  const breakdown = alert.score_breakdown || {};

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.2 }}
      style={{
        margin: '0 0 2px',
        background: 'var(--color-background-secondary)',
        borderLeft: '3px solid var(--color-border-info)',
        borderRadius: '0 0 10px 10px',
        padding: '16px 20px',
        borderTop: 'none',
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>

        {/* Score breakdown */}
        <div>
          <p style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 10 }}>
            Score breakdown
          </p>
          {Object.entries(breakdown).map(([key, val]) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', width: 60, flexShrink: 0 }}>
                {BREAKDOWN_LABELS[key] || key}
              </span>
              <ScoreBar value={val} color={val >= 0.7 ? '#E43232' : val >= 0.4 ? '#F57F17' : '#1D9E75'} />
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)', width: 28, textAlign: 'right' }}>
                {Math.round(val * 100)}%
              </span>
            </div>
          ))}
        </div>

        {/* Reason codes + SAR prob */}
        <div>
          <p style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 10 }}>
            Reason codes
          </p>
          {(alert.reason_codes || []).map((rc, i) => (
            <div key={i} style={{
              fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)',
              padding: '4px 8px', marginBottom: 4,
              background: 'var(--color-background-primary)',
              borderRadius: 4,
              borderLeft: '2px solid var(--color-border-danger)',
            }}>
              {rc}
            </div>
          ))}
          <div style={{ marginTop: 12, padding: '8px 10px', borderRadius: 6, background: 'var(--color-background-primary)', border: '1px solid var(--color-border-tertiary)' }}>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)' }}>SAR probability</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <ScoreBar value={alert.sar_filing_probability || 0} color="#E43232" />
              <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)', color: '#E43232' }}>
                {Math.round((alert.sar_filing_probability || 0) * 100)}%
              </span>
            </div>
          </div>
        </div>

        {/* Network nodes summary + status action */}
        <div>
          <p style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 10 }}>
            Accounts involved
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12, maxHeight: 130, overflowY: 'auto' }}>
            {(alert.nodes || []).map(n => (
              <div key={n.account_id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '4px 8px', borderRadius: 4,
                background: 'var(--color-background-primary)',
                border: '1px solid var(--color-border-tertiary)',
              }}>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
                  ···{n.account_id.slice(-4)}
                </span>
                <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: n.role === 'SOURCE' ? '#E43232' : n.role === 'AGGREGATOR' ? '#F57F17' : n.role === 'MULE' ? '#854F0B' : '#1D9E75' }}>
                  {n.role}
                </span>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)' }}>
                  {Math.round((n.smurf_score || 0) * 100)}%
                </span>
              </div>
            ))}
          </div>

          <p style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 6 }}>
            Update status
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['UNDER_REVIEW', 'ESCALATED', 'RESOLVED'].map(s => (
              <button
                key={s}
                disabled={statusLoading || alert.status === s}
                onClick={() => onStatusChange(alert.alert_id, s)}
                style={{
                  padding: '6px 10px', borderRadius: 6, cursor: alert.status === s ? 'default' : 'pointer',
                  fontSize: 10, fontWeight: 600, fontFamily: 'var(--font-mono)', letterSpacing: '0.5px',
                  background: alert.status === s ? 'var(--color-background-primary)' : 'transparent',
                  border: `1px solid ${STATUS_COLORS[s]?.border || '#888'}`,
                  color: STATUS_COLORS[s]?.text || '#333',
                  opacity: alert.status === s ? 0.5 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                {statusLoading === s ? 'Updating...' : s.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ── Main component ─────────────────────────────────────────────── */

export default function AlertQueue({ onSelectAlert }) {
  const [alerts, setAlerts]           = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [filterSeverity, setFilterSeverity] = useState('ALL');
  const [filterStatus,   setFilterStatus]   = useState('ALL');
  const [expandedId, setExpandedId]   = useState(null);
  const [statusLoading, setStatusLoading]   = useState(null);
  const [usingDemo, setUsingDemo]     = useState(false);

  /* ── Fetch alerts ── */
  useEffect(() => {
    const params = new URLSearchParams();
    if (filterSeverity !== 'ALL') params.set('severity', filterSeverity);
    if (filterStatus   !== 'ALL') params.set('status',   filterStatus);
    params.set('limit', '50');

    setLoading(true);
    fetch(`${API_BASE}/alerts?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        const raw = data.alerts || data || [];
        // Client-side priority scoring if not pre-scored by backend
        const scored = raw.map(a => ({
          ...a,
          priority_score: a.priority_score ?? scorePriority(a),
          sar_filing_probability: a.sar_filing_probability ?? sarProbability(a),
          investigation_complexity: a.investigation_complexity ?? complexity(a),
          score_breakdown: a.score_breakdown ?? breakdown(a),
        }));
        scored.sort((a, b) => b.priority_score - a.priority_score);
        setAlerts(scored);
        setUsingDemo(false);
        setLoading(false);
      })
      .catch(() => {
        // Fall back to demo data
        const demo = DEMO_ALERTS
          .filter(a => filterSeverity === 'ALL' || a.severity === filterSeverity)
          .filter(a => filterStatus   === 'ALL' || a.status   === filterStatus);
        demo.sort((a, b) => b.priority_score - a.priority_score);
        setAlerts(demo);
        setUsingDemo(true);
        setLoading(false);
      });
  }, [filterSeverity, filterStatus]);

  /* ── Status update ── */
  const handleStatusChange = async (alertId, newStatus) => {
    setStatusLoading(newStatus);
    try {
      const r = await fetch(`${API_BASE}/alerts/${alertId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!r.ok) throw new Error();
      setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status: newStatus } : a));
    } catch {
      // Optimistic update even if API fails (demo mode)
      setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status: newStatus } : a));
    } finally {
      setStatusLoading(null);
    }
  };

  /* ── Summary stats ── */
  const stats = useMemo(() => ({
    open:     alerts.filter(a => a.status === 'OPEN').length,
    critical: alerts.filter(a => a.severity === 'CRITICAL').length,
    highSAR:  alerts.filter(a => (a.sar_filing_probability || 0) > 0.6).length,
    totalAmt: alerts.reduce((s, a) => s + (a.total_amount || 0), 0),
  }), [alerts]);

  const severities = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
  const statuses   = ['ALL', 'OPEN', 'UNDER_REVIEW', 'ESCALATED', 'RESOLVED'];

  return (
    <div style={{ fontFamily: 'var(--font-sans)', padding: '20px 0' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 500, color: 'var(--color-text-primary)' }}>
            Investigation queue
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-text-secondary)' }}>
            ML-ranked by priority score · {alerts.length} alerts
            {usingDemo && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>[demo data]</span>}
          </p>
        </div>
        <button
          onClick={() => window.location.reload()}
          style={{ fontSize: 12, padding: '6px 14px', borderRadius: 6, cursor: 'pointer', background: 'transparent', border: '1px solid var(--color-border-secondary)', color: 'var(--color-text-secondary)' }}
        >
          Refresh
        </button>
      </div>

      {/* ── Summary cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 20 }}>
        {[
          { label: 'Open alerts',        value: stats.open,                  color: '#185FA5' },
          { label: 'Critical severity',  value: stats.critical,              color: '#C42020' },
          { label: 'High SAR risk',       value: stats.highSAR,               color: '#854F0B' },
          { label: 'Suspicious flow',     value: formatAmount(stats.totalAmt), color: '#0F6E56' },
        ].map(s => (
          <div key={s.label} style={{
            background: 'var(--color-background-secondary)',
            borderRadius: 10, padding: '12px 14px',
          }}>
            <p style={{ margin: 0, fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {s.label}
            </p>
            <p style={{ margin: '4px 0 0', fontSize: 22, fontWeight: 500, color: s.color, fontFamily: 'var(--font-mono)' }}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* ── Filters ── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', marginRight: 4 }}>Severity</span>
          {severities.map(s => (
            <button key={s} onClick={() => setFilterSeverity(s)} style={{
              fontSize: 10, padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
              fontFamily: 'var(--font-mono)', letterSpacing: '0.3px',
              background: filterSeverity === s ? 'var(--color-background-info)' : 'transparent',
              border: `1px solid ${filterSeverity === s ? 'var(--color-border-info)' : 'var(--color-border-tertiary)'}`,
              color: filterSeverity === s ? 'var(--color-text-info)' : 'var(--color-text-secondary)',
            }}>
              {s}
            </button>
          ))}
        </div>
        <div style={{ width: 1, background: 'var(--color-border-tertiary)', margin: '0 4px' }} />
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', marginRight: 4 }}>Status</span>
          {statuses.map(s => (
            <button key={s} onClick={() => setFilterStatus(s)} style={{
              fontSize: 10, padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
              fontFamily: 'var(--font-mono)', letterSpacing: '0.3px',
              background: filterStatus === s ? 'var(--color-background-info)' : 'transparent',
              border: `1px solid ${filterStatus === s ? 'var(--color-border-info)' : 'var(--color-border-tertiary)'}`,
              color: filterStatus === s ? 'var(--color-text-info)' : 'var(--color-text-secondary)',
            }}>
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* ── Queue rows ── */}
      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 13 }}>
          Loading queue…
        </div>
      ) : alerts.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 13 }}>
          No alerts match current filters
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <AnimatePresence>
            {alerts.map((alert, idx) => {
              const expanded = expandedId === alert.alert_id;
              const sev = SEV_COLORS[alert.severity] || SEV_COLORS.LOW;
              return (
                <div key={alert.alert_id}>
                  <motion.div
                    layout
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.04, duration: 0.25 }}
                    onClick={() => {
                      setExpandedId(expanded ? null : alert.alert_id);
                      if (onSelectAlert) onSelectAlert(alert);
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '12px 16px', cursor: 'pointer',
                      background: 'var(--color-background-primary)',
                      border: `0.5px solid ${expanded ? sev.border : 'var(--color-border-tertiary)'}`,
                      borderRadius: expanded ? '10px 10px 0 0' : 10,
                      borderBottom: expanded ? 'none' : undefined,
                      transition: 'border-color 0.2s, background 0.2s',
                    }}
                    whileHover={{ background: 'var(--color-background-secondary)' }}
                  >
                    {/* Priority ring */}
                    <PriorityRing score={alert.priority_score} rank={idx + 1} />

                    {/* Main info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                        <span style={{ fontSize: 13, fontWeight: 500, fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)' }}>
                          {alert.alert_id}
                        </span>
                        <SeverityBadge severity={alert.severity} />
                        <StatusBadge   status={alert.status} />
                        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: COMPLEXITY_COLORS[alert.investigation_complexity], marginLeft: 'auto' }}>
                          {alert.investigation_complexity} complexity
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 16, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)' }}>
                        <span>{formatAmount(alert.total_amount)}</span>
                        <span>{alert.account_count} accounts</span>
                        <span>{alert.txn_count} txns</span>
                        <span style={{ color: '#E43232' }}>SAR {Math.round((alert.sar_filing_probability || 0) * 100)}%</span>
                      </div>
                    </div>

                    {/* Score breakdown mini-bars */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, width: 100 }}>
                      {Object.entries(alert.score_breakdown || {}).slice(0, 3).map(([key, val]) => (
                        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: 'var(--color-text-tertiary)', width: 32, flexShrink: 0 }}>
                            {BREAKDOWN_LABELS[key]?.slice(0, 4)}
                          </span>
                          <ScoreBar value={val} color={val >= 0.7 ? '#E43232' : val >= 0.4 ? '#F57F17' : '#1D9E75'} />
                        </div>
                      ))}
                    </div>

                    {/* Chevron */}
                    <motion.span
                      animate={{ rotate: expanded ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                      style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginLeft: 4 }}
                    >
                      ▾
                    </motion.span>
                  </motion.div>

                  {/* Expanded detail */}
                  <AnimatePresence>
                    {expanded && (
                      <AlertDetail
                        alert={alert}
                        onStatusChange={handleStatusChange}
                        statusLoading={statusLoading}
                      />
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

/* ── Client-side priority scoring fallback ──────────────────────── */

function scorePriority(a) {
  const risk   = Math.min(1, a.risk_score || 0);
  const amt    = Math.min(1, Math.log1p(a.total_amount || 0) / Math.log1p(1000000));
  const nodes  = (a.nodes || []);
  const cent   = nodes.length ? Math.max(...nodes.map(n => n.betweenness_centrality || 0)) : 0;
  const evid   = Math.min(1, (a.reason_codes || []).length / 10);
  const newAcc = nodes.filter(n => (n.account_age_days || 999) < 7).length;
  const time   = Math.min(1, 0.5 + 0.5 * (newAcc / Math.max(nodes.length, 1)));
  return 0.30 * risk + 0.20 * amt + 0.20 * cent + 0.15 * evid + 0.15 * time;
}

function sarProbability(a) {
  const base = { CRITICAL: 0.9, HIGH: 0.6, MEDIUM: 0.3, LOW: 0.1 }[a.severity?.toUpperCase()] || 0.1;
  return Math.min(1, base + Math.min((a.reason_codes || []).length * 0.02, 0.1));
}

function complexity(a) {
  const score = (a.account_count || 0) + (a.txn_count || 0) / 10 + (a.reason_codes || []).length;
  return score > 15 ? 'HIGH' : score > 5 ? 'MEDIUM' : 'LOW';
}

function breakdown(a) {
  const nodes = a.nodes || [];
  const cent  = nodes.length ? Math.max(...nodes.map(n => n.betweenness_centrality || 0)) : 0;
  const newAcc = nodes.filter(n => (n.account_age_days || 999) < 7).length;
  return {
    risk_score:         Math.min(1, a.risk_score || 0),
    amount_factor:      Math.min(1, Math.log1p(a.total_amount || 0) / Math.log1p(1000000)),
    network_centrality: cent,
    evidence_diversity: Math.min(1, (a.reason_codes || []).length / 10),
    time_sensitivity:   Math.min(1, 0.5 + 0.5 * (newAcc / Math.max(nodes.length, 1))),
  };
}