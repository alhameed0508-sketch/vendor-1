import React, { useState, useEffect, useRef } from 'react';

import { statusLabel } from '../utils/statusLabel';

export default function ApprovalDialog({ alert, status = 'STR_FILED', onConfirm, onCancel }) {
  const filing = status === 'STR_FILED';
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = e => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  const submit = async () => {
    setPending(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setError(e?.message || (filing ? 'Filing failed' : 'Update failed'));
      setPending(false);
    }
  };

  return (
    <div className="approval-backdrop">
      <div className="approval-dialog glass-card" role="dialog" aria-modal="true"
           aria-labelledby="approval-title">
        <p className="eyebrow">{filing ? 'Approval required' : 'Reason required'}</p>
        <h2 id="approval-title" className="approval-title">
          {filing ? `File STR for ${alert.alert_id}` : `Close ${alert.alert_id}: ${statusLabel(status)}`}
        </h2>
        <label className="approval-label" htmlFor="approval-reason">
          {filing ? 'Reason for filing' : 'Reason for decision'}
        </label>
        <textarea id="approval-reason" ref={inputRef} className="approval-reason" rows={4}
                  value={reason} onChange={e => setReason(e.target.value)} />
        {error && <p role="alert" className="approval-error">{error}</p>}
        <div className="approval-actions">
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={pending}>Cancel</button>
          <button type="button" className="btn-primary" onClick={submit}
                  disabled={!reason.trim() || pending}>
            {pending ? (filing ? 'Filing...' : 'Saving...') : (filing ? 'Confirm filing' : 'Confirm decision')}
          </button>
        </div>
      </div>
    </div>
  );
}
