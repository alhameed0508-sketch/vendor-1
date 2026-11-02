import React, { useState } from 'react';
import { addEvidence } from './complaintsApi';
import { EVIDENCE_PRESETS, SOURCE, canWrite } from './labels';

const IST_OFFSET = '+05:30';
const minuteOf = iso => iso.slice(0, 16); // the desk clock is already in IST

export default function EvidenceForm({ view, role, onAdded }) {
  const [presetKey, setPresetKey] = useState(EVIDENCE_PRESETS[0].key);
  const [summary, setSummary] = useState(EVIDENCE_PRESETS[0].summary);
  const [at, setAt] = useState(minuteOf(view.as_of));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const endpoint = `POST /api/v1/complaints/${view.complaint_id}/evidence`;

  if (view.status !== 'OPEN') return null;

  const pick = e => {
    const preset = EVIDENCE_PRESETS.find(p => p.key === e.target.value);
    setPresetKey(preset.key);
    setSummary(preset.summary);
  };

  const submit = async e => {
    e.preventDefault();
    const { source, kind, data } = EVIDENCE_PRESETS.find(p => p.key === presetKey);
    setBusy(true);
    setError('');
    try {
      onAdded(await addEvidence(view.complaint_id, { source, kind, data, summary, at: `${at}:00${IST_OFFSET}` }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="glass-card fc-card">
      <h2 className="section-title">Add evidence</h2>
      <p className="page-meta">
        Couriers, merchants and telecom partners send this through <code className="fc-code">{endpoint}</code>.
        It appears on an open case within seconds.
      </p>
      {canWrite(role) ? (
        <form onSubmit={submit} className="fc-form">
          <label>What arrived
            <select value={presetKey} onChange={pick}>
              {EVIDENCE_PRESETS.map(p => <option key={p.key} value={p.key}>{SOURCE[p.source]}: {p.summary.split(': ')[1] || p.summary}</option>)}
            </select>
          </label>
          <label>Summary
            <input value={summary} onChange={e => setSummary(e.target.value)} required maxLength={500} />
          </label>
          <label>When it happened (IST)
            <input type="datetime-local" value={at} max={minuteOf(view.as_of)} onChange={e => setAt(e.target.value)} required />
          </label>
          {error && <p role="alert" className="fc-error">{error}</p>}
          <button type="submit" className="btn btn-ghost btn-sm" disabled={busy}>{busy ? 'Adding…' : 'Add to the chain'}</button>
        </form>
      ) : (
        <p className="page-meta">Sign in as bank staff to add evidence here.</p>
      )}
    </section>
  );
}
