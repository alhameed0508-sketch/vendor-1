import React, { useState } from 'react';
import { ShieldCheck, UserCheck } from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../auth/api';

const card = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: 24,
  boxShadow: 'var(--shadow)',
};

async function post(path, payload) {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok || !body.success) {
    throw new Error(body?.error?.message || 'Request failed');
  }
  return body.data;
}

function Result({ data }) {
  if (!data) return null;
  return (
    <div style={{ ...card, marginTop: 18 }} aria-live="polite">
      <div className="section-title">Decision</div>
      <pre style={{
        margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere',
        color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)',
        fontSize: 12, lineHeight: 1.6,
      }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

export default function RiskOperationsPage() {
  const [mode, setMode] = useState('onboarding');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    account_id: '',
    name: '',
    phone_number: '',
    email_address: '',
    postal_address: '',
    identifiers: '',
    phone_age_days: 365,
    email_age_days: 365,
    kyc_completeness: 1,
    selfie_confidence: 0.95,
    device_overlap_count: 0,
    ip_geolocation_mismatch: false,
    address_verified: true,
  });

  const change = (event) => {
    const { name, value, type, checked } = event.target;
    setForm(previous => ({
      ...previous,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const data = mode === 'onboarding'
        ? await post('/api/v1/onboarding/assess', {
            account_id: form.account_id,
            full_name: form.name,
            phone_number: form.phone_number || null,
            email_address: form.email_address || null,
            postal_address: form.postal_address || null,
            phone_age_days: Number(form.phone_age_days),
            email_age_days: Number(form.email_age_days),
            kyc_completeness: Number(form.kyc_completeness),
            selfie_confidence: Number(form.selfie_confidence),
            device_overlap_count: Number(form.device_overlap_count),
            ip_geolocation_mismatch: form.ip_geolocation_mismatch,
            address_verified: form.address_verified,
          })
        : await post('/api/v1/screening/screen', {
            account_id: form.account_id,
            name: form.name,
            identifiers: form.identifiers
              .split(',')
              .map(value => value.trim())
              .filter(Boolean),
          });
      setResult(data);
      toast.success(mode === 'onboarding' ? 'Risk assessment completed' : 'Screening completed');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1000, margin: '0 auto' }}>
      <div className="page-header">
        <h1>Customer Risk Operations</h1>
        <div className="page-meta">
          Onboarding mule-risk assessment and sanctions screening
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        <button
          className={mode === 'onboarding' ? 'btn-primary' : 'btn-secondary'}
          onClick={() => { setMode('onboarding'); setResult(null); }}
        >
          <UserCheck size={14} /> Onboarding
        </button>
        <button
          className={mode === 'screening' ? 'btn-primary' : 'btn-secondary'}
          onClick={() => { setMode('screening'); setResult(null); }}
        >
          <ShieldCheck size={14} /> Sanctions screening
        </button>
      </div>

      <form onSubmit={submit} style={card}>
        <div className="section-title">
          {mode === 'onboarding' ? 'Assess application' : 'Screen customer'}
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 14,
        }}>
          <label>
            Account/application ID
            <input name="account_id" value={form.account_id} onChange={change} required maxLength={100} />
          </label>

          {mode === 'screening' ? (
            <>
              <label>
                Customer name
                <input name="name" value={form.name} onChange={change} required maxLength={200} />
              </label>
              <label>
                Identifiers (comma separated)
                <input name="identifiers" value={form.identifiers} onChange={change} maxLength={500} />
              </label>
            </>
          ) : (
            <>
              <label>Customer name
                <input name="name" value={form.name} onChange={change} required maxLength={200} />
              </label>
              <label>Phone number
                <input name="phone_number" value={form.phone_number} onChange={change} maxLength={30} />
              </label>
              <label>Email address
                <input name="email_address" type="email" value={form.email_address} onChange={change} maxLength={254} />
              </label>
              <label>Postal address
                <input name="postal_address" value={form.postal_address} onChange={change} maxLength={500} />
              </label>
              <label>KYC completeness
                <input name="kyc_completeness" type="number" min="0" max="1" step="0.01" value={form.kyc_completeness} onChange={change} />
              </label>
              <label>Selfie confidence
                <input name="selfie_confidence" type="number" min="0" max="1" step="0.01" value={form.selfie_confidence} onChange={change} />
              </label>
              <label>Phone age (days)
                <input name="phone_age_days" type="number" min="0" value={form.phone_age_days} onChange={change} />
              </label>
              <label>Email age (days)
                <input name="email_age_days" type="number" min="0" value={form.email_age_days} onChange={change} />
              </label>
              <label>Shared device accounts
                <input name="device_overlap_count" type="number" min="0" value={form.device_overlap_count} onChange={change} />
              </label>
              <label><input name="address_verified" type="checkbox" checked={form.address_verified} onChange={change} /> Address verified</label>
              <label><input name="ip_geolocation_mismatch" type="checkbox" checked={form.ip_geolocation_mismatch} onChange={change} /> IP geography mismatch</label>
            </>
          )}
        </div>
        <button className="btn-primary" type="submit" disabled={loading} style={{ marginTop: 18 }}>
          {loading ? 'Processing…' : mode === 'onboarding' ? 'Assess risk' : 'Run screening'}
        </button>
      </form>
      <Result data={result} />
    </div>
  );
}
