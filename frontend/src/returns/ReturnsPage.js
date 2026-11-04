import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { formatAmount } from '../utils/formatAmount';
import DemoTour from './DemoTour';
import { FailedNotice, StaleNotice } from './Notices';
import { isOutage, recall, remember } from './lastGood';
import { TierChip } from './TierChip';
import { getOverview, listClaims } from './returnsApi';
import { SIGNAL, SIGNAL_ORDER } from './labels';
import './returns.css';

export const summarise = ({ needs_review: needs, by_tier: tiers, amount_in_question: amount }) => {
  if (!needs) return 'No returns need a person right now.';
  const desk = tiers.BLOCK;
  return `${needs} return${needs === 1 ? ' needs' : 's need'} a person. ${
    desk ? `${desk} ${desk === 1 ? 'is' : 'are'} headed for the fraud desk. ` : ''}${formatAmount(amount)} is in question.`;
};

function HelpChip() {
  return (
    <details className="rf-help">
      <summary>How to read this</summary>
      <div className="rf-help__body">
        <p>Six checks look at each return: the photo, whether the photo fits the claim, the receipt file, the device, the customer's habits and who else is linked.</p>
        <p>One loud check never sends a case to the fraud desk. It takes agreement from at least three. A person always makes the final call.</p>
        <p>The photo-against-claim check is a simulation here: it reads labels, not pixels.</p>
      </div>
    </details>
  );
}

function GuidedEntry({ onTour, firstToReview }) {
  return (
    <div className="rf-entry">
      <button type="button" className="rf-entry__card" onClick={onTour}>
        <span className="rf-entry__title">See it work</span>
        <span className="rf-entry__text">A short tour of seven returns, from an ordinary one to a ring of five customers.</span>
      </button>
      {firstToReview
        ? <Link className="rf-entry__card" to={`/returns/${firstToReview}`}>
            <span className="rf-entry__title">Review what needs a person</span>
            <span className="rf-entry__text">Start with the return that scores highest.</span>
          </Link>
        : <div className="rf-entry__card" aria-disabled="true">
            <span className="rf-entry__title">Review what needs a person</span>
            <span className="rf-entry__text">Nothing is waiting.</span>
          </div>}
      <Link className="rf-entry__card" to="/returns/capture">
        <span className="rf-entry__title">Check a return in the field</span>
        <span className="rf-entry__text">Take a photo of the item and the receipt from a phone and get a recommendation.</span>
      </Link>
    </div>
  );
}

function Coverage({ coverage, total }) {
  return (
    <ul className="rf-coverage">
      {SIGNAL_ORDER.map(name => (
        <li key={name}>
          <strong>{SIGNAL[name]}</strong>
          Ran on {coverage[name].ran} of {total}, fired on {coverage[name].fired}.
          {name === 'vlm' && ' Simulated: it reads labels, not pixels.'}
        </li>
      ))}
    </ul>
  );
}

function ClaimsTable({ claims }) {
  if (!claims.length) return <p className="rf-empty">No return claims yet. File one from the field page or through the API.</p>;
  return (
    <table className="rf-table">
      <thead>
        <tr><th>Claim</th><th>Customer</th><th>Item</th><th className="num">Amount</th><th>Recommendation</th><th>Status</th></tr>
      </thead>
      <tbody>
        {claims.map(c => (
          <tr key={c.claim_id}>
            <td><Link to={`/returns/${c.claim_id}`}>{c.claim_id}</Link></td>
            <td>{c.customer_name}</td>
            <td>{c.item}</td>
            <td className="num">{formatAmount(c.amount)}</td>
            <td><TierChip tier={c.tier} score={c.score} /></td>
            <td>{c.tier === 'APPROVE' ? 'No action' : c.reviewed ? 'Reviewed' : 'Needs a person'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Return fraud: where claims stand, a guided way in, and every claim with its recommendation. */
export default function ReturnsPage() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [claims, setClaims] = useState(null);
  const [error, setError] = useState('');
  const [staleAt, setStaleAt] = useState(null);
  const [tour, setTour] = useState(false);
  const ledger = useRef(null);

  const load = useCallback(() => {
    setError('');
    Promise.all([getOverview(), listClaims()])
      .then(([o, l]) => { remember(user?.username, 'overview', { o, l }); setStaleAt(null); setOverview(o); setClaims(l.claims); })
      .catch(err => {
        const last = isOutage(err) && recall(user?.username, 'overview');
        if (last) { setStaleAt(last.at); setOverview(last.data.o); setClaims(last.data.l.claims); } else { setError(err.message); }
      });
  }, [user?.username]);
  useEffect(load, [load]);

  const firstToReview = useMemo(() => claims?.find(c => c.tier !== 'APPROVE' && !c.reviewed)?.claim_id, [claims]);
  const closeTour = () => { setTour(false); ledger.current?.scrollIntoView?.({ block: 'start' }); };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Return fraud</h1>
          <p className="page-meta">
            Six checks on every return, one recommendation, and a package your bank can use.
          </p>
        </div>
        <HelpChip />
      </div>

      {staleAt && <StaleNotice at={staleAt} onRetry={load} />}
      {error && <FailedNotice message={error} onRetry={load} />}
      {!overview && !error && <div className="loading"><div className="spinner" />Reading every return and its six checks…</div>}

      {overview && (
        <>
          <p className="rf-summary">{summarise(overview.summary)}</p>
          {tour
            ? <DemoTour scenarios={overview.scenarios} onClose={closeTour} />
            : <GuidedEntry onTour={() => setTour(true)} firstToReview={firstToReview} />}

          {overview.rings.map(r => (
            <div key={r.claims[0]} className="rf-section rf-ring-note">
              <span>
                <strong>A ring of {r.customers} customers</strong> share a device, an address or a card, across {r.claims.length} claims worth {formatAmount(r.amount)}.
              </span>
              <Link className="btn btn-ghost btn-sm" to={`/returns/${r.claims[r.claims.length - 1]}`}>See the ring</Link>
            </div>
          ))}

          <div className="rf-section" ref={ledger}>
            <h2>Returns</h2>
            <ClaimsTable claims={claims || []} />
          </div>

          <div className="rf-section">
            <h2>How far each check reaches</h2>
            <Coverage coverage={overview.signal_coverage} total={overview.summary.total} />
          </div>
        </>
      )}
    </div>
  );
}

