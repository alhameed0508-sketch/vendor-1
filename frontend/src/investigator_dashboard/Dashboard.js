import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import AnimatedCounter from '../components/AnimatedCounter';
import { GlassCard } from '../components/ui/GlassCard';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';
import { AnimateIn } from '../components/motion/AnimateIn';
import { SkeletonTable, SkeletonCard } from '../components/Skeleton';
import { useKeyboardShortcuts } from '../components/KeyboardShortcuts';
import { apiFetch } from '../auth/api';

/* ── Severity accent colors for card top bars ── */
const SEVERITY_ACCENT = {
  Critical: 'var(--critical)',
  High: 'var(--high)',
  Open: 'var(--accent-gold)',
  'Total Amount': 'var(--accent-amber)',
};

function LiveFeed() {
  const [txns, setTxns] = useState([]);

  useEffect(() => {
    const fetchTxns = () => {
      apiFetch('/api/v1/ingest/stream-demo?count=5')
        .then(r => r.json())
        .then(body => {
          const data = body?.data || body;
          if (data.transactions) {
            setTxns(prev => [...data.transactions, ...prev].slice(0, 12));
          }
        })
        .catch(() => {});
    };
    fetchTxns();
    const interval = setInterval(fetchTxns, 4000);
    return () => clearInterval(interval);
  }, []);

  if (!txns.length) return null;

  return (
    <AnimateIn delay={0.3}>
      <GlassCard className="mt-4 p-4" hover={false} style={{ borderTop: '2px solid var(--accent-green)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', animation: 'pulse 2s infinite' }} />
            <span style={{ fontSize: 12, fontWeight: 700 }}>Live Transaction Feed</span>
          </div>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Kafka Stream Simulation</span>
        </div>
        <div style={{ maxHeight: 140, overflowY: 'auto' }}>
          {txns.map((t, i) => (
            <motion.div
              key={`${t.txn_id}-${i}`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '3px 0', borderBottom: '1px solid var(--border)', fontSize: 11,
                fontFamily: 'var(--font-mono)',
              }}
            >
              <span style={{ color: 'var(--text-muted)', width: 90 }}>{t.txn_id?.slice(0, 10)}</span>
              <span style={{ color: 'var(--text-secondary)' }}>{t.from_account?.slice(0, 10)} → {t.to_account?.slice(0, 10)}</span>
              <span style={{ color: t.is_suspicious ? 'var(--critical)' : 'var(--accent-green)', fontWeight: 600 }}>
                ₹{Number(t.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
              <span style={{ color: t.is_suspicious ? 'var(--critical)' : 'var(--text-muted)', fontSize: 10 }}>
                {t.is_suspicious ? '⚠' : '✓'}
              </span>
            </motion.div>
          ))}
        </div>
      </GlassCard>
    </AnimateIn>
  );
}


export default function Dashboard() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ severity: 'ALL', status: 'ALL' });
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const navigate = useNavigate();

  useEffect(() => {
    apiFetch('/api/v1/alerts?limit=100')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAlerts(data.alerts || []);
        setLoading(false);
        if (data.alerts?.length) toast.success(`${data.alerts.length} alerts loaded`);
      })
      .catch(() => {
        setLoading(false);
        toast.error('Failed to load alerts');
      });
  }, []);

  const filtered = alerts.filter(a => {
    if (filter.severity !== 'ALL' && a.severity !== filter.severity) return false;
    if (filter.status !== 'ALL' && a.status !== filter.status) return false;
    return true;
  });

  const riskClass = s => s === 'CRITICAL' ? 'critical' : s === 'HIGH' ? 'high' : 'medium';

  useKeyboardShortcuts({
    onNavigate: (idx) => {
      const alert = filtered[idx];
      if (alert) navigate(`/alert/${alert.alert_id}`);
    },
    selectedIndex,
    setSelectedIndex,
    alertCount: filtered.length,
    enabled: !loading,
  });

  const summaryCards = [
    { label: 'Critical',     count: alerts.filter(a => a.severity === 'CRITICAL').length, color: 'var(--critical)',      glow: 'rgba(255,59,92,0.12)' },
    { label: 'High',         count: alerts.filter(a => a.severity === 'HIGH').length,     color: 'var(--high)',           glow: 'rgba(245,158,11,0.12)' },
    { label: 'Open',         count: alerts.filter(a => a.status === 'OPEN').length,       color: 'var(--accent-gold)',  glow: 'rgba(245,158,11,0.12)' },
    { label: 'Total Amount', count: alerts.reduce((s, a) => s + a.total_amount, 0), amount: true, color: 'var(--accent-amber)', glow: 'rgba(245,158,11,0.10)' },
  ];

  /* ── Underline filter tab classes ── */
  const tabClass = (isActive, severity) => {
    if (!isActive) return 'filter-tab';
    const map = { CRITICAL: 'filter-tab active-critical', HIGH: 'filter-tab active-high', MEDIUM: 'filter-tab active-medium' };
    return map[severity] || 'filter-tab active';
  };

  return (
    <div style={{ padding: '32px 32px 48px', maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Page Header ── */}
      <AnimateIn>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32 }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--accent-gold)', letterSpacing: '3px', textTransform: 'uppercase', marginBottom: 8, opacity: 0.8 }}>
              IOB · Fraud Intelligence Platform
            </div>
            <h1 style={{ fontFamily: 'var(--font-sans)', fontSize: 30, fontWeight: 700, letterSpacing: '-1px', color: 'var(--text-primary)', lineHeight: 1, margin: 0 }}>
              Alert Queue
            </h1>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 6, letterSpacing: '0.3px' }}>
              {filtered.length} active alerts · graph topology analysis
            </p>
          </div>
          <motion.button className="btn btn-ghost" onClick={() => window.location.reload()} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} style={{ marginTop: 4, fontSize: 12 }}>
            ↻ Refresh
          </motion.button>
        </div>
      </AnimateIn>

      {/* ── Filter Tabs ── */}
      <AnimateIn delay={0.05}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginBottom: 28, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', paddingRight: 10, borderRight: '1px solid var(--border)', marginRight: 6 }}>Severity</span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'].map(s => (
            <button key={`sev-${s}`} className={tabClass(filter.severity === s, s)} onClick={() => setFilter(f => ({ ...f, severity: s }))}>{s}</button>
          ))}
          <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 10px' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', paddingRight: 10, borderRight: '1px solid var(--border)', marginRight: 6 }}>Status</span>
          {['ALL', 'OPEN', 'UNDER_REVIEW', 'RESOLVED'].map(s => (
            <button key={`sta-${s}`} className={`filter-tab ${filter.status === s ? 'active' : ''}`} onClick={() => setFilter(f => ({ ...f, status: s }))}>{s.replace('_', ' ')}</button>
          ))}
        </div>
      </AnimateIn>

      {loading ? (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
            {[0,1,2,3].map(i => <SkeletonCard key={i} />)}
          </div>
          <SkeletonTable rows={6} columns={9} />
        </div>
      ) : (
        <>
          {/* ── 4-Column Bento Metric Cards ── */}
          <StaggerContainer style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
            {summaryCards.map((c, i) => (
              <StaggerItem key={c.label}>
                <GlassCard glow glowColor={c.glow} accent={SEVERITY_ACCENT[c.label]}
                  style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}
                >
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '2px', textTransform: 'uppercase' }}>
                    {c.label}
                  </div>
                  {c.amount ? (
                    <AnimatedCounter end={parseFloat((c.count / 100000).toFixed(1))} prefix="₹" suffix="L" decimals={1}
                      style={{ fontSize: 34, fontWeight: 700, color: c.color, fontFamily: 'var(--font-sans)', letterSpacing: '-1px', lineHeight: 1 }} />
                  ) : (
                    <AnimatedCounter end={c.count}
                      style={{ fontSize: 34, fontWeight: 700, color: c.color, fontFamily: 'var(--font-sans)', letterSpacing: '-1px', lineHeight: 1 }} />
                  )}
                  <div style={{ width: '100%', height: 2, borderRadius: 1, background: 'var(--border)', overflow: 'hidden' }}>
                    <motion.div initial={{ width: 0 }} animate={{ width: c.count > 0 ? '65%' : '8%' }}
                      transition={{ duration: 1.2, delay: i * 0.12, ease: 'easeOut' }}
                      style={{ height: '100%', background: c.color, borderRadius: 1, opacity: 0.7 }} />
                  </div>
                </GlassCard>
              </StaggerItem>
            ))}
          </StaggerContainer>

          {/* ── Alert Table ── */}
          <AnimateIn delay={0.2}>
            <GlassCard style={{ padding: 0, overflow: 'hidden' }} hover={false}>
              <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '2px', textTransform: 'uppercase' }}>
                  Live Alert Feed · {filtered.length} results
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-green)', boxShadow: '0 0 8px var(--accent-green)', animation: 'pulse 2s infinite' }} />
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--accent-green)', letterSpacing: '1px' }}>LIVE</span>
                </div>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th><th>Alert ID</th><th>Severity</th><th>Risk Score</th>
                    <th>Accounts</th><th>Total Amount</th><th>Transactions</th>
                    <th>Top Signal</th><th>Status</th><th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((alert, idx) => (
                    <motion.tr key={alert.alert_id}
                      className={`clickable ${idx === selectedIndex ? 'selected' : ''}`}
                      onClick={() => navigate(`/alert/${alert.alert_id}`)}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.025, type: 'spring', stiffness: 300, damping: 30 }}
                    >
                      <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{String(idx + 1).padStart(2, '0')}</td>
                      <td><span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-gold)', fontSize: 12 }}>{alert.alert_id}</span></td>
                      <td><span className={`badge badge-${alert.severity}`}>{alert.severity}</span></td>
                      <td>
                        <div className="risk-bar">
                          <div className="risk-track">
                            <motion.div className={`risk-fill ${riskClass(alert.severity)}`}
                              initial={{ width: 0 }} animate={{ width: `${alert.risk_score * 100}%` }}
                              transition={{ duration: 0.8, delay: idx * 0.025 }} />
                          </div>
                          <span className="risk-val">{(alert.risk_score * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td><span className="mono">{alert.account_count}</span></td>
                      <td><span className="amount">₹{alert.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></td>
                      <td><span className="mono">{alert.txn_count}</span></td>
                      <td style={{ maxWidth: 180 }}><span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{alert.reason_codes?.[0]?.split(':')[0] || '—'}</span></td>
                      <td><span className={`badge badge-${alert.status}`}>{alert.status}</span></td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>{formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}</td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div style={{ padding: '72px 0', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  <div style={{ fontSize: 28, marginBottom: 12, opacity: 0.12 }}>◎</div>
                  No alerts match the current filters.
                </div>
              )}
            </GlassCard>
          </AnimateIn>
        </>
      )}

      {!loading && <LiveFeed />}
    </div>
  );
}

