import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { RefreshCw, ArrowUp, ArrowDown, AlertTriangle, Activity, Shield, DollarSign, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { alertPath } from '../utils/safeNavigation';
import { API_ALERTS_LIMIT, RISK_CRITICAL_THRESHOLD, RISK_HIGH_THRESHOLD } from '../config';
import { formatAmount } from '../utils/formatAmount';

/* ── Metric Stat Card ── */
function StatCard({ label, value, color, icon: Icon, sub, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3, ease: 'easeOut' }}
      className="premium-card"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
        <div className="meta-label">{label}</div>
        {Icon && (
          <div style={{ color: 'var(--text-faint)', opacity: 0.7 }}>
            <Icon size={14} />
          </div>
        )}
      </div>

      <div className="data-value" style={{ color, marginBottom: sub ? 'var(--space-1)' : 0 }}>{value}</div>

      {sub && (
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-faint)',
          letterSpacing: '0.2px',
        }}>{sub}</div>
      )}
    </motion.div>
  );
}

/* ── Empty State ── */
function EmptyState({ hasFilters }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-8) var(--space-4)',
        gap: 'var(--space-3)',
        textAlign: 'center',
      }}
    >
      <div style={{
        width: 56, height: 56,
        borderRadius: '50%',
        background: 'var(--accent-dim)',
        border: '1px solid var(--border-glow)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        <Shield size={24} color="var(--accent-primary)" />
        <div style={{
          position: 'absolute',
          inset: -4,
          borderRadius: '50%',
          border: '1px solid var(--accent-glow)',
          animation: 'glowPulse 2s ease-in-out infinite',
        }} />
      </div>
      <div>
        <p style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-base)',
          fontWeight: 600,
          color: 'var(--text-primary)',
          marginBottom: 'var(--space-0-5)',
        }}>
          {hasFilters ? 'No Alerts Match Current Criteria' : 'System Operational: Queue Clear'}
        </p>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
        }}>
          {hasFilters
            ? '// Adjust severity or status filters to broaden search range'
            : '// Real-time AI engine running, 0 anomalies pending investigation'
          }
        </p>
      </div>
    </motion.div>
  );
}

/* ── Main Dashboard ── */
export default function Dashboard() {
  const [alerts, setAlerts]           = useState([]);
  const [loading, setLoading]         = useState(true);
  const [filter, setFilter]           = useState({ severity: 'ALL', status: 'ALL' });
  const [sortKey, setSortKey]         = useState('risk_score');
  const [sortDir, setSortDir]         = useState('desc');
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const navigate = useNavigate();

  const fetchAlerts = () => {
    setLoading(true);
    apiFetch(`/api/v1/alerts?limit=${API_ALERTS_LIMIT}`)
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAlerts(data.alerts || []);
        setLoading(false);
      })
      .catch(err => {
        console.error('[Dashboard] Failed to load alerts:', err);
        setLoading(false);
        toast.error('Failed to load alerts');
      });
  };

  useEffect(() => { fetchAlerts(); }, []);

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'j') setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
      if (e.key === 'k') setSelectedIndex(i => Math.max(i - 1, 0));
      if (e.key === 'Enter' && selectedIndex >= 0) {
        const a = filtered[selectedIndex];
        if (a) navigate(alertPath(a.alert_id));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  const filtered = useMemo(() => {
    let result = alerts.filter(a => {
      if (filter.severity !== 'ALL' && a.severity !== filter.severity) return false;
      if (filter.status !== 'ALL' && a.status !== filter.status) return false;
      return true;
    });
    result.sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'string') av = av.toLowerCase();
      if (typeof bv === 'string') bv = bv.toLowerCase();
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return result;
  }, [alerts, filter, sortKey, sortDir]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const SortIcon = ({ k }) => sortKey !== k ? null : sortDir === 'asc'
    ? <ArrowUp size={9} style={{ marginLeft: 3, verticalAlign: 'middle', opacity: 0.7 }} />
    : <ArrowDown size={9} style={{ marginLeft: 3, verticalAlign: 'middle', opacity: 0.7 }} />;

  const stats = {
    critical: alerts.filter(a => a.severity === 'CRITICAL').length,
    high:     alerts.filter(a => a.severity === 'HIGH').length,
    open:     alerts.filter(a => a.status === 'OPEN').length,
    total:    alerts.reduce((s, a) => s + a.total_amount, 0),
  };

  const hasFilters = filter.severity !== 'ALL' || filter.status !== 'ALL';

  const getRiskColor = (score) => {
    if (score >= RISK_CRITICAL_THRESHOLD) return 'var(--critical)';
    if (score >= RISK_HIGH_THRESHOLD) return 'var(--high)';
    if (score >= 0.4) return 'var(--medium)';
    return 'var(--text-muted)';
  };

  return (
    <div className="dash-page">

      {/* ── Page Header ── */}
      <motion.div
        className="dash-head"
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 24,
        }}
      >
        <div>
          <h1 className="gradient-text" style={{
            fontFamily: 'var(--font-display)',
            fontSize: 24,
            fontWeight: 700,
            letterSpacing: '-0.3px',
            margin: '0 0 4px',
          }}>
            Alert Queue
          </h1>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--text-muted)',
            letterSpacing: '0.2px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent-green)', display: 'inline-block', flexShrink: 0 }} />
            {loading ? 'Loading alerts…' : `${filtered.length} alerts`}
            {stats.critical > 0 && <><span style={{ color: 'var(--text-faint)' }}>|</span><span style={{ color: 'var(--critical)' }}>{stats.critical} critical</span></>}
            {stats.high > 0     && <><span style={{ color: 'var(--text-faint)' }}>|</span><span style={{ color: 'var(--high)' }}>{stats.high} high</span></>}
            {stats.open > 0     && <><span style={{ color: 'var(--text-faint)' }}>|</span><span>{stats.open} open</span></>}
            {stats.total > 0 && <><span style={{ color: 'var(--text-faint)' }}>|</span><span style={{ color: 'var(--high)' }}>{formatAmount(stats.total)}</span></>}
          </p>
        </div>

        <button
          className="btn btn-ghost"
          onClick={fetchAlerts}
          style={{ gap: 7, marginTop: 4 }}
        >
          <RefreshCw size={13} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.5px' }}>Refresh</span>
        </button>
      </motion.div>

      {/* ── Metric Cards ── */}
      <div className="dash-stats">
        <StatCard label="Critical"      value={loading ? '–' : stats.critical} color="var(--critical)" icon={AlertTriangle} sub="active alerts"   index={0} />
        <StatCard label="High Severity" value={loading ? '–' : stats.high}     color="var(--high)"     icon={Activity}      sub="active alerts"   index={1} />
        <StatCard label="Open Cases"    value={loading ? '–' : stats.open}     color="var(--medium)"   icon={Shield}        sub="under review"    index={2} />
        <StatCard label="Total Flagged" value={loading ? '–' : formatAmount(stats.total)} color="var(--high)" icon={DollarSign}   sub="this cycle"      index={3} />
      </div>

      {/* ── Filter Bar ── */}
      <div className="dash-filters" style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-4)',
        overflow: 'auto',
      }}>
        <div className="segmented-control" role="group" aria-label="Severity">
          <span className="meta-label" style={{ padding: '0 var(--space-2)' }}>Severity</span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'].map(s => (
            <button
              key={`sev-${s}`}
              className={`segmented-btn ${filter.severity === s ? 'active' : ''}`}
              aria-pressed={filter.severity === s}
              onClick={() => setFilter(f => ({ ...f, severity: s }))}
            >{s}</button>
          ))}
        </div>
        <div className="segmented-control" role="group" aria-label="Status">
          <span className="meta-label" style={{ padding: '0 var(--space-2)' }}>Status</span>
          {['ALL', 'OPEN', 'UNDER_REVIEW', 'RESOLVED'].map(s => (
            <button
              key={`sta-${s}`}
              className={`segmented-btn ${filter.status === s ? 'active' : ''}`}
              aria-pressed={filter.status === s}
              onClick={() => setFilter(f => ({ ...f, status: s }))}
            >{s.replace('_', ' ')}</button>
          ))}
        </div>
      </div>

      {/* ── Table ── */}
      {loading ? (
        <div className="loading">
          <div className="spinner" />
          Loading intelligence data...
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          <div className="premium-card" style={{ padding: 0 }}>
            {filtered.length === 0 ? (
              <EmptyState hasFilters={hasFilters} />
            ) : (
              <div className="table-container">
                <table className="data-table enterprise-table" role="grid" aria-label="Fraud alerts">
                  <thead>
                    <tr>
                      <th style={{ width: 40, paddingLeft: 16 }}>#</th>
                      <th onClick={() => toggleSort('alert_id')}>Alert ID <SortIcon k="alert_id" /></th>
                      <th onClick={() => toggleSort('severity')}>Severity <SortIcon k="severity" /></th>
                      <th onClick={() => toggleSort('risk_score')}>Risk <SortIcon k="risk_score" /></th>
                      <th onClick={() => toggleSort('account_count')}>Accounts <SortIcon k="account_count" /></th>
                      <th onClick={() => toggleSort('total_amount')}>Amount <SortIcon k="total_amount" /></th>
                      <th>Transactions</th>
                      <th>Top Signal</th>
                      <th onClick={() => toggleSort('status')}>Status <SortIcon k="status" /></th>
                      <th onClick={() => toggleSort('created_at')}>Created <SortIcon k="created_at" /></th>
                      <th style={{ width: 32 }} />
                    </tr>
                  </thead>
                  <tbody>
                    <AnimatePresence>
                      {filtered.map((alert, idx) => (
                        <motion.tr
                          key={alert.alert_id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: Math.min(idx * 0.02, 0.3) }}
                          className={`clickable ${idx === selectedIndex ? 'selected' : ''}`}
                          onClick={() => navigate(alertPath(alert.alert_id))}
                          tabIndex={0}
                          role="row"
                          onKeyDown={e => { if (e.key === 'Enter') navigate(alertPath(alert.alert_id)); }}
                        >
                          <td style={{ color: 'var(--text-faint)', fontSize: 11, fontFamily: 'var(--font-mono)', paddingLeft: 16 }}>
                            {idx + 1}
                          </td>
                          <td>
                            <span style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: 12,
                              color: 'var(--accent-cyan)',
                              letterSpacing: '0.3px',
                            }}>{alert.alert_id}</span>
                          </td>
                          <td>
                            <span className={`badge badge-${alert.severity}`}>{alert.severity}</span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ width: 36, height: 3, background: 'var(--border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                                <div style={{
                                  height: '100%',
                                  width: `${alert.risk_score * 100}%`,
                                  background: getRiskColor(alert.risk_score),
                                  borderRadius: 2,
                                }} />
                              </div>
                              <span style={{
                                fontFamily: 'var(--font-mono)',
                                fontSize: 12,
                                color: getRiskColor(alert.risk_score),
                                fontWeight: 600,
                              }}>
                                {(alert.risk_score * 100).toFixed(0)}%
                              </span>
                            </div>
                          </td>
                          <td>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {alert.account_count}
                            </span>
                          </td>
                          <td>
                            <span style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: 13,
                              color: 'var(--high)',
                              fontWeight: 600,
                            }}>
                              {formatAmount(alert.total_amount)}
                            </span>
                          </td>
                          <td>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {alert.txn_count}
                            </span>
                          </td>
                          <td style={{ maxWidth: 180 }}>
                            <span style={{
                              fontSize: 11,
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--text-secondary)',
                              letterSpacing: '0.2px',
                            }}>
                              {alert.reason_codes?.[0]?.split(':')[0] || '—'}
                            </span>
                          </td>
                          <td>
                            <span className={`badge badge-${alert.status}`}>
                              {alert.status.replace('_', ' ')}
                            </span>
                          </td>
                          <td style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                            {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                          </td>
                          <td style={{ paddingRight: 16 }}>
                            <ChevronRight size={13} color="var(--text-faint)" />
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Keyboard hint */}
          <div style={{
            marginTop: 10,
            display: 'flex',
            gap: 16,
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--text-faint)',
            letterSpacing: '0.5px',
          }}>
            {[['j/k', 'navigate'], ['Enter', 'open alert'], ['click header', 'sort']].map(([k, v]) => (
              <span key={k}>
                <span style={{
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border)',
                  borderRadius: 3,
                  padding: '1px 5px',
                  marginRight: 5,
                  fontWeight: 700,
                }}>{k}</span>
                {v}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
