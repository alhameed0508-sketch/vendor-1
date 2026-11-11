import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, fromMinor, toMinor } from './api';
import { useConfig } from './IntentLockApp';
import { ErrorNote, MandateSummary, Spinner } from './parts';

const EXAMPLES = [
  'Buy me a new laptop with at least 16GB RAM and 512GB storage, under $1,000 including shipping and tax.',
  'A pair of new noise-cancelling headphones, at least 30 hours of battery, no more than $250 all in.',
  'I need a laptop.',
];
const REQUIREMENT_NAMES = ['ram_gb_min', 'storage_gb_min', 'screen_in_tenths_min', 'screen_in_tenths_max', 'battery_hours_min', 'noise_cancelling'];

const localInput = (date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const blank = () => ({
  category: '', condition: '', quantity: '1', model: '', requirements: [], budget: '', includeShipping: true, includeTax: true,
  sellerMode: 'allowlist', substitution: false, expires: localInput(new Date(Date.now() + 48 * 3600 * 1000)),
});

function formFrom(m) {
  return {
    category: m.product.category || '', condition: m.product.condition || '', quantity: String(m.product.quantity || 1), model: m.product.model || '',
    requirements: Object.entries(m.product.requirements || {}).map(([name, value]) => ({ name, value: String(value) })),
    budget: fromMinor(m.spending.maximum_total_minor, m.currency), includeShipping: !!m.spending.include_shipping, includeTax: !!m.spending.include_tax,
    sellerMode: m.seller.mode, substitution: !!m.substitution.allowed, expires: localInput(new Date(m.expires_at)),
  };
}

function build(form, config) {
  const errors = {};
  const category = form.category.trim().toLowerCase();
  if (!category) errors.category = 'Say what kind of product this is.';
  if (!form.condition) errors.condition = 'Choose new, used or refurbished.';
  const quantity = Number(form.quantity);
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 99) errors.quantity = 'Quantity must be a whole number from 1 to 99.';
  const max = toMinor(form.budget, config.currency);
  if (!max) errors.budget = `Enter the most you want to spend, in ${config.currency}.`;
  const expires = new Date(form.expires);
  if (Number.isNaN(expires.getTime()) || expires <= new Date()) errors.expires = 'Choose a time in the future.';
  const requirements = {};
  form.requirements.forEach((r) => {
    const name = r.name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    const raw = r.value.trim();
    if (!name && !raw) return;
    if (!name || !raw) { errors.requirements = 'Each requirement needs a name and a value.'; return; }
    requirements[name] = /^\d+$/.test(raw) ? Number(raw) : /^(true|yes)$/i.test(raw) ? true : /^(false|no)$/i.test(raw) ? false : raw;
  });
  if (Object.keys(errors).length) return { errors };
  return {
    mandate: {
      currency: config.currency,
      product: { category, condition: form.condition, quantity, model: form.model.trim() || null, requirements },
      seller: form.sellerMode === 'any' ? { mode: 'any', approved_seller_ids: [] } : { mode: 'allowlist', approved_seller_ids: config.default_seller_ids },
      spending: { maximum_total_minor: max, include_shipping: form.includeShipping, include_tax: form.includeTax },
      substitution: { allowed: form.substitution, require_reapproval: true },
      expires_at: `${expires.toISOString().slice(0, 19)}Z`,
    },
  };
}

export default function IntentStudio() {
  const config = useConfig();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [text, setText] = useState('');
  const [form, setForm] = useState(blank);
  const [errors, setErrors] = useState({});
  const [note, setNote] = useState(null); // AI assumptions, questions, problems
  const [source, setSource] = useState('manual');
  const [saved, setSaved] = useState(null);
  const [editing, setEditing] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    const id = params.get('m');
    if (!id) return;
    api.intent(id).then((v) => { setSaved(v); setForm(formFrom(v.mandate)); setText(v.original_request || ''); setSource(v.source); setEditing(true); }).catch(setError);
  }, [params]);

  const draft = async () => {
    setBusy('parse'); setError(null); setNote(null);
    try {
      const out = await api.parse(text);
      setForm(formFrom({ ...out.draft, product: { ...out.draft.product, category: out.draft.product.category || '', condition: out.draft.product.condition || '' } }));
      setNote(out); setSource('ai'); setErrors({});
    } catch (e) {
      setError(e.code === 'AI_UNAVAILABLE' ? { message: `${e.message}. You can fill in the form below by hand; nothing is lost.` } : e);
    } finally { setBusy(''); }
  };

  const save = async () => {
    const built = build(form, config);
    setErrors(built.errors || {});
    if (built.errors) return;
    setBusy('save'); setError(null);
    try {
      const view = saved ? await api.changeIntent(saved.mandate_id, built.mandate) : await api.saveIntent(text, source, built.mandate);
      setSaved(view); setEditing(false);
    } catch (e) { setError(e); } finally { setBusy(''); }
  };

  const confirm = async () => {
    setBusy('confirm'); setError(null);
    try {
      const view = await api.confirmIntent(saved.mandate_id, saved.canonical_hash);
      navigate(`/mandate/${view.mandate_id}`);
    } catch (e) { setError(e); setBusy(''); }
  };

  const bad = (k) => (errors[k] ? 'bad' : '');
  const hint = (k) => errors[k] && <div className="small" style={{ color: 'var(--block)' }}>{errors[k]}</div>;

  if (saved && !editing) {
    return (
      <div className="stack" style={{ maxWidth: 760 }}>
        <div>
          <p className="eyebrow">Review before you confirm</p>
          <h1>Is this exactly what the assistant may buy?</h1>
          <p className="lede">Once you confirm, these terms are locked. The assistant cannot change them, and nothing is captured unless the final PayPal order matches them.</p>
        </div>
        <div className="card stack">
          {saved.original_request && <div><div className="lbl">You asked</div><p>“{saved.original_request}”</p></div>}
          <MandateSummary view={saved} />
        </div>
        <ErrorNote error={error} />
        <div className="row">
          <button className="btn primary" onClick={confirm} disabled={!!busy}>{busy === 'confirm' ? <Spinner label="Confirming" /> : 'Confirm and lock this mandate'}</button>
          <button className="btn" onClick={() => setEditing(true)} disabled={!!busy}>Edit</button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <p className="eyebrow">Step 1</p>
        <h1>Tell the assistant what it may buy</h1>
        <p className="lede">Describe the purchase in your own words. The AI turns it into a draft; you check every line and confirm it. The AI never approves a payment.</p>
      </div>
      <div className="split">
        <section className="card stack" aria-labelledby="ask">
          <h2 id="ask">Your request</h2>
          <div>
            <label htmlFor="req">What do you want to buy, and what are your limits?</label>
            <textarea id="req" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000}
              placeholder="For example: a new laptop with at least 16GB RAM, under $1,000 including shipping and tax" />
          </div>
          <div className="chips" aria-label="Examples">
            {EXAMPLES.map((x) => <button key={x} type="button" className="chip" onClick={() => setText(x)}>{x.length > 58 ? `${x.slice(0, 56)}…` : x}</button>)}
          </div>
          <div className="row">
            <button className="btn primary" onClick={draft} disabled={!!busy || text.trim().length < 3 || !config.ai_enabled}>
              {busy === 'parse' ? <Spinner label="Reading your request" /> : 'Draft the mandate with AI'}
            </button>
            {!config.ai_enabled && <span className="small muted">AI drafting is not configured on this instance. Fill in the form by hand.</span>}
          </div>
          {note && (
            <div className="stack-s">
              {note.problems.map((p) => <div key={p} className="notice err">{p}</div>)}
              {note.questions.length > 0 && (
                <div className="notice info"><b>The assistant needs to know:</b>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{note.questions.map((q) => <li key={q}>{q}</li>)}</ul>
                </div>
              )}
              {note.assumptions.length > 0 && (
                <div className="notice"><b>Not stated in your request, so these defaults were used. Change them if they are wrong:</b>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{note.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
                </div>
              )}
              <p className="small muted">Drafted by {note.model}. Nothing is saved or authorised yet.</p>
            </div>
          )}
        </section>

        <section className="card stack" aria-labelledby="terms">
          <div className="row between"><h2 id="terms">Mandate terms</h2><span className="badge plain">{saved ? `Editing v${saved.version}` : 'Draft'}</span></div>
          <div className="field-grid">
            <div><label htmlFor="cat">Product type</label>
              <input id="cat" type="text" className={bad('category')} value={form.category} onChange={(e) => set({ category: e.target.value })} placeholder="laptop" />{hint('category')}</div>
            <div><span className="lbl" id="cond">Condition</span>
              <div className="seg" role="group" aria-labelledby="cond">
                {['new', 'used', 'refurbished'].map((c) => <button key={c} type="button" aria-pressed={form.condition === c} onClick={() => set({ condition: c })}>{c}</button>)}
              </div>{hint('condition')}</div>
            <div><label htmlFor="qty">Quantity</label>
              <input id="qty" type="number" min="1" max="99" className={bad('quantity')} value={form.quantity} onChange={(e) => set({ quantity: e.target.value })} />{hint('quantity')}</div>
          </div>
          <div><label htmlFor="model">Exact model (optional)</label>
            <input id="model" type="text" value={form.model} onChange={(e) => set({ model: e.target.value })} placeholder="Leave empty unless you want one specific model" /></div>

          <div className="stack-s">
            <span className="lbl">Must-have specifications</span>
            {form.requirements.map((r, i) => (
              <div className="req-row" key={i}>
                <input type="text" list="req-names" aria-label="Requirement name" value={r.name} placeholder="ram_gb_min"
                  onChange={(e) => set({ requirements: form.requirements.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })} />
                <input type="text" aria-label="Requirement value" value={r.value} placeholder="16"
                  onChange={(e) => set({ requirements: form.requirements.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)) })} />
                <button type="button" className="btn small" aria-label="Remove requirement" onClick={() => set({ requirements: form.requirements.filter((_, j) => j !== i) })}>Remove</button>
              </div>
            ))}
            <datalist id="req-names">{REQUIREMENT_NAMES.map((n) => <option key={n} value={n} />)}</datalist>
            <div><button type="button" className="btn small" onClick={() => set({ requirements: [...form.requirements, { name: '', value: '' }] })}>Add a requirement</button></div>
            {hint('requirements')}
            <p className="small muted">Names ending in _min or _max compare numbers. Screen size is in tenths of an inch (14 in = 140).</p>
          </div>

          <div className="field-grid">
            <div><label htmlFor="budget">Maximum total ({config.currency})</label>
              <input id="budget" type="text" inputMode="decimal" className={`num ${bad('budget')}`} value={form.budget} onChange={(e) => set({ budget: e.target.value })} placeholder="1000.00" />{hint('budget')}</div>
            <div><label htmlFor="exp">Mandate expires</label>
              <input id="exp" type="datetime-local" className={bad('expires')} value={form.expires} onChange={(e) => set({ expires: e.target.value })} />{hint('expires')}</div>
          </div>
          <div className="stack-s">
            <label className="check"><input type="checkbox" checked={form.includeShipping} onChange={(e) => set({ includeShipping: e.target.checked })} />The budget includes shipping</label>
            <label className="check"><input type="checkbox" checked={form.includeTax} onChange={(e) => set({ includeTax: e.target.checked })} />The budget includes tax</label>
            <label className="check"><input type="checkbox" checked={form.sellerMode === 'allowlist'} onChange={(e) => set({ sellerMode: e.target.checked ? 'allowlist' : 'any' })} />
              Buy only from this store's approved seller ({config.default_seller_ids.join(', ')})</label>
            <label className="check"><input type="checkbox" checked={form.substitution} onChange={(e) => set({ substitution: e.target.checked })} />
              Allow a different model if I named one</label>
          </div>
          <ErrorNote error={error} />
          <div><button className="btn primary" onClick={save} disabled={!!busy}>{busy === 'save' ? <Spinner label="Saving" /> : 'Review the mandate'}</button></div>
        </section>
      </div>
    </div>
  );
}
