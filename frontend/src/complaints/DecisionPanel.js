import React, { useState } from 'react';
import { formatRupeesExact } from '../utils/formatAmount';
import { recordDecision } from './complaintsApi';
import { DECISION_OUTCOMES, OUTCOME, canDecide, formatWhen } from './labels';

function DecisionRecord({ decision }) {
  const followed = decision.followed_recommendation;
  return (
    <ul className="fc-facts">
      <li><strong>{OUTCOME[decision.outcome]?.label}</strong>, customer pays {formatRupeesExact(decision.customer_liability)}</li>
      <li>By {decision.decided_by}, {formatWhen(decision.decided_at)}</li>
      <li>{followed == null ? 'Bank policy case: no amount was recommended'
        : followed ? 'Followed the recommendation' : 'Departed from the recommendation'}</li>
      <li>{decision.within_time_limit ? 'Within the time limit' : 'After the time limit'}</li>
      <li className="fc-basis">{decision.notes}</li>
    </ul>
  );
}

function DecisionForm({ view, onDecided }) {
  const recommended = view.liability.customer_liability;
  const [form, setForm] = useState({
    outcome: DECISION_OUTCOMES.includes(view.liability.outcome) ? view.liability.outcome : 'ZERO_LIABILITY',
    customer_liability: recommended ?? 0,
    notes: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const change = e => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      onDecided(await recordDecision(view.complaint_id, { ...form, customer_liability: Number(form.customer_liability) }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="fc-form">
      <label>Outcome
        <select name="outcome" value={form.outcome} onChange={change}>
          {DECISION_OUTCOMES.map(o => <option key={o} value={o}>{OUTCOME[o].label}</option>)}
        </select>
      </label>
      <label>Customer pays (₹)
        <input name="customer_liability" type="number" min="0" max={view.amount} step="1" required
               value={form.customer_liability} onChange={change} />
      </label>
      <label>Reasons
        <textarea name="notes" rows={3} required maxLength={2000} value={form.notes} onChange={change} />
      </label>
      {error && <p role="alert" className="fc-error">{error}</p>}
      <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
        {busy ? 'Recording…' : 'Record decision'}
      </button>
    </form>
  );
}

export default function DecisionPanel({ view, role, onDecided }) {
  return (
    <section className="glass-card fc-card">
      <h2 className="section-title">Decision</h2>
      {view.decision
        ? <DecisionRecord decision={view.decision} />
        : canDecide(role)
          ? <DecisionForm view={view} onDecided={onDecided} />
          : <p className="page-meta">A supervisor records the decision. Sign in as one to decide this case.</p>}
    </section>
  );
}
