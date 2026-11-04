import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StatCard from '../components/StatCard';
import { formatAmount, formatRupeesExact } from '../utils/formatAmount';
import { ClockBar } from './CaseCards';
import { listComplaints } from './complaintsApi';
import { CATEGORY, CHANNEL, FLAG, OUTCOME, clockLabel, formatWhen } from './labels';

const DAY_MS = 24 * 60 * 60 * 1000;

function CaseRow({ c }) {
  const outcome = OUTCOME[c.outcome];
  const open = c.status === 'OPEN';
  return (
    <li>
      <Link to={`/complaints/${encodeURIComponent(c.complaint_id)}`} className="fc-row">
        <div>
          <div className="fc-row__title">{c.customer_name}</div>
          <div className="page-meta">{c.complaint_id}, {formatAmount(c.amount)} by {CHANNEL[c.channel] || c.channel}</div>
        </div>
        <div>
          <div>{CATEGORY[c.category]}</div>
          <div className="fc-chips">
            <span className="fc-chip" style={{ color: outcome?.colour }}>{outcome?.label}</span>
            {c.flags.map(f => <span key={f} className="fc-chip fc-chip--warn">{FLAG[f] || f}</span>)}
          </div>
        </div>
        <div>
          <div className="fc-row__clock" style={{ color: open && c.overdue ? 'var(--critical)' : undefined }}>
            {open ? clockLabel(c) : 'Decided'}
          </div>
          <ClockBar daysLeft={c.days_left} limit={c.resolution_limit_days} overdue={open && c.overdue} />
        </div>
      </Link>
    </li>
  );
}

/** The bank's fraud complaint desk: every complaint on its RBI clock, most urgent first. */
export default function ComplaintsPage() {
  const [desk, setDesk] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    listComplaints().then(setDesk).catch(err => setError(err.message));
  }, []);

  const s = desk?.summary;
  const demoClock = desk && new Date(desk.as_of) - Date.now() > DAY_MS;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Fraud complaints</h1>
          <p className="page-meta">
            Every complaint on its RBI clock, with the evidence, the recommendation and the pack for the ombudsman.
            {desk && ` Desk clock ${formatWhen(desk.as_of)} IST${demoClock ? ', a demo date after the rules start on 1 Jan 2027' : ''}.`}
          </p>
        </div>
      </div>

      {error && <p role="alert" className="fc-error">{error}</p>}
      {!desk && !error && <div className="loading"><div className="spinner" />Loading complaints…</div>}

      {desk && (
        <>
          <div className="stat-grid">
            <StatCard label="Open" value={s.open} sub={`${formatAmount(s.amount_disputed)} disputed`} />
            <StatCard label="Overdue" value={s.overdue} sub="Past the 45 or 60-day limit" />
            <StatCard label="Due in 7 days" value={s.due_soon} sub={`${s.shadow_credits_pending} card shadow credit pending`} />
            <StatCard label="Compensation to pay" value={formatRupeesExact(s.compensation_due)}
                      sub={`${s.mule_linked} paid to a known mule`} />
          </div>
          <ul className="fc-list">{desk.cases.map(c => <CaseRow key={c.complaint_id} c={c} />)}</ul>
        </>
      )}
    </div>
  );
}
