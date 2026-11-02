import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { statusLabel } from '../utils/statusLabel';
import { formatAmount } from '../utils/formatAmount';
import { Link, useNavigate } from 'react-router-dom';
import { alertPath } from '../utils/safeNavigation';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import useAlertStream from '../hooks/useAlertStream';
import StatCard from '../components/StatCard';
import BoardView from './BoardView';
import ApprovalDialog from './ApprovalDialog';
import useQueueView from './useQueueView';
import { canMove, requiresApproval } from './boardModel';
import { updateAlertStatus, fileStr } from './alertActions';
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
   Shows an explicit error state if the API is unavailable; never substitutes fake alerts.
   ═══════════════════════════════════════════════════════════════ */


/* ── Helpers ────────────────────────────────────────────────────── */

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
  STR_FILED:    { cls: 'badge-STR_FILED' },
  FALSE_POSITIVE: { cls: 'badge-FALSE_POSITIVE' },
};

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
        <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', lineHeight: 1 }}>#{rank}</span>
        <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-sans)', color: fill, lineHeight: 1.2 }}>
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
        <div className="queue-detail-grid">

          {/* Score breakdown */}
          <div>
            <p className="section-title" style={{ marginBottom: 12 }}>Score breakdown</p>
            {Object.entries(breakdown).map(([key, val]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)', width: 64, flexShrink: 0 }}>
                  {BREAKDOWN_LABELS[key] || key}
                </span>
                <ScoreBar value={val} color={val >= SCORE_BAR_CRITICAL ? 'var(--critical)' : val >= SCORE_BAR_HIGH ? 'var(--high)' : 'var(--accent-green)'} />
                <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-primary)', width: 32, textAlign: 'right', fontWeight: 600 }}>
                  {Math.round(val * 100)}
                </span>
              </div>
            ))}
          </div>

          {/* Reason codes + SAR prob */}
          <div>
            <p className="section-title" style={{ marginBottom: 12 }}>Reason codes</p>
            {(alert.reason_codes || []).map((rc, i) => (
              <div key={i} className="reason-code" style={{ fontSize: 12 }}>
                {rc}
              </div>
            ))}
            <div style={{
              marginTop: 14, padding: '10px 12px', borderRadius: 'var(--radius)',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
            }}>
              <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)', }}>
                SAR filing probability
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <ScoreBar value={alert.sar_filing_probability || 0} color="var(--critical)" />
                <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-sans)', color: 'var(--critical)' }}>
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
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: roleColor, fontWeight: 600, }}>
                      {n.role}
                    </span>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-secondary)' }}>
                      {Math.round((n.smurf_score || 0) * 100)}%
                    </span>
                  </div>
                );
              })}
              {(alert.nodes || []).length > 6 && (
                <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', textAlign: 'center', padding: 4 }}>
                  +{alert.nodes.length - 6} more
                </span>
              )}
            </div>

            <p className="section-title" style={{ marginBottom: 8 }}>Update status</p>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['UNDER_REVIEW', 'STR_FILED', 'RESOLVED'].map(s => {
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
                      fontSize: 12,
                      transition: 'opacity 0.15s',
                    }}
                  >
                    {statusLoading === s ? 'Updating…' : statusLabel(s)}
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
  const [loadError, setLoadError]     = useState(false);
  const [newAlertCount, setNewAlertCount] = useState(0);
  const [seeding, setSeeding]         = useState(false);
  const [view, setView]              = useQueueView();
  const navigate                     = useNavigate();
  const [approvalAlert, setApprovalAlert] = useState(null);
  const [moveError, setMoveError]     = useState(null);
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
        setLoadError(false);
        setLoading(false);
        return scored;
      })
      .catch(() => {
        setAlerts([]);
        setLoadError(true);
        setLoading(false);
        return [];
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
    enabled: !loadError,
  });

  /* ── Polling fallback when SSE is not connected ── */
  useEffect(() => {
    if (sseConnected || loadError) return;
    const interval = setInterval(() => fetchRef.current(), ALERT_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [sseConnected, loadError]);

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
  const applyStatus = (alertId, status) =>
    setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status } : a));

  const handleMove = async (alert, toStatus) => {
    if (!canMove(alert.status, toStatus)) return;
    setMoveError(null);
    if (requiresApproval(toStatus)) {
      setApprovalAlert(alert);
      return;
    }
    setStatusLoading(toStatus);
    try {
      await updateAlertStatus(alert.alert_id, toStatus);
      applyStatus(alert.alert_id, toStatus);
    } catch (e) {
      setMoveError(e.message);
    } finally {
      setStatusLoading(null);
    }
  };

  const handleStatusChange = (alertId, newStatus) => {
    const alert = alerts.find(a => a.alert_id === alertId);
    if (alert) handleMove(alert, newStatus);
  };

  const confirmFiling = async reason => {
    await fileStr(approvalAlert, reason);
    applyStatus(approvalAlert.alert_id, 'STR_FILED');
    setApprovalAlert(null);
  };

  /* ── Summary stats ── */
  const stats = useMemo(() => ({
    open:     alerts.filter(a => a.status === 'OPEN').length,
    critical: alerts.filter(a => a.severity === 'CRITICAL').length,
    highSAR:  alerts.filter(a => (a.sar_filing_probability || 0) > SAR_PROBABILITY_THRESHOLD).length,
    totalAmt: alerts.reduce((s, a) => s + (a.total_amount || 0), 0),
  }), [alerts]);

  const severities = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
  const statuses   = ['ALL', 'OPEN', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE', 'STR_FILED'];

  return (
    <div className="page">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1>Triage</h1>
          <p className="page-meta">
            ML-ranked by priority score
            <span style={{ margin: '0 8px', color: 'var(--border-strong)' }}>|</span>
            {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
            {loadError && (
              <span className="stat-pill" style={{ marginLeft: 10 }}>
                <span className="dot" />
                alert API unavailable, showing no data
              </span>
            )}
            {sseConnected && (
              <span style={{
                marginLeft: 10, display: 'inline-flex', alignItems: 'center', gap: 5,
                fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--accent-green)',
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
                fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-sans)',
                animation: 'flash 0.5s ease-out',
              }}>
                +{newAlertCount} new
              </span>
            )}
          </p>
        </div>
        <div className="page-actions">
          <div className="view-toggle" role="group" aria-label="Queue view">
            {['board', 'table'].map(v => (
              <button key={v} type="button" aria-pressed={view === v}
                      className={`filter-tab ${view === v ? 'active' : ''}`}
                      onClick={() => setView(v)}>
                {v === 'board' ? 'Board' : 'Table'}
              </button>
            ))}
          </div>
          <button
            className="btn btn-ghost btn-sm"
            disabled={seeding}
            onClick={handleSeed}
            title="Send synthetic transactions to Kafka"
          >
            {seeding ? 'Seeding...' : 'Seed transactions'}
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
      <div className="stat-grid">
        <StatCard label="Open alerts"       value={stats.open} />
        <StatCard label="Critical severity" value={stats.critical} />
        <StatCard label="High SAR risk"     value={stats.highSAR} />
        <StatCard label="Suspicious flow"   value={formatAmount(stats.totalAmt)} />
      </div>

      {/* ── Filters ── */}
      <div className="filter-bar">
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
              {statusLabel(s)}
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
            {statusLabel(s)}
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
      ) : view === 'board' ? (
        <BoardView alerts={alerts} onMove={handleMove}
                   onOpen={id => navigate(alertPath(id))} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {/* Table header */}
          <div className="queue-row queue-head">
            <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', }}>Score</span>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', }}>Alert</span>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', }}>Breakdown</span>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', textAlign: 'right' }}>Amount</span>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', textAlign: 'center' }}>SAR</span>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', textAlign: 'right' }}>Time</span>
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
                    className="glass-card queue-row"
                    style={{
                      padding: '14px 18px',
                      cursor: 'pointer',
                      borderColor: expanded ? sevCfg.color : undefined,
                      borderRadius: expanded ? 'var(--radius-lg) var(--radius-lg) 0 0' : 'var(--radius-lg)',
                      transition: 'border-color 0.2s, box-shadow 0.2s',
                    }}
                  >
                    {/* Priority ring */}
                    <div className="q-ring"><PriorityRing score={alert.priority_score} rank={idx + 1} /></div>

                    {/* Main info */}
                    <div className="q-main" style={{ minWidth: 0 }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-sans)', color: 'var(--text-primary)', }}>
                          {alert.alert_id}
                        </span>
                        <span className={`badge ${sevCfg.cls}`}>{statusLabel(alert.severity)}</span>
                        <span className={`badge ${(STATUS_CONFIG[alert.status] || {}).cls || ''}`}>
                          {statusLabel(alert.status)}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 12, fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)' }}>
                        <span>{alert.account_count} accounts</span>
                        <span>{alert.txn_count} transfers</span>
                        {alert.investigation_complexity && (
                          <span>{statusLabel(alert.investigation_complexity)} effort</span>
                        )}
                      </div>
                    </div>

                    {/* Score breakdown mini-bars */}
                    <div className="q-break">
                      {Object.entries(alert.score_breakdown || {}).slice(0, 3).map(([key, val]) => (
                        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', width: 58, flexShrink: 0 }}>
                            {BREAKDOWN_LABELS[key] || key}
                          </span>
                          <ScoreBar value={val} color={val >= SCORE_BAR_CRITICAL ? 'var(--critical)' : val >= SCORE_BAR_HIGH ? 'var(--high)' : 'var(--accent-green)'} />
                        </div>
                      ))}
                    </div>

                    {/* Amount */}
                    <span className="amount q-amt" style={{ textAlign: 'right', fontSize: 13 }}>
                      {formatAmount(alert.total_amount)}
                    </span>

                    {/* SAR probability */}
                    <div className="q-sar">
                      <span style={{
                        fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-sans)',
                        color: sarPct >= SCORE_BAR_CRITICAL * 100 ? 'var(--critical)' : sarPct >= SCORE_BAR_HIGH * 100 ? 'var(--high)' : 'var(--text-muted)',
                      }}>
                        {sarPct}%
                      </span>
                    </div>

                    {/* Time ago */}
                    <span className="q-time" style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-faint)', textAlign: 'right' }}>
                      {timeAgo(alert.created_at)}
                    </span>

                    {/* Chevron */}
                    <motion.span
                      className="q-chev"
                      animate={{ rotate: expanded ? 180 : 0 }}
                      transition={{ duration: 0.15 }}
                      style={{ fontSize: 12, color: 'var(--text-faint)', textAlign: 'center' }}
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

      {moveError && <p role="alert" className="approval-error">{moveError}</p>}
      {approvalAlert && (
        <ApprovalDialog alert={approvalAlert} onConfirm={confirmFiling}
                        onCancel={() => setApprovalAlert(null)} />
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
