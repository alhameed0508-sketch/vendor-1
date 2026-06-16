import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play, RefreshCw, AlertTriangle, CheckCircle, XCircle,
  Shield, Activity, Database, Clock, User, ArrowUpRight,
  Cpu, Wifi, FileText, Zap, RotateCw, ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../auth/api';

const cardStyle = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '22px 24px',
  position: 'relative',
  overflow: 'hidden',
  boxShadow: 'var(--shadow)',
};

function StatCard({ label, value, color, icon: Icon, sub, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
      style={cardStyle}
      whileHover={{ borderColor: `${color}30`, boxShadow: `0 8px 32px rgba(0,0,0,0.12), 0 0 0 1px ${color}18`, y: -2, transition: { duration: 0.2 } }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${color}, transparent)`, opacity: 0.7 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
        {Icon && <div style={{ color, opacity: 0.5 }}><Icon size={13} /></div>}
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 700, color, letterSpacing: '-0.5px', lineHeight: 1, marginBottom: sub ? 6 : 0 }}>{value}</div>
      {sub && <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.3px' }}>{sub}</div>}
    </motion.div>
  );
}

function EscalationRow({ esc, onAction }) {
  const priorityColors = { CRITICAL: '#F43F5E', URGENT: '#FB923C', HIGH: '#FB923C' };
  const statusColors = { PENDING: '#FB923C', APPROVED: '#10B981', REJECTED: '#F43F5E', REASSIGNED: '#22D3EE' };

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      style={{
        display: 'grid', gridTemplateColumns: '100px 1fr 80px 80px 140px',
        padding: '12px 20px', borderBottom: '1px solid var(--border)', alignItems: 'center',
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(37,99,235,0.04)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-secondary)' }}>{esc.alert_id?.slice(0, 10) || '—'}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{esc.reason || '—'}</div>
      <div>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
          color: priorityColors[esc.priority] || '#FB923C', background: `${priorityColors[esc.priority] || '#FB923C'}12`,
          padding: '2px 8px', borderRadius: 4, border: `1px solid ${priorityColors[esc.priority] || '#FB923C'}25`,
        }}>
          {esc.priority}
        </span>
      </div>
      <div>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
          color: statusColors[esc.status] || '#4A5568', background: `${statusColors[esc.status] || '#4A5568'}12`,
          padding: '2px 8px', borderRadius: 4,
        }}>
          {esc.status}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {esc.status === 'PENDING' && (
          <>
            <button onClick={() => onAction(esc.id, 'APPROVE')} style={{ fontFamily: 'var(--font-mono)', fontSize: 10, padding: '3px 8px', borderRadius: 4, border: '1px solid rgba(16,185,129,0.3)', background: 'rgba(16,185,129,0.08)', color: '#10B981', cursor: 'pointer' }}>Approve</button>
            <button onClick={() => onAction(esc.id, 'REJECT')} style={{ fontFamily: 'var(--font-mono)', fontSize: 10, padding: '3px 8px', borderRadius: 4, border: '1px solid rgba(244,63,94,0.3)', background: 'rgba(244,63,94,0.08)', color: '#F43F5E', cursor: 'pointer' }}>Reject</button>
          </>
        )}
      </div>
    </motion.div>
  );
}

function AuditRow({ entry }) {
  const actionColors = {
    STATUS_CHANGE: '#22D3EE', FEEDBACK: '#10B981', RETRAIN_TRIGGERED: '#FB923C',
    STR_EXPORTED: '#8B5CF6', ESCALATION: '#F43F5E', LOGIN: 'var(--accent-primary)',
  };
  const color = actionColors[entry.action] || '#4A5568';

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '120px 140px 1fr 160px',
      padding: '10px 20px', borderBottom: '1px solid var(--border)', alignItems: 'center',
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
        {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '—'}
      </div>
      <div>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
          color, background: `${color}12`, padding: '2px 8px', borderRadius: 4,
        }}>
          {entry.action}
        </span>
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {entry.details || '—'}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-secondary)' }}>
        {entry.user_id || '—'}
      </div>
    </div>
  );
}

export default function SystemOpsPage() {
  const [activeTab, setActiveTab] = useState('escalations');
  const [escalations, setEscalations] = useState([]);
  const [deviceStats, setDeviceStats] = useState(null);
  const [ingestStatus, setIngestStatus] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningDetection, setRunningDetection] = useState(false);
  const [runningRetrain, setRunningRetrain] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/escalations').then(r => r.json()).then(b => b?.data || b).catch(() => []),
      apiFetch('/api/v1/device/stats').then(r => r.json()).then(b => b?.data || b).catch(() => null),
      apiFetch('/api/v1/ingest/status').then(r => r.json()).then(b => b?.data || b).catch(() => null),
      apiFetch('/api/v1/audit-log?limit=50').then(r => r.json()).then(b => b?.data || b).catch(() => []),
    ]).then(([escData, devData, ingData, audData]) => {
      setEscalations(Array.isArray(escData) ? escData : escData?.escalations || []);
      setDeviceStats(devData);
      setIngestStatus(ingData);
      setAuditLog(Array.isArray(audData) ? audData : audData?.entries || []);
      setLoading(false);
    });
  }, []);

  const handleEscalationAction = async (escalationId, action) => {
    try {
      await apiFetch(`/api/v1/escalations/${escalationId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, notes: '' }),
      });
      setEscalations(prev => prev.map(e => e.id === escalationId ? { ...e, status: action === 'APPROVE' ? 'APPROVED' : 'REJECTED' } : e));
      toast.success(`Escalation ${action.toLowerCase()}d`);
    } catch (err) {
      toast.error('Action failed');
    }
  };

  const handleRunDetection = async () => {
    setRunningDetection(true);
    try {
      await apiFetch('/api/v1/run-detection', { method: 'POST' });
      toast.success('Detection pipeline triggered');
    } catch (err) {
      toast.error('Failed to trigger detection');
    } finally {
      setRunningDetection(false);
    }
  };

  const handleRetrain = async () => {
    setRunningRetrain(true);
    try {
      const res = await apiFetch('/api/v1/feedback/retrain', { method: 'POST' });
      const body = await res.json();
      const data = body?.data || body;
      toast.success(`Retrain triggered. New threshold: ${data?.new_smurf_threshold?.toFixed(3) || '—'}`);
    } catch (err) {
      toast.error('Retrain failed');
    } finally {
      setRunningRetrain(false);
    }
  };

  const pendingEscalations = escalations.filter(e => e.status === 'PENDING').length;

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '1px', color: 'var(--text-muted)' }}>LOADING SYSTEM OPS...</span>
    </div>
  );

  return (
    <div style={{ padding: '32px 36px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <h1 className="gradient-text" style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', margin: 0 }}>System Operations</h1>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: '#A78BFA', letterSpacing: '1.5px', textTransform: 'uppercase',
            background: 'rgba(167,139,250,0.08)', border: '1px solid rgba(167,139,250,0.2)', padding: '2px 8px', borderRadius: 4,
          }}>ADMIN</span>
        </div>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.5px' }}>
          // escalation queue · device profiling · ingest monitoring · audit trail · model controls
        </p>
      </motion.div>

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        <StatCard label="Pending Escalations" value={pendingEscalations} color={pendingEscalations > 0 ? '#F43F5E' : '#10B981'} icon={AlertTriangle} index={0} />
        <StatCard label="Device Trust Avg" value={deviceStats?.avg_trust_score ? `${(deviceStats.avg_trust_score * 100).toFixed(0)}%` : '—'} color="#22D3EE" icon={Cpu} sub={deviceStats?.total_devices ? `${deviceStats.total_devices} devices tracked` : undefined} index={1} />
        <StatCard label="Kafka Status" value={ingestStatus?.status || ingestStatus?.consumer_status || 'DEMO'} color={ingestStatus?.status === 'CONNECTED' ? '#10B981' : '#FB923C'} icon={Wifi} sub={ingestStatus?.lag !== undefined ? `lag: ${ingestStatus.lag}` : undefined} index={2} />
        <StatCard label="Audit Entries" value={auditLog.length} color="#A78BFA" icon={FileText} index={3} />
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        <motion.button
          onClick={handleRunDetection}
          disabled={runningDetection}
          className="btn"
          style={{
            padding: '10px 20px', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(37,99,235,0.12)', border: '1px solid rgba(37,99,235,0.3)', color: 'var(--accent-secondary)', borderRadius: 8, cursor: runningDetection ? 'wait' : 'pointer',
          }}
          whileHover={!runningDetection ? { scale: 1.02 } : {}}
          whileTap={!runningDetection ? { scale: 0.98 } : {}}
        >
          {runningDetection ? <RefreshCw size={12} className="spinning" /> : <Play size={12} />}
          {runningDetection ? 'Running...' : 'Run Detection Pipeline'}
        </motion.button>
        <motion.button
          onClick={handleRetrain}
          disabled={runningRetrain}
          className="btn"
          style={{
            padding: '10px 20px', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)', color: '#10B981', borderRadius: 8, cursor: runningRetrain ? 'wait' : 'pointer',
          }}
          whileHover={!runningRetrain ? { scale: 1.02 } : {}}
          whileTap={!runningRetrain ? { scale: 0.98 } : {}}
        >
          {runningRetrain ? <RefreshCw size={12} className="spinning" /> : <RotateCw size={12} />}
          {runningRetrain ? 'Retraining...' : 'Trigger Model Retrain'}
        </motion.button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 20 }}>
        {[
          { id: 'escalations', label: 'Escalations', icon: AlertTriangle, badge: pendingEscalations },
          { id: 'device', label: 'Device Profiling', icon: Cpu },
          { id: 'ingest', label: 'Ingest Monitor', icon: Wifi },
          { id: 'audit', label: 'Audit Log', icon: FileText },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.5px', textTransform: 'uppercase',
              padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              background: activeTab === tab.id ? 'rgba(37,99,235,0.12)' : 'transparent',
              color: activeTab === tab.id ? 'var(--accent-secondary)' : 'var(--text-muted)',
              transition: 'all 0.2s',
            }}
          >
            <tab.icon size={12} />
            {tab.label}
            {tab.badge > 0 && (
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                background: '#F43F5E', color: '#fff', padding: '1px 5px', borderRadius: 8, minWidth: 16, textAlign: 'center',
              }}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {activeTab === 'escalations' && (
          <motion.div key="esc" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', fontWeight: 700 }}>
                  // Escalation Queue ({escalations.length})
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 80px 80px 140px', padding: '10px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
                {['Alert ID', 'Reason', 'Priority', 'Status', 'Actions'].map(h => (
                  <div key={h} style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700 }}>{h}</div>
                ))}
              </div>
              {escalations.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  <CheckCircle size={24} color="#10B981" style={{ marginBottom: 8 }} /><br />No pending escalations
                </div>
              ) : (
                escalations.map((esc, i) => <EscalationRow key={esc.id || i} esc={esc} onAction={handleEscalationAction} />)
              )}
            </div>
          </motion.div>
        )}

        {activeTab === 'device' && (
          <motion.div key="dev" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div style={{ ...cardStyle }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 20, fontWeight: 700 }}>
                // Device Profiling Statistics
              </div>
              {deviceStats ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                  {[
                    { label: 'Total Devices', value: deviceStats.total_devices ?? '—', color: 'var(--accent-primary)' },
                    { label: 'Shared Devices', value: deviceStats.shared_devices ?? '—', color: '#F43F5E' },
                    { label: 'Avg Trust Score', value: deviceStats.avg_trust_score ? `${(deviceStats.avg_trust_score * 100).toFixed(1)}%` : '—', color: '#10B981' },
                    { label: 'High Risk Devices', value: deviceStats.high_risk_count ?? '—', color: '#FB923C' },
                    { label: 'Recent Switches (24h)', value: deviceStats.recent_switches_24h ?? '—', color: '#22D3EE' },
                    { label: 'Unique Accounts', value: deviceStats.unique_accounts ?? '—', color: '#A78BFA' },
                  ].map(item => (
                    <div key={item.label} style={{
                      background: `${item.color}08`, border: `1px solid ${item.color}15`, borderRadius: 10, padding: '18px 20px',
                    }}>
                      <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 700, color: item.color, letterSpacing: '-0.5px', lineHeight: 1, marginBottom: 6 }}>{item.value}</div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.5px' }}>{item.label}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>Device profiling data unavailable</div>
              )}
            </div>
          </motion.div>
        )}

        {activeTab === 'ingest' && (
          <motion.div key="ing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div style={{ ...cardStyle }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 20, fontWeight: 700 }}>
                // Kafka Ingest Monitoring
              </div>
              {ingestStatus ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                  {Object.entries(ingestStatus).map(([key, value]) => {
                    const color = key.includes('status') || key.includes('health') ? (value === 'CONNECTED' || value === 'HEALTHY' ? '#10B981' : '#FB923C') : 'var(--accent-primary)';
                    return (
                      <div key={key} style={{ background: `${color}08`, border: `1px solid ${color}15`, borderRadius: 10, padding: '18px 20px' }}>
                        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, color, lineHeight: 1, marginBottom: 6 }}>
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.5px' }}>
                          {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  <Wifi size={24} color="var(--text-muted)" style={{ marginBottom: 8 }} /><br />Ingest monitoring unavailable (Kafka not configured)
                </div>
              )}
            </div>
          </motion.div>
        )}

        {activeTab === 'audit' && (
          <motion.div key="aud" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', fontWeight: 700 }}>
                  // Audit Trail ({auditLog.length} entries)
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 140px 1fr 160px', padding: '10px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
                {['Time', 'Action', 'Details', 'User'].map(h => (
                  <div key={h} style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700 }}>{h}</div>
                ))}
              </div>
              {auditLog.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>No audit entries</div>
              ) : (
                auditLog.map((entry, i) => <AuditRow key={i} entry={entry} />)
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
