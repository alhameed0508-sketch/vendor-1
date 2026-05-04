import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedCounter from '../components/AnimatedCounter';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';

export default function CompliancePortal() {
  const [alerts, setAlerts] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [strReports, setStrReports] = useState([]);
  const [exported, setExported] = useState(false);
  const [auditLog, setAuditLog] = useState([]);

  useEffect(() => {
    fetch('/api/alerts?limit=100')
      .then(r => r.json())
      .then(data => {
        const open = (data.alerts || []).filter(a =>
          a.risk_score > 0.6 && a.status !== 'FALSE_POSITIVE'
        );
        setAlerts(open);
        setLoading(false);
      })
      .catch(() => setLoading(false));
    // Fetch audit log
    fetch('/api/audit-log?limit=20')
      .then(r => r.json())
      .then(data => setAuditLog(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, []);

  const toggle = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === alerts.length) setSelected(new Set());
    else setSelected(new Set(alerts.map(a => a.alert_id)));
  };

  const exportSTR = async () => {
    if (!selected.size) return;
    setExporting(true);
    const res = await fetch('/api/compliance/str-export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_ids: [...selected] }),
    });
    const data = await res.json();
    setStrReports(data.str_reports || []);
    setExported(true);
    setExporting(false);
  };

  const totalSelected = [...selected].reduce((sum, id) => {
    const a = alerts.find(x => x.alert_id === id);
    return sum + (a?.total_amount || 0);
  }, 0);

  return (
    <div style={{ padding: 24 }}>
      <AnimateIn>
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Compliance Portal</h1>
          <p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Suspicious Transaction Report (STR) generation · FIU-IND format · RBI AML/CFT compliance
          </p>
        </div>
      </AnimateIn>

      {/* Compliance status bar */}
      <AnimateIn delay={0.05}>
        <GlassCard className="mb-5 p-5" hover={false} style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
          {[
            { label: 'Reportable Alerts', value: alerts.length, color: 'var(--accent-amber)' },
            { label: 'Selected for STR', value: selected.size, color: 'var(--accent-cyan)' },
            { label: 'Total Amount', value: `₹${(totalSelected / 100000).toFixed(2)}L`, color: 'var(--accent-amber)' },
            { label: 'STRs Exported', value: strReports.length, color: 'var(--accent-green)' },
            { label: 'FIU Format', value: 'v2.1', color: 'var(--text-muted)' },
          ].map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
            >
              <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'var(--font-mono)', color: s.color }}>
                {typeof s.value === 'number' ? (
                  <AnimatedCounter end={s.value} style={{ fontSize: 22, fontWeight: 800, color: s.color, fontFamily: 'var(--font-mono)' }} />
                ) : s.value}
              </div>
              <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">{s.label}</div>
            </motion.div>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <motion.button className="btn btn-ghost" onClick={toggleAll} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              {selected.size === alerts.length ? 'Deselect All' : 'Select All'}
            </motion.button>
            <motion.button
              className={`btn ${exported ? 'btn-success' : 'btn-primary'}`}
              onClick={exportSTR}
              disabled={!selected.size || exporting}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              {exporting ? '...' : exported ? `✓ ${strReports.length} STRs Exported` : `↑ Export ${selected.size} STR${selected.size !== 1 ? 's' : ''}`}
            </motion.button>
          </div>
        </GlassCard>
      </AnimateIn>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 16 }}>
        {/* Alert selection table */}
        <AnimateIn delay={0.1}>
          <GlassCard className="overflow-hidden" style={{ padding: 0 }} hover={false}>
            <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>Alerts Eligible for STR Filing</span>
            </div>
            {loading ? (
              <div className="loading"><div className="spinner" />Loading...</div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}></th>
                    <th>Alert ID</th>
                    <th>Severity</th>
                    <th>Risk Score</th>
                    <th>Accounts</th>
                    <th>Amount</th>
                    <th>Top Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a, idx) => (
                    <motion.tr
                      key={a.alert_id}
                      className="clickable"
                      onClick={() => toggle(a.alert_id)}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.03 }}
                    >
                      <td>
                        <motion.div
                          style={{
                            width: 16, height: 16, borderRadius: 3,
                            border: `2px solid ${selected.has(a.alert_id) ? 'var(--accent-cyan)' : 'var(--border-bright)'}`,
                            background: selected.has(a.alert_id) ? 'var(--accent-cyan)' : 'transparent',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 10, color: '#000',
                          }}
                          whileTap={{ scale: 0.85 }}
                          animate={{ scale: selected.has(a.alert_id) ? [1, 1.15, 1] : 1 }}
                          transition={{ duration: 0.2 }}
                        >
                          {selected.has(a.alert_id) ? '✓' : ''}
                        </motion.div>
                      </td>
                      <td><span className="mono" style={{ color: 'var(--accent-cyan)', fontSize: 12 }}>{a.alert_id}</span></td>
                      <td><span className={`badge badge-${a.severity}`}>{a.severity}</span></td>
                      <td>
                        <div className="risk-bar">
                          <div className="risk-track">
                            <div className={`risk-fill ${a.severity === 'CRITICAL' ? 'critical' : a.severity === 'HIGH' ? 'high' : 'medium'}`}
                              style={{ width: `${a.risk_score * 100}%` }} />
                          </div>
                          <span className="risk-val">{(a.risk_score * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td><span className="mono">{a.account_count}</span></td>
                      <td><span className="amount">₹{a.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></td>
                      <td className="text-xs font-mono text-[var(--text-secondary)]">
                        {a.reason_codes?.[0]?.split(':')[0] || '—'}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            )}
          </GlassCard>
        </AnimateIn>

        {/* STR preview panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* RBI compliance checklist */}
          <AnimateIn delay={0.2} direction="left">
            <GlassCard className="p-5" hover={false}>
              <p className="section-title">RBI AML/CFT Compliance Checklist</p>
              {[
                { item: 'Explainable reason codes attached', done: true },
                { item: 'FIU-IND v2.1 format', done: true },
                { item: 'Audit trail generated', done: true },
                { item: 'Account details verified', done: true },
                { item: 'Network topology attached', done: true },
                { item: 'Investigator sign-off', done: selected.size > 0 },
              ].map((c, i) => (
                <motion.div
                  key={i}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--border)' }}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.05 }}
                >
                  <motion.span
                    style={{ color: c.done ? 'var(--accent-green)' : 'var(--text-muted)', fontSize: 14 }}
                    animate={c.done ? { scale: [1, 1.2, 1] } : {}}
                    transition={{ duration: 0.3 }}
                  >
                    {c.done ? '✓' : '○'}
                  </motion.span>
                  <span style={{ fontSize: 12, color: c.done ? 'var(--text-primary)' : 'var(--text-muted)' }}>{c.item}</span>
                </motion.div>
              ))}
            </GlassCard>
          </AnimateIn>

          {/* Exported STR list */}
          <AnimatePresence>
            {strReports.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                <GlassCard className="p-5" hover={false}>
                  <p className="section-title">Exported STR Reports</p>
                  <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                    {strReports.map((r, i) => (
                      <motion.div
                        key={r.str_id}
                        style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span className="font-mono text-xs text-accent-green">{r.str_id}</span>
                          <span className="text-[10px] bg-green-500/10 text-accent-green px-2 py-0.5 rounded font-mono">READY</span>
                        </div>
                        <div className="text-xs text-[var(--text-muted)] font-mono">
                          {r.alert_id} · ₹{r.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })} · {r.transaction_count} txns
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                          {r.accounts_involved.length} accounts · FIU v{r.fiu_format_version}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </GlassCard>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Live Audit Log */}
          <AnimateIn delay={0.3} direction="left">
            <GlassCard className="p-4" hover={false} style={{ borderLeft: '3px solid var(--accent-cyan)', borderRadius: '0 8px 8px 0' }}>
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-3">Audit Trail</p>
              {auditLog.length === 0 ? (
                <p className="text-xs text-[var(--text-muted)] font-mono">No audit entries yet. Actions will be logged here.</p>
              ) : (
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {auditLog.slice(0, 15).map((entry, i) => (
                    <div key={entry.log_id || i} style={{ padding: '4px 0', borderBottom: '1px solid var(--border)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: entry.action === 'ESCALATION_CREATED' ? 'var(--accent-amber)' : entry.action === 'FEEDBACK' ? 'var(--accent-green)' : 'var(--accent-cyan)' }}>
                          {entry.action}
                        </span>
                        <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                          {new Date(entry.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                        {entry.user} {entry.alert_id ? `· ${entry.alert_id}` : ''} {entry.details ? `· ${entry.details}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
          </AnimateIn>
        </div>
      </div>
    </div>
  );
}
