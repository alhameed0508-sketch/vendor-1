import React, { useCallback, useEffect, useState } from 'react';
import {
  fetchInvestigations, moveInvestigation, openInvestigation, requestIntervention,
} from './shellApi';
import './shell.css';

const STATUS_LABEL = {
  NEW: 'New',
  UNDER_REVIEW: 'Under review',
  INVESTIGATING: 'Investigating',
  ESCALATED: 'Escalated',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};
const OUTCOMES = [
  ['CONFIRMED', 'Confirmed'],
  ['FALSE_POSITIVE', 'False positive'],
  ['UNRESOLVED', 'Unresolved'],
];

function InvestigationCard({ item, onChange, onError }) {
  const [outcome, setOutcome] = useState('');
  const [account, setAccount] = useState('');
  const [simulated, setSimulated] = useState(null);
  const id = item.investigation_id;
  const canResolve = item.allowed_next.includes('RESOLVED');

  const guard = fn => async () => {
    onError(null);
    try { await fn(); } catch (e) { onError(e.message); }
  };
  const move = to => guard(async () => onChange(await moveInvestigation(id, to, to === 'RESOLVED' ? outcome : undefined)));
  const intervene = kind => guard(async () => setSimulated(await requestIntervention(id, kind, account)));

  return (
    <article className="premium-card investigation">
      <header className="investigation__head">
        <h2 className="investigation__case">{item.source_id}</h2>
        <span className="investigation__source">{item.source} case</span>
        <span className="status-badge">{STATUS_LABEL[item.status] || item.status}</span>
      </header>
      <div className="investigation__meta">
        {item.assignee ? `Assigned to ${item.assignee}` : 'Unassigned'}
        {item.outcome && ` · Outcome: ${item.outcome.replace('_', ' ').toLowerCase()}`}
      </div>
      {item.allowed_next.length > 0 && (
        <div role="group" aria-label="Move to" className="investigation__moves">
          {canResolve && (
            <label>
              Outcome
              <select value={outcome} onChange={e => setOutcome(e.target.value)}>
                <option value="">Choose an outcome</option>
                {OUTCOMES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          )}
          {item.allowed_next.map(to => (
            <button key={to} type="button" disabled={to === 'RESOLVED' && !outcome} onClick={move(to)}>
              {STATUS_LABEL[to] || to}
            </button>
          ))}
        </div>
      )}
      <div className="investigation__intervene">
        <label>
          Account
          <input value={account} onChange={e => setAccount(e.target.value)} />
        </label>
        <button type="button" disabled={!account} onClick={intervene('HOLD')}>Request hold</button>
        <button type="button" disabled={!account} onClick={intervene('VERIFY')}>Request verification</button>
        {simulated && <div role="status" className="investigation__simulated">{simulated.label}</div>}
      </div>
    </article>
  );
}

/** One list for alert and complaint investigations, with only the moves the server allows. */
export default function InvestigationsPage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [source, setSource] = useState('alert');
  const [caseId, setCaseId] = useState('');

  useEffect(() => {
    fetchInvestigations().then(setItems).catch(() => setError('Could not load the investigations. Check that the API is running.'));
  }, []);

  const replace = useCallback(
    updated => setItems(list => list.map(i => (i.investigation_id === updated.investigation_id ? updated : i))),
    [],
  );
  const open = async () => {
    setError(null);
    try {
      const created = await openInvestigation(source, caseId.trim());
      setItems(list => [created, ...list]);
      setCaseId('');
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Investigations</h1>
        <div className="page-meta">Alert and complaint cases follow one path. A person records the outcome; no score decides it.</div>
      </div>
      {error && <div role="alert" className="shell-error">{error}</div>}
      <div className="premium-card investigation-open">
        <label>
          Case type
          <select value={source} onChange={e => setSource(e.target.value)}>
            <option value="alert">Alert</option>
            <option value="complaint">Complaint</option>
          </select>
        </label>
        <label>
          Case ID
          <input value={caseId} onChange={e => setCaseId(e.target.value)} />
        </label>
        <button type="button" disabled={!caseId.trim()} onClick={open}>Open investigation</button>
      </div>
      {items?.map(i => <InvestigationCard key={i.investigation_id} item={i} onChange={replace} onError={setError} />)}
    </div>
  );
}
