import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { alertPath } from '../utils/safeNavigation';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import useAlertStream from '../hooks/useAlertStream';
import StatCard from '../components/StatCard';
import {
  API_ALERTS_QUEUE_LIMIT,
  ALERT_POLL_INTERVAL_MS,
  PRIORITY_CRITICAL_THRESHOLD,
  PRIORITY_HIGH_THRESHOLD,
  SCORE_BAR_CRITICAL,
  SCORE_BAR_HIGH,
  PRIORITY_WEIGHT_RISK,
  PRIORITY_WEIGHT_AMOUNT,
  PRIORITY_WEIGHT_CENTRALITY,
  PRIORITY_WEIGHT_EVIDENCE,
  PRIORITY_WEIGHT_TIME,
  SEVERITY_PRIORITY,
  SAR_PROBABILITY_THRESHOLD,
  AMOUNT_NORMALIZATION_BASE,
  FLASH_ANIMATION_MS,
  DEBOUNCE_MS,
} from '../config';

/* ═══════════════════════════════════════════════════════════════
   AlertQueue — Priority-ranked investigation triage queue
   Connects to GET /api/v1/alerts  +  PATCH /api/v1/alerts/:id
   Falls back to inline demo data if API unavailable.
   ═══════════════════════════════════════════════════════════════ */

/* ── Demo data (mirrors _StubRepo in alert_service.py) ─────────── */

const DEMO_ALERTS = [
  {
    alert_id: 'ALT-0001', severity: 'CRITICAL', status: 'OPEN',
    risk_score: 0.91, total_amount: 1850000, account_count: 6,
    txn_count: 24, priority_score: 0.88, sar_filing_probability: 0.92,
    investigation_complexity: 'HIGH',
    created_at: new Date(Date.now() - 1800000).toISOString(),
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
    created_at: new Date(Date.now() - 3600000).toISOString(),
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
    created_at: new Date(Date.now() - 7200000).toISOString(),
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
    created_at: new Date(Date.now() - 14400000).toISOString(),
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

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const SEV_CONFIG = {
  CRITICAL: { color: 'var(--critical)',   bg: 'var(--critical-dim)', cls: 'badge-CRITICAL' },
  HIGH:     { color: 'var(--high)',       bg: 'var(--high-dim)',     cls: 'badge-HIGH' },
  MEDIUM:   { color: 'var(--medium)',     bg: 'var(--medium-dim)',   cls: 'badge-MEDIUM' },
  LOW:      { color: 'var(--accent-green)', bg: 'rgba(16,185,129,0.10)', cls: 'badge-MEDIUM' },
};

const STATUS_CONFIG = {
  OPEN:         { cls: 'badge-OPEN' },
  UNDER_REVIEW: { cls: 'badge-UNDER_REVIEW' },
  RESOLVED:     { cls: 'badge-RESOLVED' },
  ESCALATED:    { cls: 'badge-CRITICAL' },
  FALSE_POSITIVE: { cls: 'badge-FALSE_POSITIVE' },
};

const COMPLEXITY_COLORS = { HIGH: 'var(--critical)', MEDIUM: 'var(--high)', LOW: 'var(--accent-green)' };

const BREAKDOWN_LABELS = {
  risk_score:          'Risk',
  amount_factor:       'Amount',
  network_centrality:  'Network',
  evidence_diversity:  'Evidence',
  time_sensitivity:    'Recency',
};

/* ── Sub-components ─────────────────────────────────────────────── */

function ScoreBar({ value, color = 'var(--emerald)' }) {
  return (
    <div style={{ flex: 1, height: 3, background: 'var(--border-strong)', borderRadius: 2, overflow: 'hidden' }}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.round(value * 100)}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        style={{ height: '100%', background: color, borderRadius: 2 }}
      />
    </div>
  );
}

function PriorityRing({ score, rank }) {
  const r = 20, circ = 2 * Math.PI * r;
  const pct = Math.round(score * 100);
  const fill = score >= PRIORITY_CRITICAL_THRESHOLD ? 'var(--critical)' : score >= PRIORITY_HIGH_THRESHOLD ? 'var(--high)' : 'var(--accent-green)';
  return (
    <div style={{ position: 'relative', width: 50, height: 50, flexShrink: 0 }}>
      <svg width={50} height={50} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={25} cy={25} r={r} fill="none" stroke="var(--border-strong)" strokeWidth={3} />
        <motion.circle
          cx={25} cy={25} r={r} fill="none"
          stroke={fill} strokeWidth={3} strokeLinecap="round"
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
        <span style={{ fontSize: 7, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', lineHeight: 1 }}>#{rank}</span>
        <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: fill, lineHeight: 1.2 }}>
          {pct}
        </span>
      </div>
    </div>
  );
}

/* ── Expanded detail panel ─────────────────────────────────────── */

function AlertExpandedDetail({ alert, onStatusChange, statusLoading }) {
  const breakdown = alert.score_breakdown || {};

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      style={{ overflow: 'hidden' }}
    >
      <div style={{
        background: 'var(--bg-elevated)',
        borderLeft: `2px solid ${SEV_CONFIG[alert.severity]?.color || 'var(--emerald)'}`,
        borderRadius: '0 0 var(--radius-lg) var(--radius-lg)',
        padding: '18px 22px',
        borderTop: 'none',
        margin: '0 0 4px',
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>

          {/* Score breakdown */}
          <div>
            <p className="section-title" style={{ marginBottom: 12 }}>Score breakdown</p>
            {Object.entries(breakdown).map(([key, val]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', width: 64, flexShrink: 0 }}>
                  {BREAKDOWN_LABELS[key] || key}
                </span>
                <ScoreBar value={val} color={val >= SCORE_BAR_CRITICAL ? 'var(--critical)' : val >= SCORE_BAR_HIGH ? 'var(--high)' : 'var(--accent-green)'} />
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', width: 32, textAlign: 'right', fontWeight: 600 }}>
                  {Math.round(val * 100)}
                </span>
              </div>
            ))}
          </div>

          {/* Reason codes + SAR prob */}
          <div>
            <p className="section-title" style={{ marginBottom: 12 }}>Reason codes</p>
            {(alert.reason_codes || []).map((rc, i) => (
              <div key={i} className="reason-code" style={{ fontSize: 11 }}>
                {rc}
              </div>
            ))}
            <div style={{
              marginTop: 14, padding: '10px 12px', borderRadius: 'var(--radius)',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
            }}>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                SAR filing probability
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <ScoreBar value={alert.sar_filing_probability || 0} color="var(--critical)" />
                <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--critical)' }}>
                  {Math.round((alert.sar_filing_probability || 0) * 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* Network nodes summary + status action */}
          <div>
            <p className="section-title" style={{ marginBottom: 12 }}>Accounts involved</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14, maxHeight: 120, overflowY: 'auto' }}>
              {(alert.nodes || []).slice(0, 6).map(n => {
                const roleColor = {
                  SOURCE: 'var(--critical)', AGGREGATOR: 'var(--high)',
                  MULE: 'var(--accent-amber)', LEGITIMATE: 'var(--accent-green)',
                }[n.role] || 'var(--text-muted)';
                return (
                  <div key={n.account_id} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '5px 10px', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-card)', border: '1px solid var(--border-subtle)',
                  }}>
                    <span className="account-id">···{n.account_id.slice(-4)}</span>
                    <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: roleColor, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                      {n.role}
                    </span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {Math.round((n.smurf_score || 0) * 100)}%
                    </span>
                  </div>
                );
              })}
              {(alert.nodes || []).length > 6 && (
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textAlign: 'center', padding: 4 }}>
                  +{alert.nodes.length - 6} more
                </span>
              )}
            </div>

            <p className="section-title" style={{ marginBottom: 8 }}>Update status</p>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['UNDER_REVIEW', 'ESCALATED', 'RESOLVED'].map(s => {
                const isActive = alert.status === s;
                const cfg = STATUS_CONFIG[s] || {};
                return (
                  <button
                    key={s}
                    disabled={statusLoading || isActive}
                    onClick={(e) => { e.stopPropagation(); onStatusChange(alert.alert_id, s); }}
                    className={`badge ${cfg.cls || ''}`}
                    style={{
                      cursor: isActive ? 'default' : 'pointer',
                      opacity: isActive ? 0.5 : 1,
                      padding: '4px 10px',
                      fontSize: 10,
                      transition: 'opacity 0.15s',
                    }}
                  >
                    {statusLoading === s ? 'Updating...' : s.replace(/_/g, ' ')}
                  </button>
                );
              })}
            </div>
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
  const [filterSeverity, setFilterSeverity] = useState('ALL');
  const [filterStatus,   setFilterStatus]   = useState('ALL');
  const [expandedId, setExpandedId]   = useState(null);
  const [statusLoading, setStatusLoading]   = useState(null);
  const [usingDemo, setUsingDemo]     = useState(false);
  const [newAlertCount, setNewAlertCount] = useState(0);
  const [seeding, setSeeding]         = useState(false);
  const flashTimer = useRef(null);

  /* ── Reusable fetch ── */
  const fetchAlerts = useCallback(() => {
    const params = new URLSearchParams();
    if (filterSeverity !== 'ALL') params.set('severity', filterSeverity);
    if (filterStatus   !== 'ALL') params.set('status',   filterStatus);
    params.set('limit', String(API_ALERTS_QUEUE_LIMIT));

    return apiFetch(`/api/v1/alerts?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(body => {
        const raw = body?.data?.alerts || body?.alerts || (Array.isArray(body) ? body : []);
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
        return scored;
      })
      .catch(() => {
        const demo = DEMO_ALERTS
          .filter(a => filterSeverity === 'ALL' || a.severity === filterSeverity)
          .filter(a => filterStatus   === 'ALL' || a.status   === filterStatus);
        demo.sort((a, b) => b.priority_score - a.priority_score);
        setAlerts(demo);
        setUsingDemo(true);
        setLoading(false);
        return demo;
      });
  }, [filterSeverity, filterStatus]);
  const fetchRef = useRef(fetchAlerts);
  useEffect(() => { fetchRef.current = fetchAlerts; }, [fetchAlerts]);

  /* ── Initial fetch ── */
  useEffect(() => {
    setLoading(true);
    fetchAlerts();
  }, [fetchAlerts]);

  /* ── SSE live stream ── */
  const fetchDebounce = useRef(null);
  const handleNewAlerts = useCallback((event) => {
    setNewAlertCount(prev => prev + (event.count || 1));
    // Clear flash after 4 seconds
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setNewAlertCount(0), FLASH_ANIMATION_MS);
    // Debounce re-fetch to avoid hammering API on rapid events
    if (fetchDebounce.current) clearTimeout(fetchDebounce.current);
    fetchDebounce.current = setTimeout(() => fetchRef.current(), DEBOUNCE_MS);
  }, []);

  const { connected: sseConnected } = useAlertStream({
    onNewAlerts: handleNewAlerts,
    enabled: !usingDemo,
  });

  /* ── Polling fallback when SSE is not connected ── */
  useEffect(() => {
    if (sseConnected || usingDemo) return;
    const interval = setInterval(() => fetchRef.current(), ALERT_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [sseConnected, usingDemo]);

  /* ── Seed transactions ── */
  const handleSeed = async () => {
    setSeeding(true);
    try {
      const r = await apiFetch('/api/v1/ingest/seed', { method: 'POST' });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        console.warn('Seed failed:', body);
      }
    } catch (err) {
      console.warn('Seed error:', err);
    } finally {
      setSeeding(false);
    }
  };

  /* ── Status update ── */
  const handleStatusChange = async (alertId, newStatus) => {
    setStatusLoading(newStatus);
    try {
      const r = await apiFetch(`/api/v1/alerts/${alertId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!r.ok) throw new Error();
      setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status: newStatus } : a));
    } catch {
      setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status: newStatus } : a));
    } finally {
      setStatusLoading(null);
    }
  };

  /* ── Summary stats ── */
  const stats = useMemo(() => ({
    open:     alerts.filter(a => a.status === 'OPEN').length,
    critical: alerts.filter(a => a.severity === 'CRITICAL').length,
    highSAR:  alerts.filter(a => (a.sar_filing_probability || 0) > SAR_PROBABILITY_THRESHOLD).length,
    totalAmt: alerts.reduce((s, a) => s + (a.total_amount || 0), 0),
  }), [alerts]);

  const severities = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
  const statuses   = ['ALL', 'OPEN', 'UNDER_REVIEW', 'ESCALATED', 'RESOLVED'];

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1200, position: 'relative', zIndex: 1 }}>

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1>Triage Queue</h1>
          <p className="page-meta">
            <span className="comment">// </span>
            ML-ranked by priority score
            <span style={{ margin: '0 8px', color: 'var(--border-strong)' }}>|</span>
            {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
            {usingDemo && (
              <span className="stat-pill" style={{ marginLeft: 10 }}>
                <span className="dot" />
                demo data
              </span>
            )}
            {sseConnected && (
              <span style={{
                marginLeft: 10, display: 'inline-flex', alignItems: 'center', gap: 5,
                fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent-green)',
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--accent-green)',
                  boxShadow: '0 0 6px var(--accent-green)',
                  animation: 'pulse 2s infinite',
                }} />
                Live
              </span>
            )}
            {newAlertCount > 0 && (
              <span style={{
                marginLeft: 10, padding: '2px 8px', borderRadius: 12,
                background: 'var(--critical)', color: '#fff',
                fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)',
                animation: 'flash 0.5s ease-out',
              }}>
                +{newAlertCount} new
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            className="btn btn-ghost btn-sm"
            disabled={seeding}
            onClick={handleSeed}
            title="Send synthetic transactions to Kafka"
          >
            {seeding ? 'Seeding...' : 'Seed Transactions'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { setLoading(true); fetchRef.current(); }}
          >
            Refresh
          </button>
        </div>
      </div>

      {/* ── Summary stat cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        <StatCard label="Open alerts"       value={stats.open}                    color="var(--emerald-light)" />
        <StatCard label="Critical severity" value={stats.critical}                color="var(--critical)" />
        <StatCard label="High SAR risk"     value={stats.highSAR}                color="var(--high)" />
        <StatCard label="Suspicious flow"   value={formatAmount(stats.totalAmt)} color="var(--accent-cyan)" />
      </div>

      {/* ── Filters ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginBottom: 20 }}>
        <span className="filter-label">Severity</span>
        {severities.map(s => {
          const isActive = filterSeverity === s;
          const activeCls = s === 'CRITICAL' ? 'active-critical' : s === 'HIGH' ? 'active-high' : s === 'MEDIUM' ? 'active-medium' : 'active';
          return (
            <button
              key={s}
              onClick={() => setFilterSeverity(s)}
              className={`filter-tab ${isActive ? activeCls : ''}`}
            >
              {s}
            </button>
          );
        })}

        <div className="filter-divider" />

        <span className="filter-label">Status</span>
        {statuses.map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`filter-tab ${filterStatus === s ? 'active' : ''}`}
          >
            {s.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* ── Queue rows ── */}
      {loading ? (
        <div className="loading">
          <div className="spinner" />
          Loading queue...
        </div>
      ) : alerts.length === 0 ? (
        <div className="glass-card" style={{ padding: '48px 32px', textAlign: 'center' }}>
          <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 4 }}>No alerts match current filters</p>
          <p style={{ fontSize: 12, color: 'var(--text-faint)' }}>
            Try adjusting severity or status filters above
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {/* Table header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '56px 1fr 100px 90px 80px 80px 24px',
            gap: 12,
            padding: '0 18px 8px',
            alignItems: 'center',
          }}>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px' }}>Score</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px' }}>Alert</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px' }}>Breakdown</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px', textAlign: 'right' }}>Amount</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px', textAlign: 'center' }}>SAR</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px', textAlign: 'right' }}>Time</span>
            <span />
          </div>

          <AnimatePresence>
            {alerts.map((alert, idx) => {
              const expanded = expandedId === alert.alert_id;
              const sevCfg = SEV_CONFIG[alert.severity] || SEV_CONFIG.MEDIUM;
              const sarPct = Math.round((alert.sar_filing_probability || 0) * 100);

              return (
                <div key={alert.alert_id}>
                  {/* Alert row */}
                  <div
                    onClick={() => {
                      setExpandedId(expanded ? null : alert.alert_id);
                      if (onSelectAlert) onSelectAlert(alert);
                    }}
                    className="glass-card"
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '56px 1fr 100px 90px 80px 80px 24px',
                      gap: 12,
                      padding: '14px 18px',
                      cursor: 'pointer',
                      alignItems: 'center',
                      borderColor: expanded ? sevCfg.color : undefined,
                      borderRadius: expanded ? 'var(--radius-lg) var(--radius-lg) 0 0' : 'var(--radius-lg)',
                      transition: 'border-color 0.2s, box-shadow 0.2s',
                    }}
                  >
                    {/* Priority ring */}
                    <PriorityRing score={alert.priority_score} rank={idx + 1} />

                    {/* Main info */}
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', letterSpacing: '-0.2px' }}>
                          {alert.alert_id}
                        </span>
                        <span className={`badge ${sevCfg.cls}`}>{alert.severity}</span>
                        <span className={`badge ${(STATUS_CONFIG[alert.status] || {}).cls || ''}`}>
                          {alert.status.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 12, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        <span>{alert.account_count} accounts</span>
                        <span>{alert.txn_count} txns</span>
                        <span style={{ color: COMPLEXITY_COLORS[alert.investigation_complexity] }}>
                          {alert.investigation_complexity}
                        </span>
                      </div>
                    </div>

                    {/* Score breakdown mini-bars */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {Object.entries(alert.score_breakdown || {}).slice(0, 3).map(([key, val]) => (
                        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', width: 28, flexShrink: 0 }}>
                            {(BREAKDOWN_LABELS[key] || key).slice(0, 4)}
                          </span>
                          <ScoreBar value={val} color={val >= SCORE_BAR_CRITICAL ? 'var(--critical)' : val >= SCORE_BAR_HIGH ? 'var(--high)' : 'var(--accent-green)'} />
                        </div>
                      ))}
                    </div>

                    {/* Amount */}
                    <span className="amount" style={{ textAlign: 'right', fontSize: 13 }}>
                      {formatAmount(alert.total_amount)}
                    </span>

                    {/* SAR probability */}
                    <div style={{ textAlign: 'center' }}>
                      <span style={{
                        fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: sarPct >= SCORE_BAR_CRITICAL * 100 ? 'var(--critical)' : sarPct >= SCORE_BAR_HIGH * 100 ? 'var(--high)' : 'var(--text-muted)',
                      }}>
                        {sarPct}%
                      </span>
                    </div>

                    {/* Time ago */}
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', textAlign: 'right' }}>
                      {timeAgo(alert.created_at)}
                    </span>

                    {/* Chevron */}
                    <motion.span
                      animate={{ rotate: expanded ? 180 : 0 }}
                      transition={{ duration: 0.15 }}
                      style={{ fontSize: 11, color: 'var(--text-faint)', textAlign: 'center' }}
                    >
                      ▾
                    </motion.span>
                  </div>

                  {/* Expanded detail */}
                  <AnimatePresence>
                    {expanded && (
                      <AlertExpandedDetail
                        alert={alert}
                        onStatusChange={handleStatusChange}
                        statusLoading={statusLoading}
                      />
                    )}
                  </AnimatePresence>

                  {/* Open investigation link */}
                  {expanded && (
                    <div style={{ textAlign: 'right', padding: '4px 0 8px' }}>
                      <Link
                        to={alertPath(alert.alert_id)}
                        className="btn btn-primary btn-sm"
                        onClick={(e) => e.stopPropagation()}
                        style={{ textDecoration: 'none' }}
                      >
                        Open full investigation →
                      </Link>
                    </div>
                  )}
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
  const amt    = Math.min(1, Math.log1p(a.total_amount || 0) / Math.log1p(AMOUNT_NORMALIZATION_BASE));
  const nodes  = (a.nodes || []);
  const cent   = nodes.length ? Math.max(...nodes.map(n => n.betweenness_centrality || n.betweenness || 0)) : 0;
  const evid   = Math.min(1, (a.reason_codes || []).length / 10);
  const newAcc = nodes.filter(n => (n.account_age_days || 999) < 7).length;
  const time   = Math.min(1, 0.5 + 0.5 * (newAcc / Math.max(nodes.length, 1)));
  return PRIORITY_WEIGHT_RISK * risk + PRIORITY_WEIGHT_AMOUNT * amt + PRIORITY_WEIGHT_CENTRALITY * cent + PRIORITY_WEIGHT_EVIDENCE * evid + PRIORITY_WEIGHT_TIME * time;
}

function sarProbability(a) {
  const base = SEVERITY_PRIORITY[a.severity?.toUpperCase()] || 0.1;
  return Math.min(1, base + Math.min((a.reason_codes || []).length * 0.02, 0.1));
}

function complexity(a) {
  const score = (a.account_count || 0) + (a.txn_count || 0) / 10 + (a.reason_codes || []).length;
  return score > 15 ? 'HIGH' : score > 5 ? 'MEDIUM' : 'LOW';
}

function breakdown(a) {
  const nodes = a.nodes || [];
  const cent  = nodes.length ? Math.max(...nodes.map(n => n.betweenness_centrality || n.betweenness || 0)) : 0;
  const newAcc = nodes.filter(n => (n.account_age_days || 999) < 7).length;
  return {
    risk_score:         Math.min(1, a.risk_score || 0),
    amount_factor:      Math.min(1, Math.log1p(a.total_amount || 0) / Math.log1p(AMOUNT_NORMALIZATION_BASE)),
    network_centrality: cent,
    evidence_diversity: Math.min(1, (a.reason_codes || []).length / 10),
    time_sensitivity:   Math.min(1, 0.5 + 0.5 * (newAcc / Math.max(nodes.length, 1))),
  };
}
