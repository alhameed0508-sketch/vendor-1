import React, { useState, useEffect, useRef } from 'react';

export default function ApprovalDialog({ alert, onConfirm, onCancel }) {
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
      setError(e?.message || 'Filing failed');
      setPending(false);
    }
  };

  return (
    <div className="approval-backdrop">
      <div className="approval-dialog glass-card" role="dialog" aria-modal="true"
           aria-labelledby="approval-title">
        <p className="eyebrow">Approval required</p>
        <h2 id="approval-title" className="approval-title">File STR for {alert.alert_id}</h2>
        <label className="approval-label" htmlFor="approval-reason">Reason for filing</label>
        <textarea id="approval-reason" ref={inputRef} className="approval-reason" rows={4}
                  value={reason} onChange={e => setReason(e.target.value)} />
        {error && <p role="alert" className="approval-error">{error}</p>}
        <div className="approval-actions">
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={pending}>Cancel</button>
          <button type="button" className="btn-primary" onClick={submit}
                  disabled={!reason.trim() || pending}>
            {pending ? 'Filing...' : 'Confirm filing'}
          </button>
        </div>
      </div>
    </div>
  );
}
