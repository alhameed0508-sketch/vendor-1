import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedCounter from '../components/AnimatedCounter';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { apiFetch } from '../auth/api';
import {
  API_ALERTS_LIMIT,
  API_AUDIT_LIMIT,
  API_STR_LIMIT,
  RISK_FILTER_THRESHOLD,
  AMOUNT_DIVISOR_LAKHS,
} from '../config';

const STATUS_COLORS = {
  DRAFT: '#FB923C',
  READY_FOR_SUBMISSION: '#22D3EE',
  SUBMITTED: '#6366F1',
  ACKNOWLEDGED: '#10B981',
};

const STATUS_LABELS = {
  DRAFT: 'Draft',
  READY_FOR_SUBMISSION: 'Ready',
  SUBMITTED: 'Submitted',
  ACKNOWLEDGED: 'Acknowledged',
};

const NEXT_ACTION = {
  DRAFT: { label: 'Approve', endpoint: 'approve', body: (user) => ({ approved_by: user || 'demo_user' }) },
  READY_FOR_SUBMISSION: { label: 'Submit to FIU', endpoint: 'submit', body: () => ({}) },
  SUBMITTED: { label: 'Acknowledge', endpoint: 'acknowledge', body: () => ({}) },
};

export default function CompliancePortal() {
  const [alerts, setAlerts] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [strReports, setStrReports] = useState([]);
  const [exported, setExported] = useState(false);
  const [auditLog, setAuditLog] = useState([]);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchStrList = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/compliance/strs?limit=${API_STR_LIMIT}`);
      const body = await res.json();
      const data = body?.data || body;
      const records = data?.records || (Array.isArray(data) ? data : []);
      if (Array.isArray(records)) {
        setStrReports(records);
        if (records.length > 0) setExported(true);
      }
    } catch (err) {
      console.error('[Compliance] STR list fetch failed:', err);
    }
  }, []);

  useEffect(() => {
    apiFetch(`/api/v1/alerts?limit=${API_ALERTS_LIMIT}`)
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        const alertList = data?.alerts || (Array.isArray(data) ? data : []);
        const open = (Array.isArray(alertList) ? alertList : []).filter(a =>
          a.risk_score > RISK_FILTER_THRESHOLD && a.status !== 'FALSE_POSITIVE'
        );
        setAlerts(open);
        setLoading(false);
      })
      .catch(err => {
        console.error('[Compliance] Failed to load alerts:', err);
        setLoading(false);
      });

    fetchStrList();

    apiFetch(`/api/v1/audit-log?limit=${API_AUDIT_LIMIT}`)
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAuditLog(Array.isArray(data) ? data : []);
      })
      .catch(err => console.error('[Compliance] Audit log fetch failed:', err));
  }, [fetchStrList]);

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
    try {
      const res = await apiFetch('/api/v1/compliance/str-export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: [...selected] }),
      });
      const body = await res.json();
      if (body?.success === false) {
        console.error('[Compliance] STR export failed:', body.error);
      } else {
        setExported(true);
        await fetchStrList();
      }
    } catch (err) {
      console.error('[Compliance] STR export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const advanceStatus = async (strId, action) => {
    setActionLoading(strId);
    try {
      const res = await apiFetch(`/api/v1/compliance/str/${strId}/${action.endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action.body('demo_user')),
      });
      const body = await res.json();
      if (body?.success !== false) {
        await fetchStrList();
      }
    } catch (err) {
      console.error('[Compliance] STR action failed:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const downloadPdf = async (alertId) => {
    try {
      const res = await apiFetch(`/api/v1/compliance/str-pdf/${alertId}`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `STR_${alertId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('[Compliance] PDF download failed:', err);
    }
  };

  const totalSelected = [...selected].reduce((sum, id) => {
    const a = alerts.find(x => x.alert_id === id);
    return sum + (a?.total_amount || 0);
  }, 0);

  const statusCounts = strReports.reduce((acc, r) => {
    const s = r.status || 'DRAFT';
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1440, margin: '0 auto' }}>
      <AnimateIn>
        <div style={{ marginBottom: 24 }}>
          <h1 className="text-page-title" style={{ fontSize: 22, marginBottom: 4 }}>Compliance Portal</h1>
          <p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)', fontSize: 12 }}>
            Suspicious Transaction Report (STR) generation · FIU-IND format · RBI AML/CFT compliance
          </p>
        </div>
      </AnimateIn>

      {/* Compliance status bar */}
      <AnimateIn delay={0.05}>
        <GlassCard className="mb-5 p-5" hover={false} style={{ display: 'flex', gap: 0, alignItems: 'center' }}>
          {[
            { label: 'Reportable Alerts', value: alerts.length, color: 'var(--accent-amber)' },
            { label: 'Selected for STR', value: selected.size, color: 'var(--accent-cyan)' },
            { label: 'Total Amount', value: `₹${(totalSelected / AMOUNT_DIVISOR_LAKHS).toFixed(2)}L`, color: 'var(--accent-amber)' },
            { label: 'STRs Filed', value: strReports.length, color: 'var(--accent-green)' },
            { label: 'FIU Format', value: 'v2.1', color: 'var(--text-muted)' },
          ].map((s, i, arr) => (
            <React.Fragment key={s.label}>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.05 }}
                style={{ padding: '0 20px' }}
              >
                <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-sans)', color: 'var(--text-primary)' }}>
                  {typeof s.value === 'number' ? (
                    <AnimatedCounter end={s.value} style={{ fontSize: 22, fontWeight: 700, color: s.color, fontFamily: 'var(--font-sans)' }} />
                  ) : s.value}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', }}>{s.label}</div>
              </motion.div>
              {i < arr.length - 1 && (
                <div style={{ width: 1, height: 32, background: 'var(--border-bright)', flexShrink: 0 }} />
              )}
            </React.Fragment>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <motion.button className="btn btn-ghost" onClick={toggleAll} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              {selected.size === alerts.length ? 'Deselect All' : 'Select All'}
            </motion.button>
            <motion.button
              className={`btn ${exported ? 'btn-success' : 'btn-primary'} ${selected.size > 0 && !exported && !exporting ? 'btn-pulse' : ''}`}
              onClick={exportSTR}
              disabled={!selected.size || exporting}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              {exporting ? '...' : exported ? `+ Export ${selected.size || 'More'} STR${selected.size !== 1 ? 's' : ''}` : `Export ${selected.size} STR${selected.size !== 1 ? 's' : ''}`}
            </motion.button>
          </div>
        </GlassCard>
      </AnimateIn>

      {/* STR pipeline status */}
      {strReports.length > 0 && (
        <AnimateIn delay={0.08}>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            {Object.entries(STATUS_COLORS).map(([status, color]) => (
              <div key={status} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 14px', borderRadius: 6,
                background: 'transparent', border: '1px solid var(--border)',
              }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-secondary)' }}>
                  {STATUS_LABELS[status]}
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-sans)', color }}>
                  {statusCounts[status] || 0}
                </span>
              </div>
            ))}
          </div>
        </AnimateIn>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: 16 }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
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
                              fontSize: 12, color: '#000',
                            }}
                            whileTap={{ scale: 0.85 }}
                            animate={{ scale: selected.has(a.alert_id) ? [1, 1.15, 1] : 1 }}
                            transition={{ duration: 0.2 }}
                          >
                            {selected.has(a.alert_id) ? '✓' : ''}
                          </motion.div>
                        </td>
                        <td><span className="mono" style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500 }}>{a.alert_id}</span></td>
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
                        <td><span className="amount">{a.total_amount != null ? `₹${a.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}</span></td>
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
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Exported STR list — shown first for prominence */}
          <AnimateIn delay={0.1} direction="left">
            <GlassCard className="p-5" hover={false} style={{ borderLeft: '2px solid var(--border)', borderRadius: '0 8px 8px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <p className="section-title" style={{ margin: 0 }}>
                  STR Reports {strReports.length > 0 ? `(${strReports.length})` : ''}
                </p>
                {strReports.length > 0 && (
                  <span style={{
                    fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--accent-green)',
                    background: 'rgba(16,185,129,0.1)', padding: '2px 8px', borderRadius: 4,
                  }}>
                    FIU-IND v2.1
                  </span>
                )}
              </div>
              {strReports.length === 0 ? (
                <div style={{ padding: '20px 0', textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-sans)' }}>
                    No STRs filed yet. Select alerts and click Export to generate reports.
                  </div>
                </div>
              ) : (
                <div style={{ maxHeight: 480, overflowY: 'auto' }}>
                  <AnimatePresence mode="popLayout">
                    {strReports.map((r, i) => {
                      const status = r.status || 'DRAFT';
                      const statusColor = STATUS_COLORS[status] || '#10B981';
                      const alertId = r.alert_id || (r.alert_ids && r.alert_ids[0]) || '—';
                      const action = NEXT_ACTION[status];
                      const accountCount = r.accounts_involved?.length || r.account_ids?.length || 0;

                      return (
                        <motion.div
                          key={r.str_id}
                          layout
                          style={{
                            padding: '10px 12px', marginBottom: 8, borderRadius: 6,
                            background: 'var(--bg-elevated)',
                            border: `1px solid ${statusColor}20`,
                          }}
                          initial={{ opacity: 0, x: 20 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -20 }}
                          transition={{ delay: i * 0.03 }}
                        >
                          {/* Header: STR ID + Status badge */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                              {r.str_id}
                            </span>
                            <span style={{
                              fontSize: 12, fontFamily: 'var(--font-sans)', fontWeight: 700,
                              background: `${statusColor}20`, color: statusColor,
                              padding: '2px 8px', borderRadius: 4, }}>
                              {STATUS_LABELS[status] || status}
                            </span>
                          </div>

                          {/* Alert + financial data */}
                          <div style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                            <span style={{ color: 'var(--text-primary)' }}>{alertId}</span>
                            {r.total_amount != null && (
                              <span> · <span style={{ color: 'var(--accent-amber)' }}>₹{Number(r.total_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></span>
                            )}
                            {r.transaction_count != null && (
                              <span> · {r.transaction_count} txns</span>
                            )}
                            {accountCount > 0 && (
                              <span> · {accountCount} accts</span>
                            )}
                          </div>

                          {/* Risk + entity */}
                          <div style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                            {r.risk_score != null && (
                              <span style={{ color: r.risk_score > 0.8 ? '#EF4444' : r.risk_score > 0.5 ? '#FB923C' : 'var(--text-muted)' }}>
                                Risk: {(r.risk_score * 100).toFixed(0)}%
                              </span>
                            )}
                            {r.reporting_entity && <span> · {r.reporting_entity}</span>}
                            {r.fiu_reference && <span> · Ref: {r.fiu_reference}</span>}
                          </div>

                          {/* Action buttons */}
                          <div style={{ display: 'flex', gap: 6 }}>
                            {action && (
                              <motion.button
                                className="btn btn-ghost"
                                style={{
                                  fontSize: 12, padding: '3px 10px',
                                  border: `1px solid ${statusColor}40`,
                                  color: statusColor,
                                }}
                                onClick={(e) => { e.stopPropagation(); advanceStatus(r.str_id, action); }}
                                disabled={actionLoading === r.str_id}
                                whileHover={{ scale: 1.03 }}
                                whileTap={{ scale: 0.97 }}
                              >
                                {actionLoading === r.str_id ? '...' : action.label}
                              </motion.button>
                            )}
                            <motion.button
                              className="btn btn-ghost"
                              style={{ fontSize: 12, padding: '3px 10px', color: 'var(--text-muted)' }}
                              onClick={(e) => { e.stopPropagation(); downloadPdf(alertId); }}
                              whileHover={{ scale: 1.03 }}
                              whileTap={{ scale: 0.97 }}
                            >
                              PDF
                            </motion.button>
                            {status === 'ACKNOWLEDGED' && (
                              <span style={{ fontSize: 12, color: 'var(--accent-green)', fontFamily: 'var(--font-sans)', alignSelf: 'center', marginLeft: 'auto' }}>
                                ✓ Complete
                              </span>
                            )}
                          </div>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>
                </div>
              )}
            </GlassCard>
          </AnimateIn>

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
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 10px', borderBottom: '1px solid var(--border)',
                    borderRadius: 4,
                    background: i % 2 === 0 ? 'var(--bg-elevated)' : 'transparent',
                  }}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.05 }}
                >
                  <motion.span
                    style={{ color: c.done ? 'var(--accent-green)' : 'var(--text-muted)', fontSize: 14, flexShrink: 0 }}
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

          {/* Live Audit Log */}
          <AnimateIn delay={0.3} direction="left">
            <GlassCard className="p-4" hover={false} style={{ borderLeft: '2px solid var(--border)', borderRadius: '0 8px 8px 0' }}>
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-3">Audit Trail</p>
              {auditLog.length === 0 ? (
                <p className="text-xs text-[var(--text-muted)] font-mono">No audit entries yet. Actions will be logged here.</p>
              ) : (
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {auditLog.slice(0, 15).map((entry, i) => {
                    const actionColor = entry.action === 'ESCALATION_CREATED' ? 'var(--accent-amber)'
                      : entry.action === 'FEEDBACK' ? 'var(--accent-green)'
                      : 'var(--accent-cyan)';
                    return (
                      <div key={entry.log_id || i} style={{
                        padding: '6px 0 6px 10px', borderBottom: '1px solid var(--border)',
                        fontSize: 12, fontFamily: 'var(--font-sans)',
                        borderLeft: `2px solid ${actionColor}`,
                        marginBottom: 2,
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: actionColor }}>
                            {entry.action}
                          </span>
                          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                            {new Date(entry.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                          {entry.user} {entry.alert_id ? `· ${entry.alert_id}` : ''} {entry.details ? `· ${entry.details}` : ''}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </GlassCard>
          </AnimateIn>
        </div>
      </div>
    </div>
  );
}
