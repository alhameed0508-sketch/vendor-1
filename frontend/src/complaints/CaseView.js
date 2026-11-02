import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../auth/AuthContext';
import { formatAmount } from '../utils/formatAmount';
import { CompensationCard, ClockCard, RecommendationCard } from './CaseCards';
import { downloadPack, getComplaint } from './complaintsApi';
import DecisionPanel from './DecisionPanel';
import EvidenceForm from './EvidenceForm';
import { CHANNEL, SOURCE, canWrite, formatWhen } from './labels';
import LiveWorkflow from './LiveWorkflow';
import Narrative from './Narrative';

export const POLL_MS = 5000;

/** One complaint. While it is open the page polls, so evidence a partner posts shows up on its own. */
export default function CaseView() {
  const { complaintId } = useParams();
  const { user } = useAuth();
  const role = user?.role;
  const [view, setView] = useState(null);
  const [error, setError] = useState('');
  const [fresh, setFresh] = useState(new Set());
  const known = useRef(null);

  const accept = useCallback(next => {
    const ids = next.evidence.map(e => e.id);
    if (known.current) {
      const arrived = next.evidence.filter(e => !known.current.has(e.id));
      if (arrived.length) {
        setFresh(new Set(arrived.map(e => e.id)));
        arrived.forEach(e => toast(`New evidence from ${SOURCE[e.source] || e.source}`, { description: e.summary }));
      }
    }
    known.current = new Set(ids);
    setView(next);
  }, []);

  const load = useCallback(() => getComplaint(complaintId).then(accept).catch(err => setError(err.message)),
    [complaintId, accept]);

  useEffect(() => {
    known.current = null;
    setView(null);
    load();
  }, [load]);

  const open = view?.status === 'OPEN';
  useEffect(() => {
    if (!open) return undefined;
    const timer = setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => clearInterval(timer);
  }, [open, load]);

  const download = format => downloadPack(complaintId, format).catch(err => toast.error(err.message));

  if (error && !view) {
    return (
      <div className="page">
        <Link to="/complaints" className="fc-back"><ArrowLeft size={14} aria-hidden /> All complaints</Link>
        <p role="alert" className="fc-error">{error}</p>
      </div>
    );
  }
  if (!view) return <div className="page"><div className="loading"><div className="spinner" />Loading complaint…</div></div>;

  return (
    <div className="page">
      <Link to="/complaints" className="fc-back"><ArrowLeft size={14} aria-hidden /> All complaints</Link>
      <div className="page-header">
        <div>
          <h1>{view.customer_name}</h1>
          <p className="page-meta">
            {view.complaint_id}, {formatAmount(view.amount)} by {CHANNEL[view.channel] || view.channel},
            reported {formatWhen(view.reported_at)}{view.status === 'RESOLVED' && ', decided'}
          </p>
        </div>
        {canWrite(role) && (
          <div className="page-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => download('pdf')}>
              <Download size={14} aria-hidden /> Evidence pack (PDF)
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => download('json')}>JSON</button>
          </div>
        )}
      </div>

      <div className="grid-detail">
        <div className="fc-column">
          <LiveWorkflow view={view} fresh={fresh} />
          <Narrative complaintId={view.complaint_id} chainHead={view.evidence[view.evidence.length - 1].hash} />
        </div>
        <div className="fc-column">
          <ClockCard view={view} />
          <RecommendationCard view={view} />
          <DecisionPanel view={view} role={role} onDecided={accept} />
          <CompensationCard view={view} />
          <EvidenceForm view={view} role={role} onAdded={accept} />
        </div>
      </div>
    </div>
  );
}
