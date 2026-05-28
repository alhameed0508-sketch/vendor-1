import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { Shield, AlertTriangle, Phone, Eye } from 'lucide-react';

/* ── Constants ── */

const RECOMMENDATION_COLORS = {
  BLOCK_HARD: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', text: '#EF4444' },
  BLOCK_WITH_EDUCATION: { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', text: '#F59E0B' },
  DELAY_1HR: { bg: 'rgba(234,179,8,0.12)', border: 'rgba(234,179,8,0.3)', text: '#EAB308' },
  DELAY_30S: { bg: 'rgba(59,130,246,0.12)', border: 'rgba(59,130,246,0.3)', text: '#3B82F6' },
  ALLOW: { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)', text: '#10B981' },
};

const STATUS_COLORS = {
  PENDING: { bg: 'rgba(234,179,8,0.10)', text: '#EAB308' },
  BLOCKED: { bg: 'rgba(239,68,68,0.10)', text: '#EF4444' },
  DELAYED: { bg: 'rgba(59,130,246,0.10)', text: '#3B82F6' },
  WARNED: { bg: 'rgba(245,158,11,0.10)', text: '#F59E0B' },
  RELEASED: { bg: 'rgba(16,185,129,0.10)', text: '#10B981' },
};

const INTERVENTION_ACTIONS = ['BLOCK', 'DELAY', 'WARN', 'RELEASE'];

const ACTION_STYLES = {
  BLOCK: { bg: 'rgba(239,68,68,0.15)', border: '#EF4444', text: '#EF4444' },
  DELAY: { bg: 'rgba(59,130,246,0.15)', border: '#3B82F6', text: '#3B82F6' },
  WARN: { bg: 'rgba(245,158,11,0.15)', border: '#F59E0B', text: '#F59E0B' },
  RELEASE: { bg: 'rgba(16,185,129,0.15)', border: '#10B981', text: '#10B981' },
};

const DEFAULT_FORM = {
  sender: { account_id: 'ACCT-SENDER-001', age: 62, account_age_days: 45 },
  receiver: { account_id: 'ACCT-RECV-007' },
  transaction: { amount: 95000, channel: 'UPI', narration: 'Investment returns - urgent transfer' },
  session_context: { active_call: true, app_switches: 3 },
  receiver_mule_score: 0.78,
};

/* ── Shared Styles ── */

const sectionTitleStyle = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  letterSpacing: '1.5px',
  textTransform: 'uppercase',
  fontWeight: 700,
  marginBottom: 14,
};

const labelStyle = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  letterSpacing: '0.5px',
  textTransform: 'uppercase',
  marginBottom: 4,
  display: 'block',
};

const inputStyle = {
  width: '100%',
  padding: '8px 10px',
  background: 'rgba(15,20,33,0.6)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 6,
  color: 'var(--text-primary)',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  outline: 'none',
  transition: 'border-color 0.2s',
  boxSizing: 'border-box',
};

const monoSmall = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  letterSpacing: '0.3px',
};

/* ── Helper Components ── */

function RecommendationBadge({ recommendation }) {
  const colors = RECOMMENDATION_COLORS[recommendation] || RECOMMENDATION_COLORS.ALLOW;
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      background: colors.bg,
      border: `1px solid ${colors.border}`,
      color: colors.text,
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.5px',
    }}>
      {recommendation}
    </span>
  );
}

function StatusBadge({ status }) {
  const colors = STATUS_COLORS[status] || { bg: 'rgba(255,255,255,0.05)', text: 'var(--text-muted)' };
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 7px',
      borderRadius: 4,
      background: colors.bg,
      color: colors.text,
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      fontWeight: 600,
      letterSpacing: '0.5px',
    }}>
      {status}
    </span>
  );
}

function RiskBar({ value, label }) {
  const pct = Math.min(Math.max((value || 0) * 100, 0), 100);
  const color = pct >= 80 ? '#EF4444' : pct >= 60 ? '#F59E0B' : pct >= 40 ? '#EAB308' : '#10B981';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {label && (
        <span style={{ ...monoSmall, color: 'var(--text-muted)', minWidth: 80, fontSize: 10 }}>
          {label}
        </span>
      )}
      <div style={{
        flex: 1, height: 4, background: 'rgba(255,255,255,0.06)',
        borderRadius: 2, overflow: 'hidden', minWidth: 40,
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          style={{ height: '100%', background: color, borderRadius: 2 }}
        />
      </div>
      <span style={{ ...monoSmall, color, fontWeight: 600, minWidth: 36, textAlign: 'right' }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function FormField({ label, children }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

/* ── Section 1: Victim Alert Feed ── */

function VictimAlertFeed({ alerts, loading, onSelect, selectedId }) {
  if (loading) {
    return (
      <GlassCard hover={false} style={{ padding: 0 }}>
        <div style={{
          padding: '14px 18px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <AlertTriangle size={14} color="#F59E0B" />
          <span style={{ ...sectionTitleStyle, marginBottom: 0 }}>Victim Alert Feed</span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '48px 24px', gap: 10, color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)', fontSize: 12,
        }}>
          <div className="spinner" style={{ width: 16, height: 16 }} />
          Loading victim alerts...
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard hover={false} style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={14} color="#F59E0B" />
          <span style={{ ...sectionTitleStyle, marginBottom: 0 }}>Victim Alert Feed</span>
        </div>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 10,
          color: 'var(--text-muted)', letterSpacing: '0.3px',
        }}>
          {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>

      {alerts.length === 0 ? (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', padding: '48px 24px', gap: 12,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Shield size={18} color="#10B981" />
          </div>
          <span style={{ ...monoSmall, color: 'var(--text-muted)' }}>
            // no victim alerts detected
          </span>
        </div>
      ) : (
        <div style={{ maxHeight: 520, overflowY: 'auto' }}>
          <table style={{
            width: '100%', borderCollapse: 'collapse',
            fontFamily: 'var(--font-mono)', fontSize: 11,
          }}>
            <thead>
              <tr style={{
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                position: 'sticky', top: 0,
                background: 'rgba(15,20,33,0.95)',
                backdropFilter: 'blur(10px)',
              }}>
                {['Sender', 'Receiver', 'Victim', 'Mule', 'Combined', 'Recommendation', 'Status'].map(h => (
                  <th key={h} style={{
                    padding: '8px 10px', textAlign: 'left',
                    fontSize: 9, letterSpacing: '1px', textTransform: 'uppercase',
                    color: 'var(--text-muted)', fontWeight: 700,
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {alerts.map((alert, idx) => {
                  const isSelected = selectedId === alert.evaluation_id;
                  return (
                    <motion.tr
                      key={alert.evaluation_id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: Math.min(idx * 0.02, 0.4) }}
                      onClick={() => onSelect(alert)}
                      style={{
                        cursor: 'pointer',
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        background: isSelected
                          ? 'rgba(59,130,246,0.08)'
                          : idx % 2 === 0
                            ? 'transparent'
                            : 'rgba(255,255,255,0.015)',
                        transition: 'background 0.15s',
                      }}
                      whileHover={{ background: 'rgba(255,255,255,0.04)' }}
                    >
                      <td style={{ padding: '8px 10px', color: 'var(--accent-cyan)' }}>
                        {alert.sender_account}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--text-secondary)' }}>
                        {alert.receiver_account}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <RiskBar value={alert.sender_victim_score} />
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <RiskBar value={alert.receiver_mule_score} />
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <RiskBar value={alert.combined_risk} />
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <RecommendationBadge recommendation={alert.recommendation} />
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <StatusBadge status={alert.status} />
                      </td>
                    </motion.tr>
                  );
                })}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      )}
    </GlassCard>
  );
}

/* ── Section 2: Transaction Evaluator ── */

function TransactionEvaluator({ onEvaluationResult }) {
  const [form, setForm] = useState({ ...DEFAULT_FORM });
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const updateField = (path, value) => {
    setForm(prev => {
      const keys = path.split('.');
      if (keys.length === 1) {
        return { ...prev, [keys[0]]: value };
      }
      const [group, field] = keys;
      return {
        ...prev,
        [group]: { ...prev[group], [field]: value },
      };
    });
  };

  const handleEvaluate = async (e) => {
    e.preventDefault();
    setEvaluating(true);
    setError(null);
    setResult(null);

    try {
      const res = await apiFetch('/api/v1/scam/evaluate-transaction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || errBody.message || `Request failed (${res.status})`);
      }

      const body = await res.json();
      const data = body?.data || body;
      setResult(data);

      if (onEvaluationResult) {
        onEvaluationResult(data);
      }
    } catch (err) {
      setError(err.message || 'Evaluation failed');
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {/* Evaluation Form */}
      <GlassCard hover={false}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Eye size={14} color="var(--accent-cyan)" />
          <span style={{ ...sectionTitleStyle, marginBottom: 0 }}>Transaction Evaluator</span>
        </div>

        <form onSubmit={handleEvaluate}>
          {/* Sender fields */}
          <div style={{
            padding: '10px 12px', marginBottom: 12,
            background: 'rgba(255,255,255,0.02)', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--accent-cyan)',
              letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 10, fontWeight: 700,
            }}>
              Sender
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <FormField label="Account ID">
                <input
                  style={inputStyle}
                  value={form.sender.account_id}
                  onChange={e => updateField('sender.account_id', e.target.value)}
                />
              </FormField>
              <FormField label="Age">
                <input
                  style={inputStyle}
                  type="number"
                  value={form.sender.age}
                  onChange={e => updateField('sender.age', parseInt(e.target.value, 10) || 0)}
                />
              </FormField>
              <FormField label="Account Age (days)">
                <input
                  style={inputStyle}
                  type="number"
                  value={form.sender.account_age_days}
                  onChange={e => updateField('sender.account_age_days', parseInt(e.target.value, 10) || 0)}
                />
              </FormField>
            </div>
          </div>

          {/* Receiver fields */}
          <div style={{
            padding: '10px 12px', marginBottom: 12,
            background: 'rgba(255,255,255,0.02)', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: '#F59E0B',
              letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 10, fontWeight: 700,
            }}>
              Receiver
            </div>
            <FormField label="Account ID">
              <input
                style={inputStyle}
                value={form.receiver.account_id}
                onChange={e => updateField('receiver.account_id', e.target.value)}
              />
            </FormField>
          </div>

          {/* Transaction fields */}
          <div style={{
            padding: '10px 12px', marginBottom: 12,
            background: 'rgba(255,255,255,0.02)', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--accent-green)',
              letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 10, fontWeight: 700,
            }}>
              Transaction
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <FormField label="Amount">
                <input
                  style={inputStyle}
                  type="number"
                  value={form.transaction.amount}
                  onChange={e => updateField('transaction.amount', parseFloat(e.target.value) || 0)}
                />
              </FormField>
              <FormField label="Channel">
                <input
                  style={inputStyle}
                  value={form.transaction.channel}
                  onChange={e => updateField('transaction.channel', e.target.value)}
                />
              </FormField>
            </div>
            <FormField label="Narration">
              <input
                style={inputStyle}
                value={form.transaction.narration}
                onChange={e => updateField('transaction.narration', e.target.value)}
              />
            </FormField>
          </div>

          {/* Session context */}
          <div style={{
            padding: '10px 12px', marginBottom: 12,
            background: 'rgba(255,255,255,0.02)', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: '#A78BFA',
              letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 10, fontWeight: 700,
            }}>
              Session Context
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <FormField label="Active Call">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 4 }}>
                  <input
                    type="checkbox"
                    checked={form.session_context.active_call}
                    onChange={e => updateField('session_context.active_call', e.target.checked)}
                    style={{ accentColor: 'var(--accent-cyan)' }}
                  />
                  <Phone size={12} color={form.session_context.active_call ? '#EF4444' : 'var(--text-muted)'} />
                  <span style={{
                    ...monoSmall, fontSize: 10,
                    color: form.session_context.active_call ? '#EF4444' : 'var(--text-muted)',
                  }}>
                    {form.session_context.active_call ? 'On call' : 'No call'}
                  </span>
                </div>
              </FormField>
              <FormField label="App Switches">
                <input
                  style={inputStyle}
                  type="number"
                  min="0"
                  value={form.session_context.app_switches}
                  onChange={e => updateField('session_context.app_switches', parseInt(e.target.value, 10) || 0)}
                />
              </FormField>
            </div>
          </div>

          {/* Receiver mule score slider */}
          <div style={{
            padding: '10px 12px', marginBottom: 16,
            background: 'rgba(255,255,255,0.02)', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8,
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, color: '#EF4444',
                letterSpacing: '1.5px', textTransform: 'uppercase', fontWeight: 700,
              }}>
                Receiver Mule Score
              </span>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
                color: form.receiver_mule_score >= 0.7 ? '#EF4444'
                  : form.receiver_mule_score >= 0.4 ? '#F59E0B' : '#10B981',
              }}>
                {form.receiver_mule_score.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={form.receiver_mule_score}
              onChange={e => updateField('receiver_mule_score', parseFloat(e.target.value))}
              style={{
                width: '100%', height: 4,
                accentColor: form.receiver_mule_score >= 0.7 ? '#EF4444'
                  : form.receiver_mule_score >= 0.4 ? '#F59E0B' : '#10B981',
              }}
            />
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-faint)',
              marginTop: 4,
            }}>
              <span>0.0 Safe</span>
              <span>1.0 Mule</span>
            </div>
          </div>

          {/* Submit */}
          <motion.button
            type="submit"
            disabled={evaluating}
            style={{
              width: '100%', padding: '10px 16px',
              background: evaluating ? 'rgba(59,130,246,0.1)' : 'rgba(59,130,246,0.15)',
              border: '1px solid rgba(59,130,246,0.3)',
              borderRadius: 6, color: '#3B82F6',
              fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
              letterSpacing: '1px', textTransform: 'uppercase',
              cursor: evaluating ? 'wait' : 'pointer',
              transition: 'all 0.2s',
            }}
            whileHover={evaluating ? {} : { background: 'rgba(59,130,246,0.25)', scale: 1.01 }}
            whileTap={evaluating ? {} : { scale: 0.98 }}
          >
            {evaluating ? 'Evaluating...' : 'Evaluate Transaction'}
          </motion.button>
        </form>
      </GlassCard>

      {/* Evaluation Result */}
      <GlassCard hover={false}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Shield size={14} color="var(--accent-green)" />
          <span style={{ ...sectionTitleStyle, marginBottom: 0 }}>Evaluation Result</span>
        </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              padding: '12px 14px', borderRadius: 6,
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
              color: '#EF4444',
              fontFamily: 'var(--font-mono)', fontSize: 11,
              marginBottom: 12,
            }}
          >
            {error}
          </motion.div>
        )}

        {!result && !error && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '60px 24px', gap: 12,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: '50%',
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Eye size={18} color="var(--text-faint)" />
            </div>
            <span style={{ ...monoSmall, color: 'var(--text-faint)', textAlign: 'center' }}>
              // submit a transaction to see results
            </span>
          </div>
        )}

        {result && !error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            {/* Recommendation headline */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 16, padding: '10px 12px',
              background: (RECOMMENDATION_COLORS[result.recommendation] || RECOMMENDATION_COLORS.ALLOW).bg,
              border: `1px solid ${(RECOMMENDATION_COLORS[result.recommendation] || RECOMMENDATION_COLORS.ALLOW).border}`,
              borderRadius: 6,
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                color: (RECOMMENDATION_COLORS[result.recommendation] || RECOMMENDATION_COLORS.ALLOW).text,
                letterSpacing: '1px',
              }}>
                {result.recommendation}
              </span>
              {result.evaluation_id && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                  {result.evaluation_id}
                </span>
              )}
            </div>

            {/* Intervention message */}
            {result.intervention_message && (
              <div style={{
                padding: '10px 12px', marginBottom: 14,
                background: 'rgba(245,158,11,0.06)',
                border: '1px solid rgba(245,158,11,0.15)',
                borderRadius: 6, borderLeft: '3px solid #F59E0B',
              }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9, color: '#F59E0B',
                  letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 4, fontWeight: 700,
                }}>
                  Intervention Message
                </div>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11,
                  color: 'var(--text-secondary)', lineHeight: 1.5,
                }}>
                  {result.intervention_message}
                </div>
              </div>
            )}

            {/* Risk breakdown */}
            <div style={{ marginBottom: 14 }}>
              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
                letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8, fontWeight: 700,
              }}>
                Risk Breakdown
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {result.sender_risk !== undefined && (
                  <RiskBar value={result.sender_risk} label="Sender" />
                )}
                {result.sender_victim_score !== undefined && (
                  <RiskBar value={result.sender_victim_score} label="Victim" />
                )}
                {result.receiver_risk !== undefined && (
                  <RiskBar value={result.receiver_risk} label="Receiver" />
                )}
                {result.receiver_mule_score !== undefined && (
                  <RiskBar value={result.receiver_mule_score} label="Mule" />
                )}
                {result.combined_risk !== undefined && (
                  <RiskBar value={result.combined_risk} label="Combined" />
                )}
              </div>
            </div>

            {/* Sender risk detail */}
            {result.sender_risk_breakdown && (
              <div style={{ marginBottom: 14 }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--accent-cyan)',
                  letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8, fontWeight: 700,
                }}>
                  Sender Risk Detail
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {Object.entries(result.sender_risk_breakdown).map(([key, val]) => (
                    <div key={key} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '4px 8px', borderRadius: 4,
                      background: 'rgba(255,255,255,0.02)',
                    }}>
                      <span style={{ ...monoSmall, color: 'var(--text-muted)', fontSize: 10 }}>
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span style={{ ...monoSmall, color: 'var(--text-primary)', fontWeight: 600 }}>
                        {typeof val === 'number' ? val.toFixed(3) : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Reason codes */}
            {result.reason_codes && result.reason_codes.length > 0 && (
              <div>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
                  letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8, fontWeight: 700,
                }}>
                  Reason Codes
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {result.reason_codes.map((code, i) => (
                    <span key={i} style={{
                      padding: '3px 8px', borderRadius: 4,
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      fontFamily: 'var(--font-mono)', fontSize: 10,
                      color: 'var(--text-secondary)', letterSpacing: '0.3px',
                    }}>
                      {code}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </GlassCard>
    </div>
  );
}

/* ── Section 3: Intervention Actions ── */

function InterventionPanel({ selectedAlert, onActionComplete }) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(null);
  const [actionResult, setActionResult] = useState(null);

  const evaluationId = selectedAlert?.evaluation_id;

  const handleAction = async (action) => {
    if (!evaluationId) return;
    setSubmitting(action);
    setActionResult(null);

    try {
      const res = await apiFetch(`/api/v1/scam/intervene/${evaluationId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, reason: reason || `${action} by analyst` }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || errBody.message || `Action failed (${res.status})`);
      }

      const body = await res.json();
      const data = body?.data || body;
      setActionResult({ success: true, action, data });

      if (onActionComplete) {
        onActionComplete(evaluationId, action);
      }
    } catch (err) {
      setActionResult({ success: false, action, error: err.message });
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <GlassCard hover={false}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Shield size={14} color="#A78BFA" />
        <span style={{ ...sectionTitleStyle, marginBottom: 0 }}>Intervention Actions</span>
      </div>

      {!evaluationId ? (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', padding: '32px 24px', gap: 10,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Shield size={16} color="var(--text-faint)" />
          </div>
          <span style={{ ...monoSmall, color: 'var(--text-faint)', textAlign: 'center' }}>
            // select an alert or run an evaluation to take action
          </span>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          {/* Selected alert summary */}
          <div style={{
            padding: '10px 12px', marginBottom: 14,
            background: 'rgba(59,130,246,0.06)',
            border: '1px solid rgba(59,130,246,0.15)',
            borderRadius: 6,
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6,
            }}>
              <span style={{ ...monoSmall, color: 'var(--accent-cyan)', fontWeight: 600, fontSize: 10 }}>
                {evaluationId}
              </span>
              {selectedAlert.recommendation && (
                <RecommendationBadge recommendation={selectedAlert.recommendation} />
              )}
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              {selectedAlert.sender_account && (
                <span style={{ ...monoSmall, color: 'var(--text-muted)', fontSize: 10 }}>
                  Sender: {selectedAlert.sender_account}
                </span>
              )}
              {selectedAlert.receiver_account && (
                <span style={{ ...monoSmall, color: 'var(--text-muted)', fontSize: 10 }}>
                  Receiver: {selectedAlert.receiver_account}
                </span>
              )}
            </div>
          </div>

          {/* Reason input */}
          <FormField label="Reason for action">
            <input
              style={inputStyle}
              placeholder="Enter reason for intervention..."
              value={reason}
              onChange={e => setReason(e.target.value)}
            />
          </FormField>

          {/* Action buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
            {INTERVENTION_ACTIONS.map(action => {
              const style = ACTION_STYLES[action];
              const isActive = submitting === action;
              return (
                <motion.button
                  key={action}
                  onClick={() => handleAction(action)}
                  disabled={submitting !== null}
                  style={{
                    padding: '10px 14px',
                    background: style.bg,
                    border: `1px solid ${style.border}40`,
                    borderRadius: 6,
                    color: style.text,
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: '1px',
                    textTransform: 'uppercase',
                    cursor: submitting ? 'wait' : 'pointer',
                    opacity: submitting && !isActive ? 0.4 : 1,
                    transition: 'all 0.2s',
                  }}
                  whileHover={submitting ? {} : {
                    background: `${style.bg.replace('0.15', '0.3')}`,
                    borderColor: style.border,
                    scale: 1.02,
                  }}
                  whileTap={submitting ? {} : { scale: 0.96 }}
                >
                  {isActive ? `${action}ing...` : action}
                </motion.button>
              );
            })}
          </div>

          {/* Action result */}
          <AnimatePresence>
            {actionResult && (
              <motion.div
                initial={{ opacity: 0, y: 8, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -4, height: 0 }}
                style={{
                  marginTop: 12, padding: '10px 12px', borderRadius: 6,
                  background: actionResult.success
                    ? 'rgba(16,185,129,0.08)'
                    : 'rgba(239,68,68,0.08)',
                  border: `1px solid ${actionResult.success
                    ? 'rgba(16,185,129,0.2)'
                    : 'rgba(239,68,68,0.2)'}`,
                }}
              >
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11,
                  color: actionResult.success ? '#10B981' : '#EF4444',
                  fontWeight: 600, marginBottom: 2,
                }}>
                  {actionResult.success
                    ? `${actionResult.action} applied successfully`
                    : `Failed to apply ${actionResult.action}`}
                </div>
                {actionResult.error && (
                  <div style={{ ...monoSmall, color: 'var(--text-muted)', fontSize: 10 }}>
                    {actionResult.error}
                  </div>
                )}
                {actionResult.success && actionResult.data?.new_status && (
                  <div style={{ ...monoSmall, color: 'var(--text-muted)', fontSize: 10 }}>
                    Status: {actionResult.data.new_status}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </GlassCard>
  );
}

/* ── Main Page ── */

export default function ScamDetectionPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState(null);

  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = () => {
    setLoading(true);
    apiFetch('/api/v1/scam/victim-alerts?min_score=0.0&limit=50')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAlerts(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(err => {
        console.error('[ScamDetection] Failed to load victim alerts:', err);
        setAlerts([]);
        setLoading(false);
      });
  };

  const handleAlertSelect = (alert) => {
    setSelectedAlert(prev =>
      prev?.evaluation_id === alert.evaluation_id ? null : alert
    );
  };

  const handleEvaluationResult = (result) => {
    if (result?.evaluation_id) {
      setSelectedAlert({
        evaluation_id: result.evaluation_id,
        recommendation: result.recommendation,
        sender_account: result.sender_account,
        receiver_account: result.receiver_account,
        sender_victim_score: result.sender_victim_score,
        receiver_mule_score: result.receiver_mule_score,
        combined_risk: result.combined_risk,
        status: 'PENDING',
      });
    }
  };

  const handleActionComplete = (evaluationId, action) => {
    setAlerts(prev =>
      prev.map(a =>
        a.evaluation_id === evaluationId
          ? { ...a, status: action === 'BLOCK' ? 'BLOCKED' : action === 'RELEASE' ? 'RELEASED' : action === 'WARN' ? 'WARNED' : 'DELAYED' }
          : a
      )
    );
    fetchAlerts();
  };

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1440, margin: '0 auto' }}>

      {/* Page Header */}
      <AnimateIn>
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          style={{ marginBottom: 24 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <h1 className="gradient-text" style={{
              fontFamily: 'var(--font-display)',
              fontSize: 26,
              fontWeight: 800,
              letterSpacing: '-0.5px',
              margin: 0,
            }}>
              Scam Detection
            </h1>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: 5,
              padding: '2px 8px',
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: '#EF4444',
                animation: 'emeraldPulse 2s ease-in-out infinite',
              }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: '#EF4444',
                letterSpacing: '1px',
                textTransform: 'uppercase',
                fontWeight: 700,
              }}>Active</span>
            </div>
          </div>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--text-muted)',
            letterSpacing: '0.3px',
            margin: 0,
          }}>
            <span style={{ color: 'rgba(239,68,68,0.6)' }}>//</span>
            {' '}Dual-sided risk engine
            <span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span>
            Victim detection
            <span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span>
            Real-time intervention
          </p>
        </motion.div>
      </AnimateIn>

      {/* Section 1: Victim Alert Feed */}
      <AnimateIn delay={0.05}>
        <div style={{ marginBottom: 24 }}>
          <VictimAlertFeed
            alerts={alerts}
            loading={loading}
            onSelect={handleAlertSelect}
            selectedId={selectedAlert?.evaluation_id}
          />
        </div>
      </AnimateIn>

      {/* Section 2: Transaction Evaluator */}
      <AnimateIn delay={0.1}>
        <div style={{ marginBottom: 24 }}>
          <TransactionEvaluator onEvaluationResult={handleEvaluationResult} />
        </div>
      </AnimateIn>

      {/* Section 3: Intervention Actions */}
      <AnimateIn delay={0.15}>
        <InterventionPanel
          selectedAlert={selectedAlert}
          onActionComplete={handleActionComplete}
        />
      </AnimateIn>
    </div>
  );
}
