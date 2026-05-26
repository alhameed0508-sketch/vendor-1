import React from 'react';
import { motion } from 'framer-motion';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';

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

export { DEFAULT_FORM };

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

function FormInput({ label, type = 'text', value, onChange, ...rest }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input
        type={type}
        style={inputStyle}
        value={value}
        onChange={onChange}
        onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
        onBlur={e => e.target.style.borderColor = 'var(--border)'}
        {...rest}
      />
    </div>
  );
}

export default function AssessmentForm({ form, onFormChange, onSubmit, loading }) {
  const handleChange = (field, value) => {
    onFormChange(field, value);
  };

  return (
    <AnimateIn delay={0.1}>
      <GlassCard className="p-5" hover={false}>
        <p style={{
          fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)',
          letterSpacing: '2px', textTransform: 'uppercase', marginBottom: 16,
        }}>
          New Assessment
        </p>
        <form onSubmit={onSubmit}>
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

            <FormInput
              label="Account Age (days)"
              type="number" min={0}
              value={form.account_age_days}
              onChange={e => handleChange('account_age_days', Number(e.target.value))}
            />
            <FormInput
              label="KYC Completeness (0-1)"
              type="number" step="0.01" min={0} max={1}
              value={form.kyc_completeness}
              onChange={e => handleChange('kyc_completeness', Number(e.target.value))}
            />
            <FormInput
              label="Doc Verification (sec)"
              type="number" min={0}
              value={form.doc_verification_seconds}
              onChange={e => handleChange('doc_verification_seconds', Number(e.target.value))}
            />
            <FormInput
              label="Device Overlap Count"
              type="number" min={0}
              value={form.device_overlap_count}
              onChange={e => handleChange('device_overlap_count', Number(e.target.value))}
            />
            <FormInput
              label="Phone Number Age (days)"
              type="number" min={0}
              value={form.phone_age_days}
              onChange={e => handleChange('phone_age_days', Number(e.target.value))}
            />
            <FormInput
              label="Email Age (days)"
              type="number" min={0}
              value={form.email_age_days}
              onChange={e => handleChange('email_age_days', Number(e.target.value))}
            />
            <FormInput
              label="Selfie Match (0-1)"
              type="number" step="0.01" min={0} max={1}
              value={form.selfie_confidence}
              onChange={e => handleChange('selfie_confidence', Number(e.target.value))}
            />
            <FormInput
              label="App Velocity Count"
              type="number" min={0}
              value={form.application_velocity_count}
              onChange={e => handleChange('application_velocity_count', Number(e.target.value))}
            />
            <FormInput
              label="Similar Name Count"
              type="number" min={0}
              value={form.similar_name_count}
              onChange={e => handleChange('similar_name_count', Number(e.target.value))}
            />
            <FormInput
              label="Application Hour (0-23)"
              type="number" min={0} max={23}
              value={form.application_hour}
              onChange={e => handleChange('application_hour', Number(e.target.value))}
            />

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
  );
}
