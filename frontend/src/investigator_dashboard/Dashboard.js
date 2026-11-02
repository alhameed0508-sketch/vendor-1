import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { alertPath } from '../utils/safeNavigation';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { RefreshCw, ArrowUp, ArrowDown, AlertTriangle, Activity, Shield, DollarSign, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { API_ALERTS_LIMIT, RISK_CRITICAL_THRESHOLD, RISK_HIGH_THRESHOLD } from '../config';
import { formatAmount } from '../utils/formatAmount';
import StatCard from '../components/StatCard';
import { statusLabel as label } from '../utils/statusLabel';

/* ── Empty State ── */
function EmptyState({ hasFilters }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 40px',
        gap: 16,
        textAlign: 'center',
      }}
    >
      <div style={{
        width: 48, height: 48,
        borderRadius: '50%',
        background: 'var(--accent-dim)',
        border: '1px solid color-mix(in srgb, var(--accent) 15%, transparent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Shield size={20} color="var(--accent)" />
      </div>
      <div>
        <p style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 15,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          marginBottom: 4,
        }}>
          {hasFilters ? 'No alerts match filters' : 'Queue is clear'}
        </p>
        <p className="text-mono-sm">
          {hasFilters
            ? 'Adjust severity or status filters'
            : 'Network topology analysis running'
          }
        </p>
      </div>
    </div>
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
    total:    alerts.reduce((s, a) => s + (a.total_amount || 0), 0),
  };

  const hasFilters = filter.severity !== 'ALL' || filter.status !== 'ALL';

  const getRiskColor = (score) => {
    if (score >= RISK_CRITICAL_THRESHOLD) return 'var(--critical)';
    if (score >= RISK_HIGH_THRESHOLD) return 'var(--high)';
    if (score >= 0.4) return 'var(--medium)';
    return 'var(--text-muted)';
  };

  return (
    <div className="page">

      {/* ── Page Header ── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 24,
        }}
      >
        <div>
          <h1 className="text-page-title" style={{ margin: '0 0 4px' }}>
            Alerts
          </h1>
          <p className="text-mono-sm" style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '4px 12px',
            fontSize: 13,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', flexShrink: 0 }} />
            {filtered.length} alerts
            {stats.critical > 0 && <span style={{ color: 'var(--critical)' }}>{stats.critical} critical</span>}
            {stats.high > 0     && <span style={{ color: 'var(--high)' }}>{stats.high} high</span>}
            {stats.open > 0     && <span>{stats.open} open</span>}
            {stats.total > 0 && <span>{formatAmount(stats.total)} flagged</span>}
          </p>
        </div>

        <button
          className="btn btn-ghost"
          onClick={fetchAlerts}
          style={{ gap: 7, marginTop: 4 }}
        >
          <RefreshCw size={13} />
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, }}>Refresh</span>
        </button>
      </div>

      {/* ── Metric Cards ── */}
      <div className="stat-grid">
        <StatCard label="Critical"      value={stats.critical} icon={AlertTriangle} sub="active alerts" />
        <StatCard label="High severity" value={stats.high}     icon={Activity}      sub="active alerts" />
        <StatCard label="Open cases"    value={stats.open}   icon={Shield}        sub="under review" />
        <StatCard label="Total flagged" value={formatAmount(stats.total)} icon={DollarSign}   sub="this cycle" />
      </div>

      {/* ── Filter Bar ── */}
      <div className="filter-bar filter-bar-attached" style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        marginBottom: 0,
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-card)',
        borderRadius: '10px 10px 0 0',
        padding: '2px 4px',
        overflow: 'auto',
      }}>
        <span className="filter-label">Severity</span>
        {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'].map(s => (
          <button
            key={`sev-${s}`}
            className={`filter-tab ${filter.severity === s
              ? s === 'CRITICAL' ? 'active-critical'
              : s === 'HIGH'     ? 'active-high'
              : s === 'MEDIUM'   ? 'active-medium'
              : 'active'
              : ''
            }`}
            onClick={() => setFilter(f => ({ ...f, severity: s }))}
          >{label(s)}</button>
        ))}
        <div className="filter-divider" />
        <span className="filter-label">Status</span>
        {['ALL', 'OPEN', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE', 'STR_FILED'].map(s => (
          <button
            key={`sta-${s}`}
            className={`filter-tab ${filter.status === s ? 'active' : ''}`}
            onClick={() => setFilter(f => ({ ...f, status: s }))}
          >{label(s)}</button>
        ))}
      </div>

      {/* ── Table ── */}
      {loading ? (
        <div className="loading">
          <div className="spinner" />
          Loading intelligence data...
        </div>
      ) : (
        <div>
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderTop: 'none',
            borderRadius: '0 0 10px 10px',
            overflow: 'hidden',
          }}>
            {filtered.length === 0 ? (
              <EmptyState hasFilters={hasFilters} />
            ) : (
              <div className="table-container">
                <table className="data-table data-table-stack" role="grid" aria-label="Fraud alerts">
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
                    {filtered.map((alert, idx) => (
                      <tr
                        key={alert.alert_id}
                        className={`clickable ${idx === selectedIndex ? 'selected' : ''}`}
                        onClick={() => navigate(alertPath(alert.alert_id))}
                        tabIndex={0}
                        role="row"
                        onKeyDown={e => { if (e.key === 'Enter') navigate(alertPath(alert.alert_id)); }}
                      >
                        <td className="col-idx" style={{ color: 'var(--text-faint)', fontSize: 12, fontFamily: 'var(--font-sans)', paddingLeft: 16 }}>
                          {idx + 1}
                        </td>
                        <td className="col-id">
                          <span style={{
                            fontFamily: 'var(--font-sans)',
                            fontSize: 13,
                            fontWeight: 500,
                            color: 'var(--text-primary)',
                          }}>{alert.alert_id}</span>
                        </td>
                        <td className="col-sev">
                          <span className={`badge badge-${alert.severity}`}>{alert.severity}</span>
                        </td>
                        <td className="col-risk">
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
                              fontFamily: 'var(--font-sans)',
                              fontSize: 12,
                              color: getRiskColor(alert.risk_score),
                              fontWeight: 600,
                            }}>
                              {(alert.risk_score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </td>
                        <td className="col-acc">
                          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13 }}>
                            {alert.account_count}
                          </span>
                        </td>
                        <td className="col-amt">
                          <span style={{
                            fontFamily: 'var(--font-sans)',
                            fontSize: 13,
                            color: 'var(--text-primary)',
                            fontWeight: 600,
                          }}>
                            ₹{alert.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </span>
                        </td>
                        <td className="col-txn">
                          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13 }}>
                            {alert.txn_count}
                          </span>
                        </td>
                        <td className="col-sig" style={{ maxWidth: 180 }}>
                          <span style={{
                            fontSize: 12,
                            fontFamily: 'var(--font-sans)',
                            color: 'var(--text-secondary)',
                            letterSpacing: '0.2px',
                          }}>
                            {alert.reason_codes?.[0]?.split(':')[0] || '—'}
                          </span>
                        </td>
                        <td className="col-status">
                          <span className={`badge badge-${alert.status}`}>
                            {alert.status.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="col-created" style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }}>
                          {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                        </td>
                        <td className="col-go" style={{ paddingRight: 16 }}>
                          <ChevronRight size={13} color="var(--text-faint)" />
                        </td>
                      </tr>
                    ))}
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
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--text-faint)',
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
        </div>
      )}
    </div>
  );
}
