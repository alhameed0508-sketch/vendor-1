import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { TierChip } from './TierChip';
import { fileClaim } from './returnsApi';
import './returns.css';

const toBase64 = file => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result).split(',')[1]);
  reader.onerror = () => reject(new Error('Could not read that file'));
  reader.readAsDataURL(file);
});

const EMPTY = { customer_id: '', customer_name: '', item: '', amount: '', reason_text: '', delivered_at: '', returned_at: '' };
const iso = local => (local ? new Date(local).toISOString() : '');

/** A phone-friendly form for field agents: photograph the item and the receipt, get a recommendation. */
export default function CapturePage() {
  const [form, setForm] = useState(EMPTY);
  const [photo, setPhoto] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const change = e => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const body = {
        ...form, amount: Number(form.amount), delivered_at: iso(form.delivered_at), returned_at: iso(form.returned_at),
        photo_b64: photo ? await toBase64(photo) : undefined,
        receipt_pdf_b64: receipt ? await toBase64(receipt) : undefined,
      };
      setResult(await fileClaim(body));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <div className="page">
        <div className="page-header"><h1>Recommendation</h1></div>
        <div className="rf-panel rf-summary-card">
          <TierChip tier={result.fusion.tier} score={result.fusion.score} />
          <p>{result.narrative.what_we_found}</p>
          <p>{result.narrative.what_we_recommend}</p>
          <div className="rf-actions">
            <Link className="btn btn-primary btn-sm" to={`/returns/${result.claim.claim_id}`}>Open the case</Link>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setResult(null); setForm(EMPTY); setPhoto(null); setReceipt(null); }}>
              Check another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <Link to="/returns" className="page-meta">Return fraud</Link>
          <h1>Check a return</h1>
          <p className="page-meta">Photos stay with the claim. Without a photo or receipt, those checks are skipped, not passed.</p>
        </div>
      </div>
      <form className="rf-form" onSubmit={submit}>
        <label>Customer ID<input name="customer_id" required maxLength={64} value={form.customer_id} onChange={change} /></label>
        <label>Customer name<input name="customer_name" required maxLength={120} value={form.customer_name} onChange={change} /></label>
        <label>Item<input name="item" required maxLength={160} value={form.item} onChange={change} /></label>
        <label>Amount (₹)<input name="amount" type="number" min="1" step="1" required value={form.amount} onChange={change} /></label>
        <label>Reason given<textarea name="reason_text" rows={2} required maxLength={1000} value={form.reason_text} onChange={change} /></label>
        <label>Delivered<input name="delivered_at" type="datetime-local" required value={form.delivered_at} onChange={change} /></label>
        <label>Return requested<input name="returned_at" type="datetime-local" required value={form.returned_at} onChange={change} /></label>
        <label>Photo of the item
          <input type="file" accept="image/*" capture="environment" onChange={e => setPhoto(e.target.files[0] || null)} />
        </label>
        <label>Receipt
          <input type="file" accept="application/pdf,image/*" capture="environment" onChange={e => setReceipt(e.target.files[0] || null)} />
        </label>
        {error && <p role="alert" className="rf-error">{error}</p>}
        <div><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Checking…' : 'Check this return'}</button></div>
      </form>
    </div>
  );
}
