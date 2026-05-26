import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { RefreshCw, ArrowUp, ArrowDown, AlertTriangle, Activity, Shield, DollarSign, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';

/* ── Metric Stat Card ── */
function StatCard({ label, value, color, icon: Icon, sub, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35, ease: 'easeOut' }}
      style={{
        background: 'rgba(15,20,33,0.70)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 10,
        padding: '16px 18px',
        position: 'relative',
        overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        cursor: 'default',
      }}
      whileHover={{
        borderColor: `${color}30`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${color}18`,
        y: -1,
        transition: { duration: 0.2 },
      }}
    >
      {/* Glow behind value */}
      <div style={{
        position: 'absolute', top: -20, right: -20,
        width: 80, height: 80,
        background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />
      {/* Top accent */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 1,
        background: `linear-gradient(90deg, ${color}60, transparent)`,
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--text-muted)',
          letterSpacing: '1.2px',
          textTransform: 'uppercase',
          fontWeight: 700,
        }}>{label}</div>
        {Icon && (
          <div style={{ color, opacity: 0.5 }}>
            <Icon size={13} />
          </div>
        )}
      </div>

      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 28,
        fontWeight: 800,
        color,
        letterSpacing: '-1px',
        lineHeight: 1,
        marginBottom: sub ? 6 : 0,
      }}>{value}</div>

      {sub && (
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
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
        padding: '80px 40px',
        gap: 16,
        textAlign: 'center',
      }}
    >
      <div style={{
        width: 48, height: 48,
        borderRadius: '50%',
        background: 'rgba(16,185,129,0.08)',
        border: '1px solid rgba(16,185,129,0.15)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Shield size={20} color="#10B981" />
      </div>
      <div>
        <p style={{
          fontFamily: 'var(--font-display)',
          fontSize: 15,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          marginBottom: 4,
        }}>
          {hasFilters ? 'No alerts match filters' : 'Queue is clear'}
        </p>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
        }}>
          {hasFilters
            ? '// adjust severity or status filters'
            : '// network topology analysis running · 0 anomalies detected'
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
    apiFetch('/api/v1/alerts?limit=100')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAlerts(data.alerts || []);
        setLoading(false);
      })
      .catch(() => {
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
        if (a) navigate(`/alert/${a.alert_id}`);
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
    total:    (alerts.reduce((s, a) => s + a.total_amount, 0) / 100000).toFixed(1),
  };

  const hasFilters = filter.severity !== 'ALL' || filter.status !== 'ALL';

  const getRiskColor = (score) => {
    if (score >= 0.8) return 'var(--critical)';
    if (score >= 0.6) return 'var(--high)';
    if (score >= 0.4) return 'var(--medium)';
    return 'var(--text-muted)';
  };

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1440, margin: '0 auto' }}>

      {/* ── Page Header ── */}
      <motion.div
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: 26,
              fontWeight: 800,
              letterSpacing: '-0.5px',
              color: 'var(--text-primary)',
              margin: 0,
            }}>
              Alert Queue
            </h1>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 5,
              padding: '2px 8px',
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: '#10B981',
                animation: 'emeraldPulse 2s ease-in-out infinite',
              }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: '#10B981',
                letterSpacing: '1px',
                textTransform: 'uppercase',
                fontWeight: 700,
              }}>Live</span>
            </div>
          </div>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--text-muted)',
            letterSpacing: '0.3px',
          }}>
            <span style={{ color: 'rgba(16,185,129,0.6)' }}>//</span>
            {' '}{filtered.length} alerts
            {stats.critical > 0 && <><span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span><span style={{ color: 'var(--critical)' }}>{stats.critical} critical</span></>}
            {stats.high > 0     && <><span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span><span style={{ color: 'var(--high)' }}>{stats.high} high</span></>}
            {stats.open > 0     && <><span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span><span>{stats.open} open</span></>}
            {parseFloat(stats.total) > 0 && <><span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span><span style={{ color: 'var(--high)' }}>₹{stats.total}L flagged</span></>}
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        <StatCard label="Critical"      value={stats.critical} color="var(--critical)" icon={AlertTriangle} sub="active alerts"   index={0} />
        <StatCard label="High Severity" value={stats.high}     color="var(--high)"     icon={Activity}      sub="active alerts"   index={1} />
        <StatCard label="Open Cases"    value={stats.open}     color="var(--medium)"   icon={Shield}        sub="under review"    index={2} />
        <StatCard label="Total Flagged" value={`₹${stats.total}L`} color="var(--high)" icon={DollarSign}   sub="this cycle"      index={3} />
      </div>

      {/* ── Filter Bar ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        marginBottom: 16,
        borderBottom: '1px solid var(--border)',
        background: 'rgba(15,20,33,0.4)',
        borderRadius: '8px 8px 0 0',
        padding: '0 4px',
        backdropFilter: 'blur(10px)',
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
          >{s}</button>
        ))}
        <div className="filter-divider" />
        <span className="filter-label">Status</span>
        {['ALL', 'OPEN', 'UNDER_REVIEW', 'RESOLVED'].map(s => (
          <button
            key={`sta-${s}`}
            className={`filter-tab ${filter.status === s ? 'active' : ''}`}
            onClick={() => setFilter(f => ({ ...f, status: s }))}
          >{s.replace('_', ' ')}</button>
        ))}
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
          <div style={{
            background: 'rgba(15,20,33,0.60)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid var(--border)',
            borderTop: 'none',
            borderRadius: '0 0 10px 10px',
            overflow: 'hidden',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}>
            {filtered.length === 0 ? (
              <EmptyState hasFilters={hasFilters} />
            ) : (
              <div className="table-container">
                <table className="data-table" role="grid" aria-label="Fraud alerts">
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
                          onClick={() => navigate(`/alert/${alert.alert_id}`)}
                          tabIndex={0}
                          role="row"
                          onKeyDown={e => { if (e.key === 'Enter') navigate(`/alert/${alert.alert_id}`); }}
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
                              <div style={{ width: 36, height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
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
                              ₹{alert.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
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
                  background: 'rgba(255,255,255,0.05)',
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
