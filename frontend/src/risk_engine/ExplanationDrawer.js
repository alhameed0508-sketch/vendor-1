import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import {
  BAND_META, ENGINE_META, ENGINE_ORDER, FEEDBACK_ROLES, SOURCE_META, engineReasons, formatInr, getJson, postJson,
} from './riskApi';

const KIND_LABEL = { decisive: 'Confirmed fact', strong: 'Evidence', weak: 'Context', familiarity: 'Calming' };

function Bar({ value, color }) {
  const width = `${Math.max(0, Math.min(1, value || 0)) * 100}%`;
  return (
    <div className="re-bar" aria-hidden="true">
      <div className="re-bar-fill" style={{ width, background: color }} />
    </div>
  );
}

/** ``initial`` is a decision from the feed: used as-is when it carries its explanation (stream events do),
 * otherwise fetched in full by id. Live-feed decisions come from a private engine and are never fetched. */
export default function ExplanationDrawer({ initial, role, onClose, onUpdated }) {
  const [decision, setDecision] = useState(initial?.explanation ? initial : null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const decisionId = initial?.decision_id;

  useEffect(() => {
    let alive = true;
    setError(null);
    if (initial?.explanation) {
      setDecision(initial);
      return undefined;
    }
    setDecision(null);
    getJson(`/decisions/${decisionId}`)
      .then((d) => alive && setDecision(d))
      .catch((e) => alive && setError(e.message));
    return () => { alive = false; };
  }, [initial, decisionId]);

  const sendFeedback = async (outcome) => {
    setSaving(true);
    try {
      const updated = await postJson(`/decisions/${decisionId}/feedback`, { outcome, note: '' });
      setDecision(updated);
      if (onUpdated) onUpdated(updated);
      toast.success(outcome === 'FALSE_ALERT'
        ? "Recorded as a false alert: this payee, phone and place now count as the customer's own."
        : 'Recorded as fraud: the payee is now a known-fraud account for every customer.');
    } catch (e) {
      toast.error(`Feedback not saved: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const exp = decision?.explanation;
  const band = decision ? BAND_META[decision.band] || BAND_META.APPROVE : null;
  const source = decision ? SOURCE_META[decision.source] : null;
  const canGiveFeedback = decision && FEEDBACK_ROLES.includes(role) && decision.source !== 'live';
  const calming = (decision?.reasons || []).filter((r) => r.kind === 'familiarity');
  const contributions = Object.entries(decision?.contributions || {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const maxAbs = Math.max(0.01, ...contributions.map(([, v]) => Math.abs(v)));

  return (
    <aside className="re-drawer" role="dialog" aria-label="Decision explanation">
      <div className="re-drawer-head">
        <span className="eyebrow">Why this decision</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close explanation">
          <X size={14} />
        </button>
      </div>
      {error && <p className="re-error">{error}</p>}
      {!decision && !error && <p className="re-muted">Loading…</p>}
      {decision && (
        <div className="re-drawer-body">
          <div className="re-drawer-top">
            <span className="re-band" style={{ color: band.color, borderColor: band.color }}>{band.label}</span>
            <span className="re-score">{decision.score}<small>/100</small></span>
            {source && <span className="re-source" title={source.title}>{source.label}</span>}
          </div>
          <p className="re-summary">{exp.summary}</p>
          <p className="re-action"><strong>Action:</strong> {exp.action}</p>
          <dl className="re-facts">
            <dt>Payment</dt>
            <dd>{decision.customer_id} → {decision.beneficiary_id}, {formatInr(decision.amount)}</dd>
            <dt>Event time</dt>
            <dd>{decision.event_time}{decision.source === 'synthetic' || decision.source === 'scenario'
              ? ' (simulated)' : ''}</dd>
            <dt>Baseline confidence</dt>
            <dd>{Math.round((exp.confidence || 0) * 100)}% · familiarity {Math.round((exp.familiarity || 0) * 100)}%</dd>
            {exp.personal_limit && (<><dt>Usual ceiling</dt><dd>{formatInr(exp.personal_limit)}</dd></>)}
            <dt>Engines in agreement</dt>
            <dd>{exp.corroborating_engines} of 4</dd>
          </dl>

          {exp.false_positive_controls?.length > 0 && (
            <section className="re-section">
              <h3>False-positive controls applied</h3>
              <ul>{exp.false_positive_controls.map((c) => <li key={c}>{c}</li>)}</ul>
            </section>
          )}

          <section className="re-section">
            <h3>Engines</h3>
            {ENGINE_ORDER.map((key) => {
              const e = exp.engines[key];
              const reasons = engineReasons(decision.reasons, key);
              return (
                <div key={key} className="re-engine-row">
                  <div className="re-engine-row-head">
                    <span>{ENGINE_META[key].label}{ENGINE_META[key].core ? ' (core)' : ''}</span>
                    <span>{e.data_available ? `${Math.round(e.score * 100)}%` : 'no data'}</span>
                  </div>
                  <Bar value={e.score} color={e.score >= 0.4 ? 'var(--critical)' : 'var(--accent)'} />
                  {reasons.map((r) => (
                    <p key={r.code + r.text} className="re-reason">
                      <code>{r.code}</code> <span className={`re-kind re-kind-${r.kind}`}>{KIND_LABEL[r.kind]}</span>{' '}
                      {r.text}{r.dampened ? ' (softened by familiarity)' : ''}
                    </p>
                  ))}
                  {!e.data_available && <p className="re-muted">{e.note}</p>}
                </div>
              );
            })}
          </section>

          {calming.length > 0 && (
            <section className="re-section">
              <h3>What calmed the score</h3>
              {calming.map((r) => <p key={r.code} className="re-reason"><code>{r.code}</code> {r.text}</p>)}
            </section>
          )}

          <section className="re-section">
            <h3>Model contributions (log-odds)</h3>
            <p className="re-muted">Model {exp.model.version}; intercept {exp.model.intercept}; probability{' '}
              {(exp.model.probability * 100).toFixed(1)}% before the false-positive controls.</p>
            {contributions.map(([name, value]) => (
              <div key={name} className="re-contrib">
                <span>{name}</span>
                <div className="re-contrib-track">
                  <div className="re-contrib-fill" style={{ width: `${(Math.abs(value) / maxAbs) * 50}%`,
                    [value >= 0 ? 'left' : 'right']: '50%',
                    background: value >= 0 ? 'var(--critical)' : 'var(--accent)' }} />
                </div>
                <span className="re-num">{value > 0 ? '+' : ''}{value.toFixed(2)}</span>
              </div>
            ))}
          </section>

          {decision.outcome && (
            <p className="re-outcome">Outcome: <strong>{decision.outcome === 'FALSE_ALERT' ? 'False alert' : 'Confirmed fraud'}</strong>
              {decision.outcome_by ? ` by ${decision.outcome_by}` : ''}</p>
          )}
          {canGiveFeedback && (
            <div className="re-feedback">
              <button type="button" className="btn btn-danger btn-sm" disabled={saving}
                onClick={() => sendFeedback('CONFIRMED_FRAUD')}>Confirmed fraud</button>
              <button type="button" className="btn btn-ghost btn-sm" disabled={saving}
                onClick={() => sendFeedback('FALSE_ALERT')}>False alert</button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
