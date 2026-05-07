import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import NetworkGraph from '../graph_viz/NetworkGraph';
import TimelineSlider from '../graph_viz/TimelineSlider';
import IndiaMap from '../components/IndiaMap';
import AnimatedCounter from '../components/AnimatedCounter';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';
import { SkeletonGraph, SkeletonCard } from '../components/Skeleton';
import ExplainabilityPanel from '../explainability/ExplainabilityPanel';
import { apiFetch } from '../auth/api';

export default function AlertDetail() {
  const { alertId } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [strExporting, setStrExporting] = useState(false);
  const [strExported, setStrExported] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const [escalated, setEscalated] = useState(false);
  const [vizTab, setVizTab] = useState('graph');
  const [timeRange, setTimeRange] = useState(null);

  useEffect(() => {
    apiFetch(`/api/v1/alerts/${alertId}`)
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAlert(data);
        setStatus(data.status);
        setNotes(data.investigator_notes || '');
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [alertId]);

  const saveUpdate = async () => {
    setSaving(true);
    try {
      await apiFetch(`/api/v1/alerts/${alertId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, investigator_notes: notes }),
      });
      setSaving(false);
      setSaved(true);
      toast.success('Investigation status saved');
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setSaving(false);
      toast.error('Failed to save — try again');
    }
  };

  const markFalsePositive = async () => {
    try {
      await apiFetch('/api/v1/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_id: alertId, is_true_positive: false }),
      });
      setStatus('FALSE_POSITIVE');
      toast.success('Marked as false positive');
      saveUpdate();
    } catch {
      toast.error('Failed to submit feedback');
    }
  };

  const escalateAlert = async () => {
    setEscalating(true);
    try {
      const res = await apiFetch('/api/v1/escalations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alert_id: alertId,
          reason: notes || 'Requires supervisor review',
          priority: alert.severity === 'CRITICAL' ? 'URGENT' : 'HIGH',
        }),
      });
      if (!res.ok) throw new Error();
      setEscalating(false);
      setEscalated(true);
      setStatus('UNDER_REVIEW');
      toast.success('Escalated to supervisor');
    } catch {
      setEscalating(false);
      toast.error('Escalation failed');
    }
  };

  const exportSTR = async () => {
    setStrExporting(true);
    try {
      // Download PDF directly
      const res = await apiFetch(`/api/v1/compliance/str-pdf/${alertId}`);
      if (!res.ok) throw new Error('PDF generation failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `STR_${alertId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setStrExporting(false);
      setStrExported(true);
      toast.success('STR PDF downloaded — FIU-ready');
    } catch {
      setStrExporting(false);
      toast.error('STR export failed');
    }
  };

  if (loading) return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
        {[0,1,2,3,4].map(i => <SkeletonCard key={i} />)}
      </div>
      <SkeletonGraph />
    </div>
  );
  if (!alert) return <div className="loading">Alert not found.</div>;

  const riskPct = (alert.risk_score * 100).toFixed(1);

  const metricCards = [
    { label: 'Risk Score', value: parseFloat(riskPct), suffix: '%', decimals: 1, color: alert.severity === 'CRITICAL' ? 'var(--critical)' : alert.severity === 'HIGH' ? 'var(--high)' : 'var(--accent-blue)' },
    { label: 'Confidence', value: parseFloat((alert.confidence * 100).toFixed(1)), suffix: '%', decimals: 1, color: 'var(--accent-cyan)' },
    ...(alert.gnn_score != null ? [{ label: 'GNN Score', value: parseFloat((alert.gnn_score * 100).toFixed(1)), suffix: '%', decimals: 1, color: 'var(--accent-green)' }] : []),
    { label: 'Total Amount', value: parseFloat((alert.total_amount / 100000).toFixed(2)), prefix: '₹', suffix: 'L', decimals: 2, color: 'var(--accent-amber)' },
    { label: 'Accounts', value: alert.account_count, color: 'var(--text-primary)' },
  ];

  return (
    <div style={{ padding: 24 }}>
      {/* Back nav */}
      <AnimateIn>
        <motion.button
          className="btn btn-ghost"
          style={{ marginBottom: 20 }}
          onClick={() => navigate('/')}
          whileHover={{ x: -3 }}
          whileTap={{ scale: 0.97 }}
        >
          ← Back to queue
        </motion.button>
      </AnimateIn>

      {/* Header row */}
      <AnimateIn delay={0.05}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
              <h1 style={{ fontSize: 20, fontWeight: 800 }}>{alert.alert_id}</h1>
              <span className={`badge badge-${alert.severity}`}>{alert.severity}</span>
              <span className={`badge badge-${alert.status}`}>{alert.status}</span>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              Cluster {alert.cluster_id || 'N/A'} · {alert.account_count} accounts · {alert.txn_count} transactions
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <motion.button className="btn btn-danger" onClick={markFalsePositive} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>✗ False Positive</motion.button>
            <motion.button
              className={`btn ${escalated ? 'btn-success' : 'btn-ghost'}`}
              onClick={escalateAlert}
              disabled={escalating || escalated}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              style={{ borderColor: 'var(--accent-amber)' }}
            >
              {escalating ? '...' : escalated ? '✓ Escalated' : '⬆ Escalate'}
            </motion.button>
            <motion.button
              className={`btn ${strExported ? 'btn-success' : 'btn-primary'}`}
              onClick={exportSTR}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              style={strExporting ? {
                background: 'linear-gradient(90deg, transparent, rgba(6,182,212,0.3), transparent)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.5s infinite',
              } : {}}
            >
              {strExporting ? 'Generating...' : strExported ? '✓ STR Exported' : '↑ Export STR'}
            </motion.button>
          </div>
        </div>
      </AnimateIn>

      {/* Top metric cards */}
      <StaggerContainer className="mb-6" style={{ display: 'grid', gridTemplateColumns: `repeat(${metricCards.length}, 1fr)`, gap: 12 }}>
        {metricCards.map((m) => (
          <StaggerItem key={m.label}>
            <GlassCard className="p-5 text-center">
              <div style={{ fontSize: 26, fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
                <AnimatedCounter
                  end={m.value}
                  prefix={m.prefix || ''}
                  suffix={m.suffix || ''}
                  decimals={m.decimals || 0}
                  style={{ fontSize: 26, fontWeight: 800, color: m.color, fontFamily: 'var(--font-mono)' }}
                />
              </div>
              <div className="text-xs font-mono text-[var(--text-muted)] mt-1 uppercase tracking-wider">{m.label}</div>
            </GlassCard>
          </StaggerItem>
        ))}
      </StaggerContainer>

      {/* Main two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 16, marginBottom: 16 }}>
        {/* Graph / Map visualization with tabs */}
        <AnimateIn delay={0.15}>
          <div>
            {/* Tab switcher */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
              {[
                { key: 'graph', label: 'Network Graph' },
                { key: 'map', label: 'India Map' },
              ].map(tab => (
                <motion.button
                  key={tab.key}
                  className="btn btn-ghost"
                  style={{
                    fontSize: 12, padding: '6px 14px',
                    ...(vizTab === tab.key ? { borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)', background: 'rgba(6,182,212,0.08)' } : {}),
                    position: 'relative',
                  }}
                  onClick={() => setVizTab(tab.key)}
                  whileTap={{ scale: 0.97 }}
                >
                  {tab.label}
                  {vizTab === tab.key && (
                    <motion.div
                      layoutId="viz-tab-underline"
                      style={{ position: 'absolute', bottom: -1, left: 8, right: 8, height: 2, background: 'var(--accent-cyan)', borderRadius: 1 }}
                    />
                  )}
                </motion.button>
              ))}
            </div>

            {vizTab === 'graph' ? (
              <GlassCard
                className="network-graph-container overflow-hidden"
                style={{ padding: 0 }}
                hover={false}
                glow={alert.severity === 'CRITICAL'}
                glowColor="rgba(255,59,92,0.1)"
              >
                <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>Network Topology — Social Network of Money</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Louvain + GNN detected</span>
                </div>
                <NetworkGraph nodes={alert.nodes} edges={alert.edges} timeRange={timeRange} />
                <TimelineSlider edges={alert.edges} onChange={setTimeRange} />
              </GlassCard>
            ) : (
              <IndiaMap nodes={alert.nodes} edges={alert.edges} />
            )}
          </div>
        </AnimateIn>

        {/* Right panel: reason codes + fingerprints */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Reason codes */}
          <AnimateIn delay={0.25} direction="left">
            <GlassCard className="reason-codes-panel p-5" hover={false}>
              <p className="section-title">Reason Codes</p>
              {alert.reason_codes.map((rc, i) => (
                <motion.div
                  key={i}
                  className="reason-code"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.06, type: 'spring', stiffness: 300, damping: 30 }}
                >
                  {rc}
                </motion.div>
              ))}
              {alert.reason_codes.length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No reason codes generated.</p>
              )}
            </GlassCard>
          </AnimateIn>

          {/* Shared fingerprints */}
          {(alert.shared_devices.length > 0 || alert.shared_ips.length > 0) && (
            <AnimateIn delay={0.35} direction="left">
              <GlassCard className="p-5" hover={false}>
                <p className="section-title">Shared Fingerprints</p>
                {alert.shared_devices.map((d, i) => (
                  <div key={`dev-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span className="text-[10px] bg-blue-500/15 text-accent-blue px-1.5 py-0.5 rounded font-mono">DEV</span>
                    <span className="font-mono text-xs text-[var(--text-secondary)]">{d}</span>
                  </div>
                ))}
                {alert.shared_ips.map((ip, i) => (
                  <div key={`ip-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span className="text-[10px] bg-amber-500/15 text-accent-amber px-1.5 py-0.5 rounded font-mono">IP</span>
                    <span className="font-mono text-xs text-[var(--text-secondary)]">{ip}</span>
                  </div>
                ))}
              </GlassCard>
            </AnimateIn>
          )}

          {/* Account list */}
          <AnimateIn delay={0.4} direction="left">
            <GlassCard className="p-5" style={{ flex: 1 }} hover={false}>
              <p className="section-title">Accounts in Cluster</p>
              <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                {alert.nodes.map((n, i) => (
                  <motion.div
                    key={i}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '8px 0', borderBottom: '1px solid var(--border)',
                    }}
                    initial={{ opacity: 0, x: 15 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + i * 0.04, type: 'spring', stiffness: 300, damping: 30 }}
                  >
                    <div>
                      <span className="account-id">{n.account_id}</span>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{n.bank} · {n.city}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{
                        fontSize: 10,
                        fontFamily: 'var(--font-mono)',
                        padding: '2px 6px',
                        borderRadius: 3,
                        background: n.role === 'SOURCE' || n.role === 'AGGREGATOR' ? 'rgba(255,59,92,0.15)' : 'rgba(245,158,11,0.12)',
                        color: n.role === 'SOURCE' || n.role === 'AGGREGATOR' ? 'var(--critical)' : 'var(--high)',
                      }}>{n.role}</span>
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                        score {(n.smurf_score * 100).toFixed(0)}%
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </GlassCard>
          </AnimateIn>
        </div>
      </div>

      {/* Explainability Engine */}
      <AnimateIn delay={0.3}>
        <div style={{ marginBottom: 16 }}>
          <ExplainabilityPanel alertId={alertId} explanation={alert.explanation} />
        </div>
      </AnimateIn>

      {/* Investigator workspace */}
      <AnimateIn delay={0.35}>
        <GlassCard className="investigator-workspace p-5" hover={false}>
          <p className="section-title">Investigator Workspace</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, color: 'var(--text-secondary)' }}>Status</label>
              <select
                value={status}
                onChange={e => setStatus(e.target.value)}
                className="w-full bg-surface-elevated border border-border text-[var(--text-primary)] px-3 py-2 rounded-lg text-sm font-mono"
              >
                {['OPEN', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE'].map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <motion.button
              className={`btn ${saved ? 'btn-success' : 'btn-primary'}`}
              onClick={saveUpdate}
              disabled={saving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              {saving ? '...' : saved ? '✓ Saved' : 'Save'}
            </motion.button>
          </div>
          <div style={{ marginTop: 12 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 12, color: 'var(--text-secondary)' }}>Investigation Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              placeholder="Add investigation notes..."
              className="w-full bg-surface-elevated border border-border text-[var(--text-primary)] px-3.5 py-2.5 rounded-lg font-mono text-xs resize-y"
            />
          </div>
        </GlassCard>
      </AnimateIn>
    </div>
  );
}
