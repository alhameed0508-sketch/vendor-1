import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { TierChip } from './TierChip';
import { SCENARIO, TIER } from './labels';

/** A walk through the seven demo cases, one at a time, ending in a summary of what was seen. */
export default function DemoTour({ scenarios, onClose }) {
  const [step, setStep] = useState(0);
  const total = scenarios.length;
  const done = step >= total;
  const current = scenarios[step];

  if (done) {
    const counts = Object.keys(TIER).map(t => [t, scenarios.filter(s => s.tier === t).length]);
    const person = scenarios.filter(s => s.tier !== 'APPROVE').length;
    return (
      <section className="rf-tour rf-summary-card" aria-label="Tour summary">
        <h3>What you saw</h3>
        <ul className="rf-tiers">
          {counts.map(([t, n]) => <li key={t}><strong>{n}</strong>{TIER[t].label}</li>)}
        </ul>
        <p>
          {person} of {total} cases need a person to look. Not one was refunded or blocked automatically, and
          no single check could send a case to the fraud desk on its own.
        </p>
        <div className="rf-actions">
          <button type="button" className="btn btn-primary btn-sm" onClick={onClose}>Review claims</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setStep(0)}>Start again</button>
        </div>
      </section>
    );
  }

  return (
    <section className="rf-tour" aria-label="Demo tour">
      <div className="rf-tour__top">
        <span className="rf-muted">Case {step + 1} of {total}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Leave the tour</button>
      </div>
      <div className="rf-progress" role="progressbar" aria-label="Tour progress" aria-valuemin={0} aria-valuemax={total} aria-valuenow={step + 1}>
        <span style={{ width: `${((step + 1) / total) * 100}%` }} />
      </div>
      <h3>{SCENARIO[current.scenario] || current.scenario}</h3>
      <p>{current.blurb}</p>
      <p>{current.tier && <TierChip tier={current.tier} score={current.score} />}</p>
      <div className="rf-actions">
        {current.claim_id && <Link className="btn btn-primary btn-sm" to={`/returns/${current.claim_id}`}>Open this case</Link>}
        <button type="button" className="btn btn-ghost btn-sm" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setStep(step + 1)}>
          {step === total - 1 ? 'Finish' : 'Next case'}
        </button>
      </div>
    </section>
  );
}
