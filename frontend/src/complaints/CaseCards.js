import React from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';
import { formatRupeesExact } from '../utils/formatAmount';
import { alertPath } from '../utils/safeNavigation';
import { CATEGORY, FLAG, OUTCOME, clockLabel, formatDay } from './labels';

const SPLIT_LABELS = { rbi: 'RBI fund', customer_bank: 'Your bank', beneficiary_bank: 'Beneficiary bank' };

const Cites = ({ ids }) => ids.map(id => <a key={id} href={`#ev-${id}`} className="fc-chip fc-cite">{id}</a>);

function CheckRow({ met, label, ids = [] }) {
  return (
    <li className="fc-check">
      {met
        ? <Check size={14} aria-label="Met" style={{ color: 'var(--accent)' }} />
        : <X size={14} aria-label="Not met" style={{ color: 'var(--critical)' }} />}
      <span>{label} <Cites ids={ids} /></span>
    </li>
  );
}

export function ClockBar({ daysLeft, limit, overdue }) {
  const used = overdue ? 100 : Math.min(100, Math.max(0, ((limit - daysLeft) / limit) * 100));
  const colour = overdue ? 'var(--critical)' : daysLeft <= 7 ? 'var(--high)' : 'var(--accent)';
  return <div className="fc-clock" aria-hidden><span style={{ width: `${used}%`, background: colour }} /></div>;
}

export function ClockCard({ view }) {
  const d = view.deadlines;
  return (
    <section className="glass-card fc-card">
      <h2 className="section-title">Clock</h2>
      <div className="fc-big" style={{ color: d.overdue ? 'var(--critical)' : 'var(--text-primary)' }}>
        {view.status === 'OPEN' ? clockLabel(d) : 'Decided'}
      </div>
      <ClockBar daysLeft={d.days_left} limit={d.resolution_limit_days} overdue={d.overdue && view.status === 'OPEN'} />
      <ul className="fc-facts">
        <li>Resolve by {formatDay(d.resolve_by)} ({d.resolution_limit_days}-day limit{view.cross_border ? ', cross-border' : ''})</li>
        <li>
          Reported {d.reported_after_days === 0 ? 'the same day'
            : `${d.reported_after_days} day${d.reported_after_days === 1 ? '' : 's'} after the fraud`}:
          {d.within_zero_liability_window ? ' inside' : ' outside'} the 5-day zero-liability window
        </li>
        {d.shadow_credit_by && <li>Shadow credit to the card by {formatDay(d.shadow_credit_by)}</li>}
        {!d.rules_in_force && <li>Fraud before 1 Jan 2027: the earlier RBI rules apply</li>}
      </ul>
    </section>
  );
}

export function RecommendationCard({ view }) {
  const { finding, liability, mule_link: mule } = view;
  const outcome = OUTCOME[liability.outcome];
  return (
    <section className="glass-card fc-card">
      <h2 className="section-title">Recommendation</h2>
      <div className="fc-big" style={{ color: outcome?.colour }}>{outcome?.label}</div>
      <p className="page-meta">
        {CATEGORY[finding.category]}.{' '}
        {liability.customer_liability == null
          ? 'The amount follows your board-approved policy.'
          : `Customer liability ${formatRupeesExact(liability.customer_liability)}.`}
      </p>
      <p className="fc-basis">{liability.basis}</p>
      {finding.flags.length > 0 && (
        <div className="fc-chips">
          {finding.flags.map(f => <span key={f} className="fc-chip fc-chip--warn">{FLAG[f] || f}</span>)}
        </div>
      )}
      {mule && (
        <p className="fc-basis">
          Beneficiary {mule.account_id} is {/^[aeiou]/i.test(mule.role) ? 'an' : 'a'} {String(mule.role).toLowerCase()} in{' '}
          <Link to={alertPath(mule.alert_id)}>MuleCatch alert {mule.alert_id}</Link>
          {mule.risk_score != null && `, risk ${Math.round(mule.risk_score * 100)}%`}.
        </p>
      )}
      {finding.reasons.length > 0 && (
        <ul className="fc-checks">
          {finding.reasons.map(r => <CheckRow key={r.evidence.join()} met label={r.text} ids={r.evidence} />)}
        </ul>
      )}
      {finding.checklist.length > 0 && (
        <>
          <h3 className="fc-subhead">What the bank must prove</h3>
          <ul className="fc-checks">
            {finding.checklist.map(c => <CheckRow key={c.label} met={c.met} label={c.label} ids={c.evidence} />)}
          </ul>
        </>
      )}
      <p className="page-meta">The recommendation never decides. A supervisor does.</p>
    </section>
  );
}

export function CompensationCard({ view }) {
  const comp = view.compensation;
  const unmet = comp.checks.filter(c => !c.met);
  return (
    <section className="glass-card fc-card">
      <h2 className="section-title">Small-value compensation</h2>
      {comp.eligible ? (
        <>
          <div className="fc-big">{formatRupeesExact(comp.amount)}</div>
          <p className="page-meta">85% of a net loss of {formatRupeesExact(comp.net_loss)}, capped at ₹25,000</p>
          <ul className="fc-facts">
            {Object.entries(comp.split).map(([who, amount]) => (
              <li key={who} className="fc-split"><span>{SPLIT_LABELS[who] || who}</span><span>{formatRupeesExact(amount)}</span></li>
            ))}
            {comp.pay_by && <li>Pay by {formatDay(comp.pay_by)}</li>}
          </ul>
        </>
      ) : (
        <>
          <p className="page-meta">Not eligible:</p>
          <ul className="fc-checks">{unmet.map(c => <CheckRow key={c.label} met={false} label={c.label} />)}</ul>
        </>
      )}
    </section>
  );
}
