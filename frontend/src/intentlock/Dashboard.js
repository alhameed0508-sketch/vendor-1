import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, codeBreaks, ledgerAmount, money, when } from './api';
import { LEDGER_HEAD, LedgerRows } from './ledgerParts';
import { ErrorNote, Spinner } from './parts';

const PERIODS = [[7, '7 days'], [14, '14 days'], [30, '30 days'], [0, 'All time']];
const SERIES = [['ALLOW', 'Allowed', 'var(--allow)'], ['BLOCK', 'Outside the mandate', 'var(--block)'], ['REAUTHORISE', 'Needs approval', 'var(--reauth)'], ['REVIEW', 'Unverified', 'var(--review)']];

function Statement({ st, currency }) {
  const allowed = st.checked - st.refused_rules;
  const notTaken = Math.max(0, allowed - st.ordered);
  const awaiting = Math.max(0, st.ordered - st.approved);
  const pending = Math.max(0, st.approved - st.refused_final - st.captured);
  const m = (v) => ledgerAmount(v, currency, false);
  const Row = ({ label, n, v, cls = '', neg }) => (
    <tr className={cls}><td className="label"><span className="leader">{label}</span></td><td className="n">{neg ? `(${n})` : n}</td><td className="v">{v ?? ''}</td></tr>
  );
  return (
    <table className="statement">
      <tbody>
        <Row label="Proposals checked" n={st.checked} />
        <Row label="Less: refused by the rules" n={st.refused_rules} neg cls="neg" v={st.refused_rules ? ledgerAmount(st.refused_rules_value_minor, currency, true) : null} />
        <tr className="sub"><td className="label">outside the mandate · needs approval · unverified</td><td className="n" colSpan="2">{st.refused_rules_by_decision.BLOCK} · {st.refused_rules_by_decision.REAUTHORISE} · {st.refused_rules_by_decision.REVIEW}</td></tr>
        <Row label="Allowed by the rules" n={allowed} cls="rule-above" />
        <Row label="Less: not taken to PayPal" n={notTaken} neg />
        <Row label="Sent to PayPal as orders" n={st.ordered} />
        <Row label="Less: not yet approved by the buyer" n={awaiting} neg />
        <Row label="Approved by the buyer in PayPal" n={st.approved} />
        <Row label="Less: refused at the final check" n={st.refused_final} neg cls="neg" v={st.refused_final ? ledgerAmount(st.refused_final_value_minor, currency, true) : null} />
        {pending > 0 && <Row label="Less: capture pending or declined" n={pending} neg />}
        <Row label="Captured" n={st.captured} v={`${currency} ${m(st.captured_minor)}`} cls="total rule-above" />
        <Row label={`Confirmed by a verified PayPal webhook${st.mismatched ? `, ${st.mismatched} mismatched` : ''}`} n={st.verified} />
      </tbody>
    </table>
  );
}

function PerDay({ days }) {
  // Drawn at the container's real width so the 11px labels stay 11px on every screen.
  const box = useRef(null);
  const [W, setW] = useState(560);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = 190, L = 26, B = 22, T = 8;
  const max = Math.max(1, ...days.map((d) => d.ALLOW + d.BLOCK + d.REAUTHORISE + d.REVIEW));
  const step = Math.max(1, Math.ceil(max / 4));
  const top = step * Math.ceil(max / step);
  const bw = (W - L) / days.length;
  const y = (v) => T + (H - T - B) * (1 - v / top);
  const every = Math.max(1, Math.ceil(46 / ((W - L) / days.length)));
  return (
    <div ref={box}><svg className="chart" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Proposals per day, split by the rules' decision">
      {Array.from({ length: top / step + 1 }, (_, i) => i * step).map((v) => (
        <g key={v}><line className={v ? 'grid' : 'base'} x1={L} x2={W} y1={y(v)} y2={y(v)} /><text x={L - 6} y={y(v) + 4} textAnchor="end">{v}</text></g>
      ))}
      {days.map((d, i) => {
        let acc = 0;
        const x = L + i * bw + bw * 0.18;
        return (
          <g key={d.day}>
            <title>{`${d.day}: ${SERIES.map(([k, label]) => `${d[k]} ${label.toLowerCase()}`).join(', ')}`}</title>
            {SERIES.map(([k, , color]) => {
              if (!d[k]) return null;
              const y0 = y(acc), y1 = y(acc + d[k]);
              acc += d[k];
              return <rect key={k} x={x} width={bw * 0.64} y={y1} height={Math.max(1, y0 - y1)} fill={color} />;
            })}
            {i % every === 0 && <text x={x + bw * 0.32} y={H - 6} textAnchor="middle">{new Date(`${d.day}T00:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })}</text>}
          </g>
        );
      })}
    </svg></div>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(14);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => { setError(null); api.overview(days).then(setData).catch(setError); }, [days]);
  useEffect(load, [load]);

  if (error && !data) return <ErrorNote error={error} onRetry={load} />;
  if (!data) return <Spinner label="Reconciling the ledger" />;
  const st = data.statement;
  const cur = data.currency;
  const stopped = st.refused_rules + st.refused_final;
  const top = data.by_rule[0];
  const ruleMax = Math.max(1, ...data.by_rule.map((r) => r.count));
  const period = days ? `the last ${days} days` : 'all time';

  return (
    <div className="stack">
      <div className="page-head">
        <p className="headline">
          {st.checked === 0 ? `No purchases were checked in ${period}.`
            : <><em>{stopped} of {st.checked}</em> proposals were stopped before any money moved.{top ? ` Most common reason: ${top.reason.toLowerCase()}.` : ''}</>}
        </p>
        <div className="seg" role="group" aria-label="Period">
          {PERIODS.map(([d, label]) => <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}>{label}</button>)}
        </div>
      </div>

      {st.checked === 0 ? (
        <div className="panel empty">
          <h2>Nothing in the ledger for {period}</h2>
          <p>Every purchase an assistant or a buyer proposes is posted here with the rules' decision.</p>
          <div className="row" style={{ justifyContent: 'center', marginTop: 14 }}><Link className="btn primary" to="/demo">Run a demo scenario</Link><Link className="btn" to="/new">Start a purchase</Link></div>
        </div>
      ) : (
        <>
          <div className="seams lead">
            <section className="panel" aria-labelledby="rec">
              <div className="panel-head"><h2 id="rec">Reconciliation</h2><span className="small">{period} · {cur} · store-wide</span></div>
              <Statement st={st} currency={cur} />
            </section>
            <section className="panel" aria-labelledby="why">
              <div className="panel-head"><h2 id="why">Why they were stopped</h2><Link className="small" to="/rules">All rules</Link></div>
              {data.by_rule.length === 0 ? <p className="muted small">Nothing was stopped in {period}.</p> : (
                <ul className="rulebars">
                  {data.by_rule.slice(0, 7).map((r) => (
                    <li key={r.rule_id}>
                      <span className="t">{r.reason}<span className="mono code">{codeBreaks(r.rule_id)}</span></span><span className="c num">{r.count}</span>
                      <span className="track"><span style={{ width: `${(r.count / ruleMax) * 100}%` }} /></span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="small muted" style={{ marginTop: 14 }}>A proposal can fail more than one rule. Rules are fixed code; the AI never decides.</p>
            </section>
          </div>

          <div className="seams three">
            <section className="panel" aria-labelledby="perday">
              <div className="panel-head"><h2 id="perday">Decisions per day</h2>
                <div className="legend">{SERIES.map(([k, label, c]) => <span key={k}><i style={{ background: c }} />{label}</span>)}</div>
              </div>
              <PerDay days={data.per_day} />
            </section>
            <section className="panel" aria-labelledby="who">
              <div className="panel-head"><h2 id="who">Who proposed</h2></div>
              {[['agent', 'AI assistant'], ['buyer', 'Buyer']].map(([k, label]) => {
                const p = data.by_proposer[k] || { total: 0, stopped: 0 };
                return (
                  <div key={k} style={{ marginBottom: 14 }}>
                    <div className="row between small"><b>{label}</b><span className="num">{p.total} proposed · <span style={{ color: 'var(--block)' }}>{p.stopped} stopped</span></span></div>
                    <div className="split-bar" aria-hidden="true">
                      <span style={{ width: `${p.total ? ((p.total - p.stopped) / p.total) * 100 : 0}%`, background: 'var(--allow)' }} />
                      <span style={{ width: `${p.total ? (p.stopped / p.total) * 100 : 0}%`, background: 'var(--block)' }} />
                    </div>
                  </div>
                );
              })}
              <p className="small muted">Assistant proposals go through the same rules as the buyer's own choices.</p>
            </section>
            <section className="panel" aria-labelledby="integrity">
              <div className="panel-head"><h2 id="integrity">Integrity</h2><Link className="small" to="/integrations">Details</Link></div>
              <dl className="facts">
                <div><dt>Audit chain</dt><dd><span className={`badge ${data.integrity.audit_intact ? 'ok' : 'bad'}`}>{data.integrity.audit_intact ? 'Intact' : 'Broken'}</span> <span className="small muted num">{data.integrity.audit_events} events</span></dd></div>
                <div><dt>Verified webhooks</dt><dd className="num">{data.integrity.webhooks_verified}</dd></div>
                <div><dt>Last webhook</dt><dd className="small">{data.integrity.last_webhook_at ? when(data.integrity.last_webhook_at) : 'none yet'}</dd></div>
                <div><dt>Confirmed mandates</dt><dd className="num">{data.mandates.confirmed} of {data.mandates.total}</dd></div>
                <div><dt>Captured</dt><dd className="num">{money(st.captured_minor, cur)}</dd></div>
              </dl>
            </section>
          </div>

          <section className="panel" aria-labelledby="latest">
            <div className="panel-head"><h2 id="latest">Latest entries</h2><Link className="small" to="/ledger">Open the ledger</Link></div>
            <div className="table-wrap">
              <table className="ledger entries"><thead>{LEDGER_HEAD}</thead><tbody><LedgerRows rows={data.recent} /></tbody></table>
            </div>
            <p className="small muted" style={{ marginTop: 10 }}>Store-wide: entries from every visitor, without their typed requests. Only your own entries open.</p>
          </section>
        </>
      )}
    </div>
  );
}
