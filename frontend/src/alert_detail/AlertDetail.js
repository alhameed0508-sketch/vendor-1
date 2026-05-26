import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, Check } from 'lucide-react';
import NetworkGraph from '../graph_viz/NetworkGraph';
import TimelineSlider from '../graph_viz/TimelineSlider';
import ExplainabilityPanel from '../explainability/ExplainabilityPanel';
import InvestigationChat from '../genai/InvestigationChat';
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
  const [escalating, setEscalating] = useState(false);
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
      .catch(err => {
        console.error('[AlertDetail] Failed to load alert:', err);
        setLoading(false);
      });
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
      toast.success('Saved');
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setSaving(false);
      toast.error('Failed to save');
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
      setStatus('UNDER_REVIEW');
      toast.success('Escalated');
    } catch {
      setEscalating(false);
      toast.error('Escalation failed');
    }
  };

  const exportSTR = async () => {
    setStrExporting(true);
    try {
      const res = await apiFetch(`/api/v1/compliance/str-pdf/${alertId}`);
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `STR_${alertId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setStrExporting(false);
      toast.success('STR PDF downloaded');
    } catch {
      setStrExporting(false);
      toast.error('STR export failed');
    }
  };

  if (loading) return <div className="loading"><div className="spinner" /> Loading alert...</div>;
  if (!alert) return <div className="loading">Alert not found.</div>;

  const riskPct = (alert.risk_score * 100).toFixed(1);
  const confPct = (alert.confidence * 100).toFixed(1);

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Back + Header */}
      <button className="btn btn-ghost" style={{ marginBottom: 18, fontSize: 13 }} onClick={() => navigate('/')}>
        <ArrowLeft size={14} /> Back
      </button>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, fontFamily: 'var(--font-mono)' }}>{alert.alert_id}</h1>
            <span className={`badge badge-${alert.severity}`}>{alert.severity}</span>
            <span className={`badge badge-${status}`}>{status}</span>
          </div>
          <p style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', margin: 0 }}>
            Risk {riskPct}% · Confidence {confPct}%
            {alert.gnn_score != null && ` · GNN ${(alert.gnn_score * 100).toFixed(1)}%`}
            {' · '}{alert.account_count} accounts · {alert.txn_count} txns
            {' · ₹'}{(alert.total_amount / 100000).toFixed(2)}L
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-danger" onClick={markFalsePositive}>False Positive</button>
          <button className="btn btn-ghost" onClick={escalateAlert} disabled={escalating} style={{ borderColor: 'var(--accent-amber)' }}>
            {escalating ? '...' : 'Escalate'}
          </button>
          <button className="btn btn-primary" onClick={exportSTR} disabled={strExporting}>
            {strExporting ? 'Exporting...' : 'Export STR'}
          </button>
        </div>
      </div>

      {/* Main two-column layout */}
      <div className="grid-detail" style={{ marginBottom: 16 }}>
        {/* Network Graph */}
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', fontSize: 13, fontWeight: 600 }}>
            Network Graph
          </div>
          <NetworkGraph nodes={alert.nodes} edges={alert.edges} timeRange={timeRange} />
          <TimelineSlider edges={alert.edges} onChange={setTimeRange} />
        </div>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Reason codes */}
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 18, boxShadow: 'var(--shadow-sm)' }}>
            <p className="section-title">Reason Codes</p>
            {alert.reason_codes.length === 0 && (
              <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No reason codes.</p>
            )}
            {alert.reason_codes.map((rc, i) => (
              <div key={i} className="reason-code">{rc}</div>
            ))}
          </div>

          {/* Shared fingerprints */}
          {(alert.shared_devices.length > 0 || alert.shared_ips.length > 0) && (
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 18, boxShadow: 'var(--shadow-sm)' }}>
              <p className="section-title">Shared Fingerprints</p>
              {alert.shared_devices.map((d, i) => (
                <div key={`dev-${i}`} style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, background: 'rgba(56,189,248,0.15)', color: 'var(--accent-blue)', padding: '2px 7px', borderRadius: 4, marginRight: 8 }}>DEV</span>
                  {d}
                </div>
              ))}
              {alert.shared_ips.map((ip, i) => (
                <div key={`ip-${i}`} style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, background: 'rgba(245,158,11,0.15)', color: 'var(--accent-amber)', padding: '2px 7px', borderRadius: 4, marginRight: 8 }}>IP</span>
                  {ip}
                </div>
              ))}
            </div>
          )}

          {/* Account list */}
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 18, flex: 1, boxShadow: 'var(--shadow-sm)' }}>
            <p className="section-title">Accounts ({alert.nodes.length})</p>
            <div style={{ maxHeight: 240, overflowY: 'auto' }}>
              {alert.nodes.map((n, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 0', borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div>
                    <span className="account-id">{n.account_id}</span>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{n.bank} · {n.city}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{
                      fontSize: 11, fontFamily: 'var(--font-mono)', padding: '2px 7px', borderRadius: 4,
                      background: n.role === 'SOURCE' || n.role === 'AGGREGATOR' ? 'rgba(255,59,92,0.15)' : 'rgba(245,158,11,0.12)',
                      color: n.role === 'SOURCE' || n.role === 'AGGREGATOR' ? 'var(--critical)' : 'var(--high)',
                    }}>{n.role}</span>
                    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                      {(n.smurf_score * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Explainability */}
      <div style={{ marginBottom: 16 }}>
        <ExplainabilityPanel alertId={alertId} explanation={alert.explanation} />
      </div>

      {/* GenAI Chat */}
      <div style={{ marginBottom: 16 }}>
        <InvestigationChat alertId={alertId} alertData={alert} />
      </div>

      {/* Investigator Workspace */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, boxShadow: 'var(--shadow-sm)' }}>
        <p className="section-title">Investigator Workspace</p>
        <div className="grid-workspace">
          <div>
            <label htmlFor="alert-status" style={{ display: 'block', marginBottom: 6, fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>Status</label>
            <select
              id="alert-status"
              value={status}
              onChange={e => setStatus(e.target.value)}
              style={{
                width: '100%', padding: '10px 14px', fontSize: 14,
                fontFamily: 'var(--font-mono)',
                background: 'var(--bg-elevated)', color: 'var(--text-primary)',
                border: '1px solid var(--border)', borderRadius: 8,
              }}
            >
              {['OPEN', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <button className={`btn ${saved ? 'btn-success' : 'btn-primary'}`} onClick={saveUpdate} disabled={saving}>
            {saving ? '...' : saved ? <><Check size={12} /> Saved</> : 'Save'}
          </button>
        </div>
        <div style={{ marginTop: 10 }}>
          <label htmlFor="alert-notes" style={{ display: 'block', marginBottom: 6, fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>Notes</label>
          <textarea
            id="alert-notes"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            placeholder="Investigation notes..."
            style={{
              width: '100%', padding: '10px 14px', fontSize: 13,
              fontFamily: 'var(--font-mono)',
              background: 'var(--bg-elevated)', color: 'var(--text-primary)',
              border: '1px solid var(--border)', borderRadius: 8,
              resize: 'vertical', boxSizing: 'border-box',
            }}
          />
        </div>
      </div>
    </div>
  );
}
