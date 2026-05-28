import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { Smartphone, CreditCard, Gamepad2, ShieldCheck } from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

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

const sectionTitleStyle = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  color: 'var(--text-muted)',
  letterSpacing: '2px',
  textTransform: 'uppercase',
  marginBottom: 16,
};

const RISK_COLORS = {
  VERY_HIGH: '#ef4444',
  HIGH: '#f59e0b',
  MEDIUM: '#eab308',
  CLEAN: '#22c55e',
  UNKNOWN: '#6b7280',
};

const TABS = [
  { key: 'fri', label: 'FRI Lookup', icon: Smartphone },
  { key: 'jandhan', label: 'Jan Dhan', icon: CreditCard },
  { key: 'crypto', label: 'Crypto/Gaming', icon: Gamepad2 },
  { key: 'upi', label: 'UPI Compliance', icon: ShieldCheck },
];

/* ------------------------------------------------------------------ */
/*  Small reusable components                                          */
/* ------------------------------------------------------------------ */

function FormField({ label, children }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

function FormInput({ label, type = 'text', value, onChange, placeholder, ...rest }) {
  return (
    <FormField label={label}>
      <input
        type={type}
        style={inputStyle}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        onFocus={e => { e.target.style.borderColor = 'var(--accent-cyan)'; }}
        onBlur={e => { e.target.style.borderColor = 'var(--border)'; }}
        {...rest}
      />
    </FormField>
  );
}

function SubmitButton({ loading, label, loadingLabel }) {
  return (
    <motion.button
      type="submit"
      disabled={loading}
      className="btn btn-primary"
      style={{
        width: '100%',
        marginTop: 16,
        padding: '10px',
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: '0.5px',
      }}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.98 }}
    >
      {loading ? loadingLabel : label}
    </motion.button>
  );
}

function ResultRow({ label, value, color }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <span style={{
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}>
        {label}
      </span>
      <span style={{
        fontSize: 13,
        fontFamily: 'var(--font-mono)',
        fontWeight: 600,
        color: color || 'var(--text-primary)',
      }}>
        {value}
      </span>
    </div>
  );
}

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div style={{
      padding: '10px 14px',
      background: 'rgba(239, 68, 68, 0.1)',
      border: '1px solid rgba(239, 68, 68, 0.3)',
      borderRadius: 6,
      color: '#ef4444',
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      marginTop: 12,
    }}>
      {message}
    </div>
  );
}

function ReasonCodeList({ codes }) {
  if (!codes || codes.length === 0) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <span style={{ ...labelStyle, marginBottom: 6 }}>Reason Codes</span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
        {codes.map((code, i) => (
          <span
            key={i}
            style={{
              padding: '3px 8px',
              background: 'rgba(62, 231, 255, 0.08)',
              border: '1px solid rgba(62, 231, 255, 0.2)',
              borderRadius: 4,
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--accent-cyan)',
            }}
          >
            {code}
          </span>
        ))}
      </div>
    </div>
  );
}

function ScoreBadge({ score, label }) {
  const pct = typeof score === 'number' ? (score * 100).toFixed(0) : score;
  const numVal = typeof score === 'number' ? score : parseFloat(score) || 0;
  const color = numVal >= 0.7
    ? '#ef4444'
    : numVal >= 0.4
      ? '#f59e0b'
      : '#22c55e';

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 28,
        fontWeight: 700,
        color,
        lineHeight: 1,
      }}>
        {pct}%
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: 'var(--text-muted)',
        marginTop: 6,
        letterSpacing: '1.5px',
        textTransform: 'uppercase',
      }}>
        {label}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Section 1: FRI Mobile Risk Lookup                                  */
/* ------------------------------------------------------------------ */

function FRILookupSection() {
  const [mobile, setMobile] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isValid = /^\d{10}$/.test(mobile);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isValid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch(`/api/v1/india/fri/${mobile}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || body?.message || `Request failed (${res.status})`);
      }
      const body = await res.json();
      setResult(body?.data || body);
    } catch (err) {
      setError(err.message || 'Failed to fetch FRI data');
    } finally {
      setLoading(false);
    }
  };

  const riskColor = result ? (RISK_COLORS[result.risk_level] || RISK_COLORS.UNKNOWN) : null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>FRI Mobile Risk Lookup</p>
        <form onSubmit={handleSubmit}>
          <FormInput
            label="Mobile Number (10 digits)"
            type="tel"
            value={mobile}
            onChange={e => setMobile(e.target.value.replace(/\D/g, '').slice(0, 10))}
            placeholder="9876543210"
            maxLength={10}
          />
          <SubmitButton
            loading={loading}
            label="Check FRI"
            loadingLabel="Checking..."
          />
        </form>
        {!isValid && mobile.length > 0 && (
          <div style={{
            marginTop: 8,
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: 'var(--accent-amber)',
          }}>
            Enter a valid 10-digit mobile number
          </div>
        )}
        <ErrorBanner message={error} />
      </GlassCard>

      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>FRI Result</p>
        {!result && !loading && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 160,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
          }}>
            Enter a mobile number to check
          </div>
        )}
        {loading && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 160,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
          }}>
            <div className="spinner" style={{ marginRight: 8 }} />
            Querying FRI database...
          </div>
        )}
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              marginBottom: 16,
              padding: '12px 16px',
              background: `${riskColor}12`,
              border: `1px solid ${riskColor}40`,
              borderRadius: 8,
            }}>
              <div style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: riskColor,
                boxShadow: `0 0 10px ${riskColor}60`,
                flexShrink: 0,
              }} />
              <div>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 14,
                  fontWeight: 700,
                  color: riskColor,
                }}>
                  {result.risk_level || 'UNKNOWN'}
                </div>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--text-muted)',
                }}>
                  {result.mobile_number}
                </div>
              </div>
              {typeof result.score === 'number' && (
                <div style={{ marginLeft: 'auto' }}>
                  <ScoreBadge score={result.score} label="FRI Score" />
                </div>
              )}
            </div>

            <ResultRow label="Source" value={result.source || '--'} />
            <ResultRow
              label="Citizen Reports"
              value={result.citizen_reports ?? '--'}
              color={result.citizen_reports > 0 ? '#f59e0b' : undefined}
            />
            <ResultRow
              label="NCRP Complaints"
              value={result.ncrp_complaints ?? '--'}
              color={result.ncrp_complaints > 0 ? '#ef4444' : undefined}
            />
            <ResultRow label="Last Updated" value={result.last_updated || '--'} />
          </motion.div>
        )}
      </GlassCard>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Section 2: Jan Dhan Account Assessment                             */
/* ------------------------------------------------------------------ */

const JANDHAN_DEFAULT_PAYLOAD = {
  account: {
    account_id: 'JD001',
    account_type: 'BSBDA',
    is_jan_dhan: true,
    tier_city: 3,
    dormant_days: 120,
    account_age_days: 365,
  },
  transactions: [
    {
      amount: 15000,
      timestamp: '2024-01-15T10:00:00Z',
      channel: 'UPI',
      counterparty_city_tier: 1,
    },
  ],
};

function JanDhanSection() {
  const [form, setForm] = useState({ ...JANDHAN_DEFAULT_PAYLOAD });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const updateAccount = (field, value) => {
    setForm(prev => ({
      ...prev,
      account: { ...prev.account, [field]: value },
    }));
  };

  const updateTransaction = (field, value) => {
    setForm(prev => ({
      ...prev,
      transactions: [{ ...prev.transactions[0], [field]: value }],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch('/api/v1/india/jan-dhan/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || body?.message || `Request failed (${res.status})`);
      }
      const body = await res.json();
      setResult(body?.data || body);
    } catch (err) {
      setError(err.message || 'Assessment failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>Jan Dhan Account Assessment</p>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <FormInput
              label="Account ID"
              value={form.account.account_id}
              onChange={e => updateAccount('account_id', e.target.value)}
            />
            <FormInput
              label="Account Type"
              value={form.account.account_type}
              onChange={e => updateAccount('account_type', e.target.value)}
            />
            <FormField label="Jan Dhan Account">
              <label style={{
                display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
                fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                padding: '8px 0',
              }}>
                <input
                  type="checkbox"
                  checked={form.account.is_jan_dhan}
                  onChange={e => updateAccount('is_jan_dhan', e.target.checked)}
                  style={{ accentColor: '#3EE7FF' }}
                />
                is_jan_dhan
              </label>
            </FormField>
            <FormInput
              label="Tier City"
              type="number"
              min={1}
              max={6}
              value={form.account.tier_city}
              onChange={e => updateAccount('tier_city', Number(e.target.value))}
            />
            <FormInput
              label="Dormant Days"
              type="number"
              min={0}
              value={form.account.dormant_days}
              onChange={e => updateAccount('dormant_days', Number(e.target.value))}
            />
            <FormInput
              label="Account Age (days)"
              type="number"
              min={0}
              value={form.account.account_age_days}
              onChange={e => updateAccount('account_age_days', Number(e.target.value))}
            />
          </div>

          <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <span style={{ ...labelStyle, marginBottom: 8 }}>Transaction</span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormInput
                label="Amount"
                type="number"
                min={0}
                value={form.transactions[0].amount}
                onChange={e => updateTransaction('amount', Number(e.target.value))}
              />
              <FormInput
                label="Channel"
                value={form.transactions[0].channel}
                onChange={e => updateTransaction('channel', e.target.value)}
              />
              <FormInput
                label="Counterparty City Tier"
                type="number"
                min={1}
                max={6}
                value={form.transactions[0].counterparty_city_tier}
                onChange={e => updateTransaction('counterparty_city_tier', Number(e.target.value))}
              />
              <FormInput
                label="Timestamp"
                value={form.transactions[0].timestamp}
                onChange={e => updateTransaction('timestamp', e.target.value)}
              />
            </div>
          </div>

          <SubmitButton loading={loading} label="Assess" loadingLabel="Assessing..." />
        </form>
        <ErrorBanner message={error} />
      </GlassCard>

      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>Assessment Result</p>
        {!result && !loading && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            Submit the form to see results
          </div>
        )}
        {loading && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            <div className="spinner" style={{ marginRight: 8 }} />
            Running assessment...
          </div>
        )}
        {result && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <ScoreBadge
                score={result.composite_score ?? 0}
                label="Composite Score"
              />
            </div>
            <ResultRow
              label="Is BSBDA"
              value={result.is_bsbda ? 'Yes' : 'No'}
              color={result.is_bsbda ? '#f59e0b' : '#22c55e'}
            />
            <ResultRow
              label="Activity Spike Score"
              value={
                typeof result.activity_spike_score === 'number'
                  ? (result.activity_spike_score * 100).toFixed(0) + '%'
                  : '--'
              }
              color={
                result.activity_spike_score >= 0.7
                  ? '#ef4444'
                  : result.activity_spike_score >= 0.4
                    ? '#f59e0b'
                    : '#22c55e'
              }
            />
            <ReasonCodeList codes={result.reason_codes} />
          </motion.div>
        )}
      </GlassCard>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Section 3: Crypto/Gaming Detection                                 */
/* ------------------------------------------------------------------ */

const CRYPTO_DEFAULT_PAYLOAD = {
  account: { account_id: 'CG001' },
  transactions: [
    {
      amount: 50000,
      merchant_id: 'WAZIRX_PAY',
      narration: 'Crypto buy',
      channel: 'UPI',
    },
  ],
};

function CryptoGamingSection() {
  const [form, setForm] = useState({ ...CRYPTO_DEFAULT_PAYLOAD });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const updateAccount = (field, value) => {
    setForm(prev => ({
      ...prev,
      account: { ...prev.account, [field]: value },
    }));
  };

  const updateTransaction = (field, value) => {
    setForm(prev => ({
      ...prev,
      transactions: [{ ...prev.transactions[0], [field]: value }],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch('/api/v1/india/crypto-gaming/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || body?.message || `Request failed (${res.status})`);
      }
      const body = await res.json();
      setResult(body?.data || body);
    } catch (err) {
      setError(err.message || 'Assessment failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>Crypto / Gaming Detection</p>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <FormInput
                label="Account ID"
                value={form.account.account_id}
                onChange={e => updateAccount('account_id', e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <span style={{ ...labelStyle, marginBottom: 8 }}>Transaction</span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormInput
                label="Amount"
                type="number"
                min={0}
                value={form.transactions[0].amount}
                onChange={e => updateTransaction('amount', Number(e.target.value))}
              />
              <FormInput
                label="Merchant ID"
                value={form.transactions[0].merchant_id}
                onChange={e => updateTransaction('merchant_id', e.target.value)}
              />
              <FormInput
                label="Narration"
                value={form.transactions[0].narration}
                onChange={e => updateTransaction('narration', e.target.value)}
              />
              <FormInput
                label="Channel"
                value={form.transactions[0].channel}
                onChange={e => updateTransaction('channel', e.target.value)}
              />
            </div>
          </div>

          <SubmitButton loading={loading} label="Assess" loadingLabel="Assessing..." />
        </form>
        <ErrorBanner message={error} />
      </GlassCard>

      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>Detection Result</p>
        {!result && !loading && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            Submit the form to see results
          </div>
        )}
        {loading && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            <div className="spinner" style={{ marginRight: 8 }} />
            Analyzing transactions...
          </div>
        )}
        {result && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <ScoreBadge
                score={result.composite_score ?? 0}
                label="Composite Score"
              />
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: 10,
              marginBottom: 16,
            }}>
              {[
                { label: 'Crypto', score: result.crypto_score },
                { label: 'Gaming', score: result.gaming_score },
                { label: 'Hawala', score: result.hawala_score },
              ].map(item => {
                const val = typeof item.score === 'number' ? item.score : 0;
                const barColor = val >= 0.7 ? '#ef4444' : val >= 0.4 ? '#f59e0b' : '#22c55e';
                return (
                  <div key={item.label} style={{
                    padding: '10px',
                    background: 'var(--bg-elevated)',
                    borderRadius: 6,
                    textAlign: 'center',
                  }}>
                    <div style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 9,
                      color: 'var(--text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      marginBottom: 6,
                    }}>
                      {item.label}
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 18,
                      fontWeight: 700,
                      color: barColor,
                    }}>
                      {(val * 100).toFixed(0)}%
                    </div>
                  </div>
                );
              })}
            </div>

            {result.flagged_merchants && result.flagged_merchants.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <span style={{ ...labelStyle, marginBottom: 6 }}>Flagged Merchants</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                  {result.flagged_merchants.map((m, i) => (
                    <span
                      key={i}
                      style={{
                        padding: '3px 8px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: 4,
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        color: '#ef4444',
                      }}
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <ReasonCodeList codes={result.reason_codes} />
          </motion.div>
        )}
      </GlassCard>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Section 4: UPI Compliance Monitor                                  */
/* ------------------------------------------------------------------ */

const UPI_DEFAULT_PAYLOAD = {
  account: {
    account_id: 'DEMO_ACC',
    annual_upi_credit: 2200000,
  },
  transactions: [
    {
      amount: 12000,
      channel: 'UPI',
      is_new_beneficiary: true,
    },
  ],
};

function UPIComplianceSection() {
  const [form, setForm] = useState({ ...UPI_DEFAULT_PAYLOAD });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const updateAccount = (field, value) => {
    setForm(prev => ({
      ...prev,
      account: { ...prev.account, [field]: value },
    }));
  };

  const updateTransaction = (field, value) => {
    setForm(prev => ({
      ...prev,
      transactions: [{ ...prev.transactions[0], [field]: value }],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch(`/api/v1/india/upi-compliance/${form.account.account_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || body?.message || `Request failed (${res.status})`);
      }
      const body = await res.json();
      setResult(body?.data || body);
    } catch (err) {
      setError(err.message || 'Check failed');
    } finally {
      setLoading(false);
    }
  };

  const UPI_LIMIT = 2500000; // 25 lakh
  const proximityPct = result?.limit_proximity_pct ?? null;
  const annualCredit = result?.annual_upi_credit ?? form.account.annual_upi_credit;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>UPI Compliance Monitor</p>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <FormInput
              label="Account ID"
              value={form.account.account_id}
              onChange={e => updateAccount('account_id', e.target.value)}
            />
            <FormInput
              label="Annual UPI Credit"
              type="number"
              min={0}
              value={form.account.annual_upi_credit}
              onChange={e => updateAccount('annual_upi_credit', Number(e.target.value))}
            />
          </div>

          <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <span style={{ ...labelStyle, marginBottom: 8 }}>Transaction</span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormInput
                label="Amount"
                type="number"
                min={0}
                value={form.transactions[0].amount}
                onChange={e => updateTransaction('amount', Number(e.target.value))}
              />
              <FormInput
                label="Channel"
                value={form.transactions[0].channel}
                onChange={e => updateTransaction('channel', e.target.value)}
              />
              <FormField label="New Beneficiary">
                <label style={{
                  display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
                  fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                  padding: '8px 0',
                }}>
                  <input
                    type="checkbox"
                    checked={form.transactions[0].is_new_beneficiary}
                    onChange={e => updateTransaction('is_new_beneficiary', e.target.checked)}
                    style={{ accentColor: '#3EE7FF' }}
                  />
                  is_new_beneficiary
                </label>
              </FormField>
            </div>
          </div>

          <SubmitButton loading={loading} label="Check" loadingLabel="Checking..." />
        </form>
        <ErrorBanner message={error} />
      </GlassCard>

      <GlassCard hover={false} padding={20}>
        <p style={sectionTitleStyle}>UPI Compliance Result</p>
        {!result && !loading && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            Submit the form to see results
          </div>
        )}
        {loading && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12,
          }}>
            <div className="spinner" style={{ marginRight: 8 }} />
            Running compliance check...
          </div>
        )}
        {result && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <ScoreBadge
                score={result.composite_score ?? 0}
                label="Composite Score"
              />
            </div>

            {/* Progress bar toward 25L limit */}
            <div style={{ marginBottom: 16 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 6,
              }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}>
                  UPI Annual Limit Proximity
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                  color: proximityPct >= 90
                    ? '#ef4444'
                    : proximityPct >= 70
                      ? '#f59e0b'
                      : 'var(--accent-cyan)',
                }}>
                  {proximityPct != null ? `${proximityPct.toFixed(1)}%` : '--'}
                </span>
              </div>
              <div style={{
                width: '100%',
                height: 10,
                background: 'var(--bg-elevated)',
                borderRadius: 5,
                overflow: 'hidden',
                border: '1px solid var(--border)',
              }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(proximityPct ?? 0, 100)}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                  style={{
                    height: '100%',
                    borderRadius: 5,
                    background: proximityPct >= 90
                      ? 'linear-gradient(90deg, #ef4444, #dc2626)'
                      : proximityPct >= 70
                        ? 'linear-gradient(90deg, #f59e0b, #d97706)'
                        : 'linear-gradient(90deg, var(--accent-cyan), #06b6d4)',
                  }}
                />
              </div>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: 4,
              }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 9,
                  color: 'var(--text-muted)',
                }}>
                  {annualCredit != null
                    ? `${(annualCredit / 100000).toFixed(1)}L`
                    : '0L'}
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 9,
                  color: 'var(--text-muted)',
                }}>
                  {(UPI_LIMIT / 100000).toFixed(0)}L Limit
                </span>
              </div>
            </div>

            <ResultRow
              label="Annual UPI Credit"
              value={
                annualCredit != null
                  ? `${(annualCredit / 100000).toFixed(1)}L`
                  : '--'
              }
            />
            <ResultRow
              label="Cooling Period"
              value={result.cooling_period_applicable ? 'Yes' : 'No'}
              color={result.cooling_period_applicable ? '#f59e0b' : '#22c55e'}
            />

            {result.flags && result.flags.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <span style={{ ...labelStyle, marginBottom: 6 }}>Flags</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                  {result.flags.map((flag, i) => (
                    <span
                      key={i}
                      style={{
                        padding: '3px 8px',
                        background: 'rgba(245, 158, 11, 0.1)',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                        borderRadius: 4,
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        color: '#f59e0b',
                      }}
                    >
                      {flag}
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

/* ------------------------------------------------------------------ */
/*  Main Page Component                                                */
/* ------------------------------------------------------------------ */

export default function IndiaCompliancePage() {
  const [activeTab, setActiveTab] = useState('fri');

  const renderSection = () => {
    switch (activeTab) {
      case 'fri':
        return <FRILookupSection />;
      case 'jandhan':
        return <JanDhanSection />;
      case 'crypto':
        return <CryptoGamingSection />;
      case 'upi':
        return <UPIComplianceSection />;
      default:
        return <FRILookupSection />;
    }
  };

  return (
    <div style={{ padding: '32px 32px 48px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Page Header */}
      <AnimateIn>
        <div style={{ marginBottom: 28 }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--accent-cyan)',
            letterSpacing: '3px',
            textTransform: 'uppercase',
            marginBottom: 8,
            opacity: 0.8,
          }}>
            RBI &middot; India Regulatory Compliance
          </div>
          <h1 className="gradient-text" style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 28,
            fontWeight: 700,
            letterSpacing: '-0.5px',
            margin: 0,
          }}>
            India Compliance
          </h1>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--text-muted)',
            marginTop: 6,
            letterSpacing: '0.3px',
          }}>
            // FRI &middot; Jan Dhan &middot; Crypto/Gaming &middot; UPI Regulatory
          </p>
        </div>
      </AnimateIn>

      {/* Tab Bar */}
      <AnimateIn delay={0.05}>
        <GlassCard
          hover={false}
          padding={0}
          style={{ marginBottom: 20, overflow: 'visible' }}
        >
          <div style={{
            display: 'flex',
            gap: 0,
            borderBottom: '1px solid var(--border)',
          }}>
            {TABS.map((tab, i) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.key;
              return (
                <motion.button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '14px 16px',
                    background: isActive
                      ? 'rgba(62, 231, 255, 0.06)'
                      : 'transparent',
                    border: 'none',
                    borderBottom: isActive
                      ? '2px solid var(--accent-cyan)'
                      : '2px solid transparent',
                    color: isActive
                      ? 'var(--accent-cyan)'
                      : 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    fontWeight: isActive ? 600 : 400,
                    letterSpacing: '0.5px',
                    textTransform: 'uppercase',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    position: 'relative',
                  }}
                  whileHover={{ background: 'rgba(62, 231, 255, 0.04)' }}
                  whileTap={{ scale: 0.98 }}
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.08 + i * 0.04 }}
                >
                  <Icon size={16} />
                  {tab.label}
                </motion.button>
              );
            })}
          </div>
        </GlassCard>
      </AnimateIn>

      {/* Active Section Content */}
      <AnimateIn delay={0.1} key={activeTab} direction="fade">
        {renderSection()}
      </AnimateIn>
    </div>
  );
}
