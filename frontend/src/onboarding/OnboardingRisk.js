import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { GlassCard, GlassCardMetric } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';
import { apiFetch } from '../auth/api';

const RISK_COLORS = {
  LOW: 'var(--accent-green)',
  MEDIUM: 'var(--accent-amber)',
  HIGH: 'var(--accent-red)',
  CRITICAL: 'var(--critical)',
};

const RISK_BG = {
  LOW: 'rgba(22,199,132,0.10)',
  MEDIUM: 'rgba(255,176,32,0.10)',
  HIGH: 'rgba(255,92,122,0.10)',
  CRITICAL: 'rgba(255,92,122,0.15)',
};

const DEFAULT_FORM = {
  account_id: '',
  account_age_days: 5,
  kyc_completeness: 0.4,
  doc_verification_seconds: 15,
  device_overlap_count: 2,
  ip_geolocation_mismatch: true,
  phone_age_days: 10,
  email_age_days: 3,
  address_verified: false,
  selfie_confidence: 0.65,
  application_velocity_count: 3,
  similar_name_count: 1,
  high_risk_geography: false,
  application_hour: 2,
};

function RiskBar({ score, level }) {
  const pct = Math.round(score * 100);
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
          Risk Score
        </span>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700,
          color: RISK_COLORS[level] || 'var(--text-primary)',
        }}>
          {pct}%
        </span>
      </div>
      <div style={{ height: 10, background: 'var(--border)', borderRadius: 5, overflow: 'hidden', position: 'relative' }}>
        {/* Gradient track */}
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.15,
          background: 'linear-gradient(90deg, #16C784 0%, #FFB020 40%, #FF5C7A 70%, #FF5C7A 100%)',
          borderRadius: 5,
        }} />
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
          style={{
            height: '100%',
            background: `linear-gradient(90deg, #16C784 0%, #FFB020 40%, #FF5C7A 70%, #FF5C7A 100%)`,
            borderRadius: 5,
            position: 'relative',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
        <span>LOW</span><span>MEDIUM</span><span>HIGH</span><span>CRITICAL</span>
      </div>
    </div>
  );
}

export default function OnboardingRisk() {
  const [form, setForm] = useState({ ...DEFAULT_FORM });
  const [result, setResult] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiExplanation, setAiExplanation] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);

  // Load stats and recent assessments
  useEffect(() => {
    apiFetch('/api/v1/onboarding/stats')
      .then(r => r.json())
      .then(body => setStats(body?.data || body))
      .catch(err => console.error('[Onboarding] Stats fetch failed:', err));

    apiFetch('/api/v1/onboarding/assessments?limit=10')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAssessments(data.assessments || []);
      })
      .catch(err => console.error('[Onboarding] Assessments fetch failed:', err));
  }, []);

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/onboarding/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const body = await res.json();
      const data = body?.data || body;
      setResult(data);
      // Refresh assessments & stats
      setAssessments(prev => [data, ...prev].slice(0, 10));
      apiFetch('/api/v1/onboarding/stats')
        .then(r => r.json())
        .then(body2 => setStats(body2?.data || body2))
        .catch(err => console.error('[Onboarding] Stats refresh failed:', err));
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleExplainWithAI = async () => {
    if (!result || result.error) return;
    setAiLoading(true);
    setAiExplanation(null);
    try {
      const res = await apiFetch('/api/v1/genai/explain-onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assessment_data: result }),
      });
      const body = await res.json();
      const data = body?.data || body;
      setAiExplanation(data.message || data);
    } catch {
      setAiExplanation('Failed to generate AI explanation. Please try again.');
    } finally {
      setAiLoading(false);
    }
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    outline: 'none',
    transition: 'border-color 0.2s',
    boxSizing: 'border-box',
  };

  const labelStyle = {
    display: 'block',
    fontSize: 10,
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    marginBottom: 4,
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
  };

  return (
    <div style={{ padding: '32px 32px 48px', maxWidth: 1400, margin: '0 auto' }}>

      {/* Page Header */}
      <AnimateIn>
        <div style={{ marginBottom: 28 }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--accent-cyan)',
            letterSpacing: '3px', textTransform: 'uppercase', marginBottom: 8, opacity: 0.8,
          }}>
            IOB · Onboarding Risk Assessment
          </div>
          <h1 style={{
            fontFamily: 'var(--font-sans)', fontSize: 28, fontWeight: 700,
            letterSpacing: '-1px', color: 'var(--text-primary)', margin: 0,
          }}>
            Onboarding Risk Scorer
          </h1>
          <p style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)',
            marginTop: 6, letterSpacing: '0.3px',
          }}>
            // Assess mule risk at point of account onboarding — 14-signal scoring engine
          </p>
        </div>
      </AnimateIn>

      {/* Stats Cards */}
      <StaggerContainer style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        <StaggerItem>
          <GlassCardMetric
            label="Total Assessed"
            value={stats?.total_assessed || 0}
            color="var(--accent-cyan)"
          />
        </StaggerItem>
        <StaggerItem>
          <GlassCardMetric
            label="High-Risk Flagged"
            value={stats?.high_risk_flagged || 0}
            color="var(--critical)"
          />
        </StaggerItem>
        <StaggerItem>
          <GlassCardMetric
            label="Auto-Blocked"
            value={stats?.auto_blocked || 0}
            color="var(--accent-amber)"
          />
        </StaggerItem>
        <StaggerItem>
          <GlassCardMetric
            label="Pass Rate"
            value={`${((stats?.pass_rate || 1) * 100).toFixed(0)}%`}
            color="var(--accent-green)"
          />
        </StaggerItem>
      </StaggerContainer>

      {/* Main Grid: Form + Result */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>

        {/* Assessment Form */}
        <AnimateIn delay={0.1}>
          <GlassCard className="p-5" hover={false}>
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
              letterSpacing: '2px', textTransform: 'uppercase', marginBottom: 16,
            }}>
              New Assessment
            </p>
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {/* Account ID */}
                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={labelStyle}>Account ID</label>
                  <input
                    style={inputStyle}
                    value={form.account_id}
                    onChange={e => handleChange('account_id', e.target.value)}
                    placeholder="e.g. AC999"
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Account Age */}
                <div>
                  <label style={labelStyle}>Account Age (days)</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.account_age_days}
                    onChange={e => handleChange('account_age_days', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* KYC Completeness */}
                <div>
                  <label style={labelStyle}>KYC Completeness (0-1)</label>
                  <input
                    type="number" step="0.01" min={0} max={1} style={inputStyle}
                    value={form.kyc_completeness}
                    onChange={e => handleChange('kyc_completeness', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Doc Verification Speed */}
                <div>
                  <label style={labelStyle}>Doc Verification (sec)</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.doc_verification_seconds}
                    onChange={e => handleChange('doc_verification_seconds', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Device Overlap */}
                <div>
                  <label style={labelStyle}>Device Overlap Count</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.device_overlap_count}
                    onChange={e => handleChange('device_overlap_count', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Phone Age */}
                <div>
                  <label style={labelStyle}>Phone Number Age (days)</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.phone_age_days}
                    onChange={e => handleChange('phone_age_days', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Email Age */}
                <div>
                  <label style={labelStyle}>Email Age (days)</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.email_age_days}
                    onChange={e => handleChange('email_age_days', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Selfie Confidence */}
                <div>
                  <label style={labelStyle}>Selfie Match (0-1)</label>
                  <input
                    type="number" step="0.01" min={0} max={1} style={inputStyle}
                    value={form.selfie_confidence}
                    onChange={e => handleChange('selfie_confidence', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Application Velocity */}
                <div>
                  <label style={labelStyle}>App Velocity Count</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.application_velocity_count}
                    onChange={e => handleChange('application_velocity_count', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Similar Name Count */}
                <div>
                  <label style={labelStyle}>Similar Name Count</label>
                  <input
                    type="number" style={inputStyle} min={0}
                    value={form.similar_name_count}
                    onChange={e => handleChange('similar_name_count', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Application Hour */}
                <div>
                  <label style={labelStyle}>Application Hour (0-23)</label>
                  <input
                    type="number" style={inputStyle} min={0} max={23}
                    value={form.application_hour}
                    onChange={e => handleChange('application_hour', Number(e.target.value))}
                    onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>

                {/* Toggles row */}
                <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 4 }}>
                  {[
                    { field: 'ip_geolocation_mismatch', label: 'IP Mismatch' },
                    { field: 'address_verified', label: 'Address Verified' },
                    { field: 'high_risk_geography', label: 'High-Risk Geography' },
                  ].map(({ field, label }) => (
                    <label key={field} style={{
                      display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
                      fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                    }}>
                      <input
                        type="checkbox"
                        checked={form[field]}
                        onChange={e => handleChange(field, e.target.checked)}
                        style={{ accentColor: '#3EE7FF' }}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>

              <motion.button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{
                  width: '100%', marginTop: 16, padding: '10px',
                  fontSize: 12, fontWeight: 600, letterSpacing: '0.5px',
                }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
              >
                {loading ? 'Assessing...' : 'Assess Onboarding Risk'}
              </motion.button>
            </form>
          </GlassCard>
        </AnimateIn>

        {/* Risk Result */}
        <AnimateIn delay={0.15}>
          <GlassCard className="p-5" hover={false} style={{ minHeight: 400 }}>
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
              letterSpacing: '2px', textTransform: 'uppercase', marginBottom: 16,
            }}>
              Assessment Result
            </p>

            {result && !result.error ? (
              <div>
                {/* Risk bar */}
                <RiskBar score={result.risk_score} level={result.risk_level} />

                {/* Risk level badge */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
                  padding: '12px 16px', borderRadius: 8,
                  background: RISK_BG[result.risk_level] || 'var(--bg-elevated)',
                  border: `1px solid ${RISK_COLORS[result.risk_level]}40`,
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                    color: RISK_COLORS[result.risk_level], letterSpacing: '1px',
                  }}>
                    {result.risk_level}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    {result.recommendation}
                  </span>
                </div>

                {/* Assessment metadata */}
                <div style={{
                  display: 'flex', gap: 16, marginBottom: 16, fontSize: 10,
                  fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                }}>
                  <span>ID: {result.assessment_id}</span>
                  <span>Account: {result.account_id}</span>
                </div>

                {/* Reason codes */}
                {result.reason_codes?.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <p style={{
                      fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                      letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8,
                    }}>
                      Triggered Reason Codes
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {result.reason_codes.map((code, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.05 }}
                          style={{
                            fontSize: 11, fontFamily: 'var(--font-mono)',
                            color: 'var(--text-secondary)', padding: '5px 10px',
                            background: 'var(--bg-elevated)', borderRadius: 4,
                            borderLeft: `2px solid ${RISK_COLORS[result.risk_level]}`,
                          }}
                        >
                          {code}
                        </motion.div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Signal breakdown */}
                <p style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                  letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8,
                }}>
                  Signal Breakdown
                </p>
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {['Signal', 'Score', 'Weight', 'Weighted'].map(h => (
                          <th key={h} style={{
                            textAlign: 'left', padding: '4px 8px', fontSize: 9,
                            fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                            borderBottom: '1px solid var(--border)', letterSpacing: '1px',
                            textTransform: 'uppercase',
                          }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.signals?.map((sig, i) => (
                        <tr key={sig.signal} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                            {sig.signal.replace(/_/g, ' ')}
                          </td>
                          <td style={{
                            padding: '4px 8px', fontSize: 11, fontFamily: 'var(--font-mono)',
                            color: sig.score >= 0.5 ? 'var(--critical)' : sig.score >= 0.3 ? 'var(--accent-amber)' : 'var(--accent-green)',
                            fontWeight: 600,
                          }}>
                            {sig.score.toFixed(2)}
                          </td>
                          <td style={{ padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            {sig.weight}
                          </td>
                          <td style={{ padding: '4px 8px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                            {sig.weighted.toFixed(4)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Explain with AI button */}
                <div style={{ marginTop: 16 }}>
                  <motion.button
                    className="btn btn-primary"
                    onClick={handleExplainWithAI}
                    disabled={aiLoading}
                    style={{
                      width: '100%', padding: '8px',
                      fontSize: 11, fontWeight: 600, letterSpacing: '0.5px',
                      background: aiExplanation ? 'rgba(62,231,255,0.08)' : undefined,
                      borderColor: 'var(--accent-cyan)',
                    }}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {aiLoading ? 'Analyzing...' : aiExplanation ? 'Refresh AI Explanation' : 'Explain with AI'}
                  </motion.button>
                </div>

                {/* AI Explanation */}
                {aiExplanation && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      marginTop: 12, padding: '12px 16px',
                      background: 'rgba(62,231,255,0.04)',
                      border: '1px solid rgba(62,231,255,0.15)',
                      borderRadius: 8,
                    }}
                  >
                    <p style={{
                      fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)',
                      letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8,
                    }}>
                      AI Explanation
                    </p>
                    <p style={{
                      fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                      lineHeight: 1.7, whiteSpace: 'pre-wrap',
                    }}>
                      {typeof aiExplanation === 'string' ? aiExplanation : JSON.stringify(aiExplanation, null, 2)}
                    </p>
                  </motion.div>
                )}
              </div>
            ) : result?.error ? (
              <div style={{
                padding: 16, borderRadius: 8, background: 'rgba(255,92,122,0.08)',
                border: '1px solid rgba(255,92,122,0.2)', color: 'var(--critical)',
                fontSize: 12, fontFamily: 'var(--font-mono)',
              }}>
                {result.error}
              </div>
            ) : (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', height: '80%', color: 'var(--text-muted)',
              }}>
                <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.12 }}>⬡</div>
                <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                  Submit an assessment to see results
                </p>
              </div>
            )}
          </GlassCard>
        </AnimateIn>
      </div>

      {/* Recent Assessments Table */}
      {assessments.length > 0 && (
        <AnimateIn delay={0.2}>
          <GlassCard style={{ padding: 0, overflow: 'hidden' }} hover={false}>
            <div style={{
              padding: '14px 20px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
                letterSpacing: '2px', textTransform: 'uppercase',
              }}>
                Recent Assessments · {assessments.length} results
              </span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Assessment ID</th>
                  <th>Account</th>
                  <th>Risk Score</th>
                  <th>Risk Level</th>
                  <th>Signals</th>
                  <th>Recommendation</th>
                  <th>Assessed At</th>
                </tr>
              </thead>
              <tbody>
                {assessments.map((a, idx) => (
                  <motion.tr
                    key={a.assessment_id || idx}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.03 }}
                  >
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                      {String(idx + 1).padStart(2, '0')}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-cyan)' }}>
                      {a.assessment_id}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                      {a.account_id}
                    </td>
                    <td>
                      <div className="risk-bar">
                        <div className="risk-track">
                          <motion.div
                            className={`risk-fill ${a.risk_level === 'CRITICAL' ? 'critical' : a.risk_level === 'HIGH' ? 'high' : 'medium'}`}
                            initial={{ width: 0 }}
                            animate={{ width: `${a.risk_score * 100}%` }}
                            transition={{ duration: 0.6 }}
                          />
                        </div>
                        <span className="risk-val">{(a.risk_score * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                        color: RISK_COLORS[a.risk_level], background: RISK_BG[a.risk_level],
                        padding: '2px 8px', borderRadius: 4, letterSpacing: '0.5px',
                      }}>
                        {a.risk_level}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                      {a.reason_codes?.length || 0} triggered
                    </td>
                    <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', maxWidth: 180 }}>
                      {a.recommendation?.split('—')[0]?.trim()}
                    </td>
                    <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {a.assessed_at ? new Date(a.assessed_at).toLocaleTimeString() : '-'}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </AnimateIn>
      )}
    </div>
  );
}
