import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { alertPath } from '../utils/safeNavigation';
import { roleLabel } from './graphModel';

export function riskLabel(score = 0) {
  if (score < 0.25) return 'Low';
  if (score < 0.45) return 'Medium';
  if (score < 0.65) return 'High';
  return 'Critical';
}

export default function NodeDetailPanel({ node, onClose, reasons = [] }) {
  useEffect(() => {
    if (!node) return undefined;
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [node, onClose]);

  if (!node) return null;
  const score = node.smurf_score || 0;

  return (
    <aside className="node-panel glass-card" aria-label="Account details">
      <div className="node-panel-head">
        <p className="node-panel-role">{roleLabel(node.role)} account</p>
        <button type="button" className="btn btn-ghost btn-sm" aria-label="Close" onClick={onClose}>×</button>
      </div>
      <p className="node-panel-id">{node.account_id}</p>
      <dl className="node-panel-fields">
        <dt>Risk</dt>
        <dd>{riskLabel(score)}, {Math.round(score * 100)}%</dd>
        {node.bank && (<><dt>Bank</dt><dd>{node.bank}</dd></>)}
        {node.city && (<><dt>City</dt><dd>{node.city}</dd></>)}
      </dl>
      {reasons.length > 0 && (
        <>
          <h3 className="node-panel-why">Why flagged</h3>
          <ul className="node-panel-reasons">
            {reasons.map(reason => <li key={reason}>{reason}</li>)}
          </ul>
        </>
      )}
      {node.alert_id && (
        <Link className="btn btn-primary btn-sm" to={alertPath(node.alert_id)}>Open alert</Link>
      )}
    </aside>
  );
}
