import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { SPECS, api, fromMinor, requirementEntry, requirementRow, toMinor } from './api';
import { useConfig } from './IntentLockApp';
import { DEMO_REQUEST, DEMO_TERMS, Guide, SCENARIOS, endDemo, startDemo } from './scenarios';
import { ErrorNote, MandateSummary, Spinner } from './parts';

const EXAMPLES = [
  'Buy me a new laptop with at least 16GB RAM and 512GB storage, under $1,000 including shipping and tax.',
  'A pair of new noise-cancelling headphones, at least 30 hours of battery, no more than $250 all in.',
  'I need a laptop.',
];

const localInput = (date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const inTwoDays = () => localInput(new Date(Date.now() + 48 * 3600 * 1000));
const blank = () => ({
  category: '', condition: '', quantity: '1', model: '', requirements: [], budget: '', includeShipping: true, includeTax: true,
  sellerMode: 'allowlist', substitution: false, expires: inTwoDays(),
});

function formFrom(m) {
  return {
    category: m.product.category || '', condition: m.product.condition || '', quantity: String(m.product.quantity || 1), model: m.product.model || '',
    requirements: Object.entries(m.product.requirements || {}).map(([name, value]) => requirementRow(name, value)),
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
  form.requirements.forEach((row) => {
    const entry = requirementEntry(row);
    if (!entry) return;
    if (entry.error) errors.requirements = entry.error;
    else requirements[entry[0]] = entry[1];
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

function RequirementRow({ row, onChange, onRemove }) {
  const spec = SPECS.find((s) => s.key === row.key);
  return (
    <div className="req-row">
      <select aria-label="Requirement" value={row.key} onChange={(e) => onChange({ key: e.target.value, name: '', value: e.target.value === 'noise_cancelling' ? 'true' : '' })}>
        {SPECS.map((s) => <option key={s.key} value={s.key}>{s.label}: {s.phrase}</option>)}
        <option value="custom">Something else</option>
      </select>
      {!spec ? (
        <span className="req-custom">
          <input type="text" aria-label="Requirement name" placeholder="name, e.g. colour" value={row.name} onChange={(e) => onChange({ ...row, name: e.target.value })} />
          <input type="text" aria-label="Requirement value" placeholder="value" value={row.value} onChange={(e) => onChange({ ...row, value: e.target.value })} />
        </span>
      ) : spec.kind === 'flag' ? <span className="small muted req-unit">must be included</span> : (
        <span className="req-value">
          <input type="text" inputMode="decimal" aria-label={`${spec.label} ${spec.phrase}, in ${spec.unit}`} className="num" value={row.value}
            placeholder={spec.kind === 'tenths' ? '14' : '16'} onChange={(e) => onChange({ ...row, value: e.target.value })} />
          <span className="small muted req-unit">{spec.unit}</span>
        </span>
      )}
      <button type="button" className="btn small" aria-label="Remove requirement" onClick={onRemove}>Remove</button>
    </div>
  );
}

export default function IntentStudio() {
  const config = useConfig();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const editingId = params.get('m');
  const [text, setText] = useState('');
  const [form, setForm] = useState(blank);
  const [errors, setErrors] = useState({});
  const [note, setNote] = useState(null); // AI assumptions, questions, problems
  const [source, setSource] = useState('manual');
  const [saved, setSaved] = useState(null);
  const [editing, setEditing] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const formRef = useRef(null);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const setReqs = (requirements) => set({ requirements });

  useEffect(() => {
    if (!editingId) return;
    api.intent(editingId).then((v) => { setSaved(v); setForm(formFrom(v.mandate)); setText(v.original_request || ''); setSource(v.source); setEditing(true); }).catch(setError);
  }, [editingId]);

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

  const submit = async (theForm, theText, theSource, busyKey = 'save') => {
    const built = build(theForm, config);
    setErrors(built.errors || {});
    if (built.errors) return;
    setBusy(busyKey); setError(null);
    try {
      const view = saved ? await api.changeIntent(saved.mandate_id, built.mandate) : await api.saveIntent(theText, theSource, built.mandate);
      setSaved(view); setEditing(false);
      window.scrollTo({ top: 0 });
    } catch (e) { setError(e); } finally { setBusy(''); }
  };

  // Guided demo: fill in a known request and go straight to the review step. The buyer still confirms by hand.
  const runDemo = (scenario) => {
    startDemo(scenario.id);
    const terms = { ...DEMO_TERMS, expires: inTwoDays() };
    setText(DEMO_REQUEST); setForm(terms); setSource('manual'); setNote(null);
    submit(terms, DEMO_REQUEST, 'manual', `demo-${scenario.id}`);
  };

  // A scenario from the Demo page arrives as ?demo=<id>: fill in the known request and go to the review step once.
  const demoId = params.get('demo');
  const ranDemo = useRef(null);
  useEffect(() => {
    const sc = SCENARIOS.find((s) => s.id === demoId);
    if (!sc || ranDemo.current === demoId) return;
    ranDemo.current = demoId;
    runDemo(sc);
  }, [demoId]); // runs once per scenario id; runDemo reads the latest state

  const confirm = async () => {
    setBusy('confirm'); setError(null);
    try {
      const view = await api.confirmIntent(saved.mandate_id, saved.canonical_hash);
      navigate(`/mandates/${view.mandate_id}`);
    } catch (e) { setError(e); setBusy(''); }
  };

  const bad = (k) => (errors[k] ? 'bad' : '');
  const hint = (k) => errors[k] && <div className="small" style={{ color: 'var(--block)' }}>{errors[k]}</div>;

  if (saved && !editing) {
    return (
      <div className="stack" style={{ maxWidth: 760 }}>
        <Guide page="review" />
        <div>
          <h2 className="h-large">Is this exactly what the assistant may buy?</h2>
          <p className="lede">Once you confirm, these terms are locked. The assistant cannot change them, and nothing is captured unless the final PayPal order matches them.</p>
        </div>
        <div className="card stack">
          {saved.original_request && <div><div className="lbl">You asked</div><p>“{saved.original_request}”</p></div>}
          <MandateSummary view={saved} />
        </div>
        <ErrorNote error={error} />
        <div className="row">
          <button className="btn primary" onClick={confirm} disabled={!!busy}>{busy === 'confirm' ? <Spinner label="Confirming" /> : 'Confirm and lock this mandate'}</button>
          <button className="btn" onClick={() => { endDemo(); setEditing(true); }} disabled={!!busy}>Edit</button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div ref={formRef}>
        <h2 className="h-large">{editingId ? 'Change your mandate' : 'Tell the assistant what it may buy'}</h2>
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
          <div className="field-grid basics">
            <div><label htmlFor="cat">Product type</label>
              <input id="cat" type="text" list="categories" className={bad('category')} value={form.category} onChange={(e) => set({ category: e.target.value })} placeholder="laptop" />
              <datalist id="categories"><option value="laptop" /><option value="headphones" /></datalist>{hint('category')}</div>
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
            <span className="lbl">Must-haves</span>
            {form.requirements.length === 0 && <p className="small muted">None yet. Add what the product must have, such as memory or battery life.</p>}
            {form.requirements.map((r, i) => (
              <RequirementRow key={i} row={r} onChange={(next) => setReqs(form.requirements.map((x, j) => (j === i ? next : x)))}
                onRemove={() => setReqs(form.requirements.filter((_, j) => j !== i))} />
            ))}
            <div><button type="button" className="btn small" onClick={() => {
              const free = SPECS.find((s) => !form.requirements.some((r) => r.key === s.key));
              setReqs([...form.requirements, { key: free ? free.key : 'custom', name: '', value: free && free.kind === 'flag' ? 'true' : '' }]);
            }}>Add a must-have</button></div>
            {hint('requirements')}
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
          <div><button className="btn primary" onClick={() => { endDemo(); submit(form, text, source); }} disabled={!!busy}>{busy === 'save' ? <Spinner label="Saving" /> : 'Review the mandate'}</button></div>
        </section>
      </div>
    </div>
  );
}
