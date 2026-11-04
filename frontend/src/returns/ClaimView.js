import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../auth/AuthContext';
import { formatRupeesExact } from '../utils/formatAmount';
import { Heatmap, RingGraph, Timeline } from './ClaimLayers';
import { ContributionBar, CorroborationBadge } from './ClaimScore';
import { FailedNotice, StaleNotice } from './Notices';
import { TierChip } from './TierChip';
import { isOutage, recall, remember } from './lastGood';
import { downloadPackage, getClaim, reviewClaim } from './returnsApi';
import {
  FIRED_ABOVE, REVIEW_OUTCOME, SIGNAL, SIGNAL_HELP, TIER, canReview, evidenceTime, formatWhen,
} from './labels';
import { buildRing, firedSignals, timelineEvents } from './ringModel';
import './returns.css';

const MAX_RING_COLUMNS = 8;

function Strip({ view, onDownload, busy }) {
  const { narrative, fusion } = view;
  return (
    <div className="rf-strip" aria-label="Case summary">
      <section><h2>What happened</h2><p>{narrative.what_happened}</p></section>
      <section><h2>What we found</h2><p>{narrative.what_we_found}</p></section>
      <section className="rf-strip__tier" style={{ color: TIER[fusion.tier].colour }}>
        <h2>What we recommend</h2>
        <p style={{ color: 'var(--text-primary)' }}>{narrative.what_we_recommend}</p>
        {fusion.tier !== 'APPROVE' && (
          <div className="rf-actions rf-strip__cta">
            <a className="btn btn-primary btn-sm" href="#outcome">Open for review</a>
            <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => onDownload('pdf')}>
              {busy === 'pdf' ? 'Preparing…' : 'Download evidence package'}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

const RESULT = (s) => (!s.available ? '○ Did not run' : s.score > FIRED_ABOVE ? '▲ Fired' : '● Quiet');

function Ledger({ view, onDownload, busy }) {
  const { signals, dispute_category: category, fusion } = view;
  return (
    <>
      <div className="rf-table-wrap">
        <table className="rf-table">
          <thead>
            <tr>
              <th>Check</th><th>Result</th><th className="num">Score</th><th>Evidence time</th>
              <th>Source</th><th>Also flagged by</th><th>Why</th>
            </tr>
          </thead>
          <tbody>
            {signals.map(s => (
              <tr key={s.name}>
                <td title={SIGNAL_HELP[s.name]}>{SIGNAL[s.name]}</td>
                <td>{RESULT(s)}</td>
                <td className="num">{s.available ? Math.round(s.score) : '—'}</td>
                <td>{evidenceTime(s) ? formatWhen(evidenceTime(s)) : '—'}</td>
                <td>{s.source || '—'}</td>
                <td>{s.corroborated_by?.length ? s.corroborated_by.map(n => SIGNAL[n]).join(', ') : s.available && s.score > FIRED_ABOVE ? 'No other check' : '—'}</td>
                <td>{s.reasons.join('. ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="rf-muted" style={{ marginTop: 'var(--space-3)' }}>
        {fusion.firewall} {fusion.capped_from && `This claim scored in the ${fusion.capped_from.toLowerCase()} band, but too few checks agree, so it stays at ${fusion.tier.toLowerCase()}.`}
      </p>
      <div className="rf-ledger-foot">
        <div>
          <strong>{category.label}</strong>
          <div className="rf-muted">{category.note}</div>
        </div>
        <div className="rf-actions">
          <button type="button" className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => onDownload('pdf')}>
            {busy === 'pdf' ? 'Preparing…' : 'Download bank package (PDF)'}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => onDownload('json')}>
            {busy === 'json' ? 'Preparing…' : 'Download JSON'}
          </button>
        </div>
      </div>
      <details className="rf-raw">
        <summary>Raw data, for debugging, not for review</summary>
        <pre>{JSON.stringify({ signals, fusion }, null, 2)}</pre>
      </details>
    </>
  );
}

function ReviewPanel({ view, role, onReviewed }) {
  const [outcome, setOutcome] = useState('request_proof');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (view.review) {
    const r = view.review;
    return (
      <p>
        <strong>{REVIEW_OUTCOME[r.outcome]}</strong>, recorded by {r.reviewed_by} on {formatWhen(r.reviewed_at)}.
        {r.notes && ` “${r.notes}”`}
      </p>
    );
  }
  if (!canReview(role)) {
    return <p className="rf-muted">Only a supervisor records the outcome. Nothing is refunded or blocked until they do.</p>;
  }
  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      onReviewed(await reviewClaim(view.claim.claim_id, { outcome, notes }));
      toast('Outcome recorded');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="rf-form" onSubmit={submit}>
      <label>Outcome
        <select value={outcome} onChange={e => setOutcome(e.target.value)}>
          {Object.entries(REVIEW_OUTCOME).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label>Reasons
        <textarea rows={3} maxLength={1000} value={notes} onChange={e => setNotes(e.target.value)} />
      </label>
      {error && <p role="alert" className="rf-error">{error}</p>}
      <div><button type="submit" className="btn btn-primary btn-sm" disabled={busy}>{busy ? 'Recording…' : 'Record outcome'}</button></div>
    </form>
  );
}

export default function ClaimView() {
  const { claimId } = useParams();
  const { user } = useAuth();
  const [view, setView] = useState(null);
  const [members, setMembers] = useState([]);
  const [error, setError] = useState('');
  const [cutoff, setCutoff] = useState(null);
  const [focus, setFocus] = useState(null);
  const [busy, setBusy] = useState('');
  const [playKey, setPlayKey] = useState(0);
  const [staleAt, setStaleAt] = useState(null);
  const [ringFailed, setRingFailed] = useState(false);
  const [ringTry, setRingTry] = useState(0);

  const load = useCallback(() => {
    setError('');
    getClaim(claimId)
      .then(fresh => { remember(user?.username, `claim.${claimId}`, fresh); setStaleAt(null); setView(fresh); })
      .catch(err => {
        const last = isOutage(err) && recall(user?.username, `claim.${claimId}`);
        if (last) { setStaleAt(last.at); setView(last.data); } else { setError(err.message); }
      });
  }, [claimId, user?.username]);
  useEffect(() => { setView(null); setMembers([]); setCutoff(null); setFocus(null); setStaleAt(null); load(); }, [load]);

  const ringIds = useMemo(() => view?.signals.find(s => s.name === 'graph')?.detail?.ring_claims || [], [view]);
  useEffect(() => {
    if (!view || ringIds.length < 2) return undefined;
    let live = true;
    setRingFailed(false);
    Promise.all(ringIds.slice(0, MAX_RING_COLUMNS).map(id => (id === view.claim.claim_id ? view : getClaim(id))))
      .then(rows => live && setMembers(rows))
      .catch(() => { if (live) { setMembers([view]); setRingFailed(true); } });
    return () => { live = false; };
  }, [view, ringIds, ringTry]);

  const events = useMemo(() => (view ? timelineEvents(view) : []), [view]);
  const at = cutoff ?? Math.max(events.length - 1, 0);
  const cutoffTime = events[at] ? new Date(events[at].at) : null;
  const ring = useMemo(() => buildRing(members.map(m => m.claim)), [members]);
  const columns = (members.length ? members : view ? [view] : []).map(m => ({
    id: m.claim.claim_id, label: m.claim.customer_name.split(' ')[0], signals: m.signals, returnedAt: m.claim.returned_at,
  }));

  const download = async format => {
    setBusy(format);
    try { await downloadPackage(claimId, format); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };

  if (error) {
    return (
      <div className="page">
        <FailedNotice message={error} onRetry={load} />
        <Link to="/returns">Back to return fraud</Link>
      </div>
    );
  }
  if (!view) return <div className="page"><div className="loading"><div className="spinner" />Scoring the claim against 6 checks…</div></div>;

  const c = view.claim;
  const fired = firedSignals(view).length;
  const available = view.signals.filter(s => s.available).length;
  return (
    <div className="page">
      {staleAt && <StaleNotice at={staleAt} onRetry={load} />}
      <div className="page-header">
        <div>
          <Link to="/returns" className="page-meta">Return fraud</Link>
          <h1>{c.item}, {c.customer_name}</h1>
          <p className="page-meta">
            {c.claim_id}, {formatRupeesExact(c.amount)}. {fired} of {available} checks fired.
          </p>
        </div>
        <div className="rf-verdict">
          <TierChip tier={view.fusion.tier} score={view.fusion.score} />
          <CorroborationBadge fusion={view.fusion} available={available} />
        </div>
      </div>

      <Strip view={view} onDownload={download} busy={busy} />

      {view.fusion.contributions && (
        <div className="rf-section">
          <h2>How the score adds up</h2>
          <div className="rf-panel"><ContributionBar fusion={view.fusion} /></div>
        </div>
      )}

      <div className="rf-section">
        <h2>The evidence, three ways</h2>
        <div className="rf-layers">
          <div className="rf-panel">
            <h2>When things happened</h2>
            <Timeline events={events} cutoff={at} onCutoff={setCutoff} focus={focus} />
          </div>
          <div className="rf-panel">
            <h2>How hard each check hit</h2>
            <Heatmap columns={columns} focus={focus} onFocus={setFocus} cutoffTime={cutoffTime} />
            <p className="rf-muted" style={{ marginTop: 'var(--space-2)' }}>Select a check to follow it through the timeline and the graph.</p>
          </div>
          <div className="rf-panel rf-panel--wide">
            <h2>Who is linked</h2>
            {ringFailed && (
              <p role="alert" className="rf-error">
                The linked claims could not be loaded, so only this claim is shown.{' '}
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRingTry(n => n + 1)}>Retry</button>
              </p>
            )}
            <div className="rf-phone-hide">
            <RingGraph ring={ring} selfCustomer={c.customer_id} focus={focus} cutoffTime={cutoffTime} playKey={playKey} />
            {ring.hubs.length > 0 && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPlayKey(k => k + 1)}>Replay</button>
            )}
            </div>
            <p className="rf-phone-only rf-muted">
              The graph needs a larger screen. The evidence ledger below lists the same links.
            </p>
          </div>
        </div>
      </div>

      <div className="rf-section">
        <h2>Evidence ledger</h2>
        <div className="rf-panel"><Ledger view={view} onDownload={download} busy={busy} /></div>
      </div>

      <div className="rf-section" id="outcome">
        <h2>Outcome</h2>
        <div className="rf-panel"><ReviewPanel view={view} role={user?.role} onReviewed={setView} /></div>
      </div>
    </div>
  );
}
