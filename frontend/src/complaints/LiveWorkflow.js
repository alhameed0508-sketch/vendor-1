import React, { useEffect, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { formatRupeesExact } from '../utils/formatAmount';
import { CATEGORY, OUTCOME, SOURCE, formatWhen } from './labels';

const STEP_MS = 1400;

// The zero-liability label already says the customer pays nothing.
const liabilityText = step => {
  if (step.outcome === 'ZERO_LIABILITY') return null;
  return step.customer_liability == null ? 'Amount set by bank policy' : `Customer pays ${formatRupeesExact(step.customer_liability)}`;
};

function Stage({ title, lit, children }) {
  return (
    <div className={`fc-stage${lit ? ' fc-stage--lit' : ''}`}>
      <div className="text-metric-label">{title}</div>
      <div className="fc-stage__body">{children}</div>
    </div>
  );
}

function Event({ step, previous, current, fresh }) {
  const moved = !previous || previous.category !== step.category || previous.outcome !== step.outcome;
  const classes = ['fc-event', current && 'fc-event--current', fresh && 'fc-event--fresh'].filter(Boolean).join(' ');
  return (
    <li id={`ev-${step.evidence_id}`} className={classes}>
      <div className="fc-event__meta">
        <span className="fc-chip">{step.evidence_id}</span>
        <strong>{SOURCE[step.source] || step.source}</strong>
        <span>received {formatWhen(step.received_at)}</span>
      </div>
      <div className="fc-event__summary">{step.summary}</div>
      <div className="fc-event__at">Happened {formatWhen(step.at)}</div>
      {moved && (
        <div className="fc-event__moved">
          Finding now: {CATEGORY[step.category]}, {OUTCOME[step.outcome]?.label.toLowerCase()}
        </div>
      )}
    </li>
  );
}

/**
 * The case as a flow: sources send evidence, the chain grows, the RBI rules place it, a recommendation
 * follows, a supervisor decides. Replay steps through the evidence in the order the bank received it.
 */
export default function LiveWorkflow({ view, fresh }) {
  const steps = view.replay;
  const [position, setPosition] = useState(null); // null = live: everything received so far
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = setTimeout(() => {
      const next = (position ?? 0) + 1;
      setPosition(next >= steps.length ? null : next);
      if (next >= steps.length) setPlaying(false);
    }, STEP_MS);
    return () => clearTimeout(timer);
  }, [playing, position, steps.length]);

  const shown = position ?? steps.length;
  const current = steps[shown - 1];
  const sources = [...new Set(steps.slice(0, shown).map(s => s.source))];
  const decided = Boolean(view.decision) && position === null;

  const play = () => { setPosition(1); setPlaying(true); };
  const scrub = event => {
    const value = Number(event.target.value);
    setPlaying(false);
    setPosition(value >= steps.length ? null : value);
  };

  return (
    <section className="glass-card fc-card" aria-labelledby="fc-flow-title">
      <div className="fc-card__head">
        <div>
          <h2 id="fc-flow-title" className="section-title" style={{ margin: 0 }}>Live workflow</h2>
          <p className="page-meta">Every item as the bank received it, and how the recommendation moved.</p>
        </div>
        <div className="fc-controls">
          <button type="button" className="btn btn-ghost btn-sm" onClick={playing ? () => setPlaying(false) : play}>
            {playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}
            {playing ? 'Pause' : 'Replay the case'}
          </button>
          <span className="page-meta" aria-live="polite">
            {position === null
              ? <><span className="fc-live-dot" aria-hidden />Live</>
              : `Step ${shown} of ${steps.length}`}
          </span>
        </div>
      </div>

      <input type="range" className="fc-scrub" min={1} max={steps.length} value={shown} onChange={scrub}
             aria-label="Step through the evidence" />

      <div className="fc-flow">
        <Stage title="Sources" lit>
          <div className="fc-chips">{sources.map(s => <span key={s} className="fc-chip">{SOURCE[s] || s}</span>)}</div>
        </Stage>
        <Stage title="Evidence chain" lit>
          {shown} item{shown === 1 ? '' : 's'}
          <div className="page-meta">
            {view.chain.intact ? 'Hash chain intact' : `Chain broken at ${view.chain.broken_at}`}
          </div>
        </Stage>
        <Stage title="RBI rules" lit={current.category !== 'UNDETERMINED'}>
          {CATEGORY[current.category]}
        </Stage>
        <Stage title="Recommendation" lit>
          <span style={{ color: OUTCOME[current.outcome]?.colour }}>{OUTCOME[current.outcome]?.label}</span>
          {liabilityText(current) && <div className="page-meta">{liabilityText(current)}</div>}
          {current.proof_needed > 0 && (
            <div className="page-meta">Proof {current.proof_met} of {current.proof_needed}</div>
          )}
        </Stage>
        <Stage title="Supervisor" lit={decided}>
          {decided ? `${OUTCOME[view.decision.outcome]?.label}, by ${view.decision.decided_by}` : 'Waiting for a decision'}
        </Stage>
      </div>

      <ol className="fc-events">
        {steps.slice(0, shown).map((step, i) => (
          <Event key={step.evidence_id} step={step} previous={steps[i - 1]}
                 current={position !== null && i === shown - 1} fresh={fresh.has(step.evidence_id)} />
        ))}
      </ol>
    </section>
  );
}
