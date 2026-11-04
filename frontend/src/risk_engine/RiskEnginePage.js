import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Play, RefreshCw, Square } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../auth/AuthContext';
import ExplanationDrawer from './ExplanationDrawer';
import useRiskStream from './useRiskStream';
import {
  BAND_META, ENGINE_META, ENGINE_ORDER, SOURCE_META, formatInr, formatPct, getJson, postJson,
} from './riskApi';
import './RiskEngine.css';

const POLL_MS = 5000;
const SYSTEM_ORDER = ['unified', 'unified_no_fp_control', 'mule_only', 'static_rules'];

function Tile({ label, value, detail }) {
  return (
    <div className="re-tile">
      <span className="eyebrow">{label}</span>
      <div className="re-tile-value">{value}</div>
      {detail && <div className="re-muted">{detail}</div>}
    </div>
  );
}

function BandPill({ band }) {
  const meta = BAND_META[band] || BAND_META.APPROVE;
  return <span className="re-band" style={{ color: meta.color, borderColor: meta.color }}>{meta.label}</span>;
}

function SourcePill({ source }) {
  const meta = SOURCE_META[source];
  if (!meta) return null;
  return <span className={`re-source re-source-${source}`} title={meta.title}>{meta.label}</span>;
}

function EnginePanel({ engine, metrics }) {
  const meta = ENGINE_META[engine];
  const total = metrics?.decisions || 0;
  const active = metrics?.engine_active?.[engine] || 0;
  const codes = (metrics?.top_reasons || []).filter(([code]) => code.startsWith(meta.prefix)
    || (engine === 'behaviour' && code.startsWith('FC')));
  return (
    <section className={`re-engine${meta.core ? ' re-engine-core' : ''}`} aria-label={meta.label}>
      <div className="re-engine-head">
        <h2>{meta.label}</h2>
        {meta.core && <span className="re-core-tag">Core</span>}
      </div>
      <p className="re-muted">{meta.blurb}</p>
      <div className="re-engine-stat">
        <span className="re-tile-value">{total ? formatPct(active / total) : '—'}</span>
        <span className="re-muted">of decisions where this engine found something (score ≥ 0.4)</span>
      </div>
      {codes.length > 0 ? (
        <ul className="re-codes">
          {codes.slice(0, 4).map(([code, n]) => <li key={code}><code>{code}</code> × {n}</li>)}
        </ul>
      ) : <p className="re-muted">No reasons from this engine yet.</p>}
    </section>
  );
}

function DecisionFeed({ decisions, onOpen, selectedId }) {
  if (!decisions.length) {
    return <p className="re-muted re-empty">No decisions yet. Start the feed or run a scenario.</p>;
  }
  return (
    <div className="re-table-wrap">
      <table className="re-table">
        <thead>
          <tr><th>Decision</th><th>Payment</th><th className="re-num">Amount</th><th>Top reason</th><th>Data</th></tr>
        </thead>
        <tbody>
          {decisions.map((d) => {
            const top = (d.reasons || []).find((r) => r.kind !== 'familiarity');
            return (
              <tr key={d.decision_id} className={d.decision_id === selectedId ? 're-selected' : ''}>
                <td>
                  <button type="button" className="re-link" onClick={() => onOpen(d)}
                    aria-label={`Explain decision for ${d.customer_id} to ${d.beneficiary_id}`}>
                    <BandPill band={d.band} /> <span className="re-score-sm">{d.score}</span>
                  </button>
                </td>
                <td className="re-ellipsis" title={`${d.customer_id} → ${d.beneficiary_id}`}>
                  {d.customer_id} → {d.beneficiary_id}
                </td>
                <td className="re-num">{formatInr(d.amount)}</td>
                <td className="re-ellipsis" title={top?.text}>{top ? `${top.code} · ${top.text}` : 'Nothing unusual'}</td>
                <td><SourcePill source={d.source} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ScenarioRunner({ scenarios, onRan }) {
  const [running, setRunning] = useState(null);
  const [results, setResults] = useState({});
  const run = async (name) => {
    setRunning(name);
    try {
      const result = await postJson(`/scenarios/${name}/run`);
      setResults((prev) => ({ ...prev, [name]: result }));
      onRan(result);
    } catch (e) {
      toast.error(`Scenario failed: ${e.message}`);
    } finally {
      setRunning(null);
    }
  };
  return (
    <section className="re-panel" aria-label="Scenarios">
      <div className="re-panel-head"><h2>Worked scenarios</h2>
        <span className="re-muted">Replayed on an isolated engine with synthetic history</span></div>
      <div className="re-scenarios">
        {scenarios.map((s) => {
          const r = results[s.name];
          return (
            <article key={s.name} className="re-scenario">
              <h3>{s.title}</h3>
              <p className="re-muted">{s.story}</p>
              <p className="re-expect">Intended: <BandPill band={s.expected_band} /> {s.expected_why}</p>
              <button type="button" className="btn btn-ghost btn-sm" disabled={running !== null} onClick={() => run(s.name)}>
                <Play size={12} /> {running === s.name ? 'Running…' : 'Run'}
              </button>
              {r && (
                <div className="re-scenario-result">
                  <span>Actual: {r.decisions.map((d) => <BandPill key={d.decision_id} band={d.band} />)}</span>
                  <strong className={r.matched_expectation ? 're-ok' : 're-bad'}>
                    {r.matched_expectation ? 'As intended' : 'Did not match the intent'}
                  </strong>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function ModelPerformance({ evaluation, missing }) {
  if (missing) {
    return (
      <section className="re-panel" aria-label="Model performance">
        <div className="re-panel-head"><h2>Model performance</h2></div>
        <p className="re-muted">No offline evaluation has been run on this build.</p>
      </section>
    );
  }
  if (!evaluation) return null;
  const cell = (row, key) => {
    const v = row?.[key];
    return v ? formatPct(v.mean) : '—';
  };
  return (
    <section className="re-panel" aria-label="Model performance">
      <div className="re-panel-head"><h2>Model performance</h2>
        <span className="re-synthetic-note">Synthetic, time-separated test days</span></div>
      <p className="re-muted">{evaluation.caveat}</p>
      <div className="re-table-wrap">
        <table className="re-table">
          <thead>
            <tr><th>System</th><th className="re-num">Fraud interrupted</th><th className="re-num">Genuine interrupted</th>
              <th className="re-num">Genuine held</th><th className="re-num">REVIEW precision</th></tr>
          </thead>
          <tbody>
            {SYSTEM_ORDER.filter((k) => evaluation.systems[k]).map((k) => {
              const row = evaluation.systems[k].customer_payments;
              return (
                <tr key={k} className={k === 'unified' ? 're-selected' : ''}>
                  <td>{evaluation.systems[k].label}</td>
                  <td className="re-num">{cell(row, 'recall_interrupt')}</td>
                  <td className="re-num">{cell(row, 'genuine_interrupt_rate')}</td>
                  <td className="re-num">{cell(row, 'genuine_review_rate')}</td>
                  <td className="re-num">{cell(row, 'review_precision')}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h3 className="re-subhead">Design targets (targets, not results)</h3>
      <ul className="re-targets">
        {Object.entries(evaluation.targets).map(([key, t]) => (
          <li key={key}>{t.label}: target {t.op}{' '}
            {key === 'decision_p95_ms' ? `${t.target} ms` : formatPct(t.target)}</li>
        ))}
      </ul>
      <p className="re-muted">Model in use: {evaluation.model_used}. Generated {evaluation.generated_at}. Decision
        p95 on the evaluation machine: {evaluation.latency_decision_p95_ms_worst_seed} ms (worst seed).</p>
    </section>
  );
}

function DataSources({ feeds }) {
  if (!feeds) return null;
  return (
    <section className="re-panel" aria-label="Data sources">
      <div className="re-panel-head"><h2>Data sources</h2>
        <span className="re-muted">Every external list, with when it was fetched</span></div>
      <ul className="re-sources">
        {feeds.threat_feeds.feeds.map((f) => (
          <li key={f.name}>
            <strong>{f.label}</strong>{' '}
            {!feeds.threat_feeds.enabled ? <span className="re-muted">disabled on this server</span>
              : f.fetched_at ? <span className={f.stale ? 're-bad' : 're-ok'}>
                {f.entries.toLocaleString('en-IN')} entries, {f.age_hours} h old ({f.origin}){f.stale ? ', stale' : ''}
              </span> : <span className="re-bad">not loaded{f.error ? `: ${f.error}` : ''}</span>}
          </li>
        ))}
        {['live_payments', 'sanctions', 'complaints', 'mule_alerts'].map((k) => (
          <li key={k}><strong>{feeds[k].provider}</strong> <span className="re-muted">{feeds[k].used_by}
            {feeds[k].enabled === false ? ' (disabled on this server)' : ''}</span></li>
        ))}
      </ul>
    </section>
  );
}

export default function RiskEnginePage() {
  const { user } = useAuth();
  const [source, setSource] = useState('demo');
  const { state, start, stop } = useRiskStream({ source });
  const [metrics, setMetrics] = useState(null);
  const [recent, setRecent] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [evaluationMissing, setEvaluationMissing] = useState(false);
  const [feeds, setFeeds] = useState(null);
  const [selected, setSelected] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [m, list] = await Promise.all([getJson('/metrics'), getJson('/decisions?limit=60')]);
      setMetrics(m);
      setRecent(list.decisions || []);
    } catch (e) {
      toast.error(`Risk engine unavailable: ${e.message}`);
    }
  }, []);

  useEffect(() => {
    refresh();
    getJson('/scenarios').then((d) => setScenarios(d.scenarios || [])).catch(() => setScenarios([]));
    getJson('/evaluation').then(setEvaluation).catch(() => setEvaluationMissing(true));
    getJson('/feeds').then(setFeeds).catch(() => setFeeds(null));
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const streaming = state.status === 'streaming' || state.status === 'connecting';
  const decisions = useMemo(
    () => (source === 'live' || streaming || state.decisions.length ? state.decisions : recent),
    [source, streaming, state.decisions, recent],
  );
  const total = metrics?.decisions || 0;
  const bands = metrics?.bands || {};
  const labelled = metrics?.synthetic_labelled;
  const traffic = metrics?.demo_traffic;

  const switchSource = (next) => {
    if (next === source) return;
    stop();
    setSelected(null);
    setSource(next);
  };

  return (
    <div className="re-page page-enter">
      <header className="re-header">
        <div>
          <h1 className="text-page-title">Risk engine</h1>
          <p className="re-muted">Four engines, one decision for every payment. The mule-network core stays at the
            centre; the other three add session, payee and behaviour evidence, and the customer's own history keeps
            genuine payments flowing.</p>
        </div>
        <div className="re-controls">
          <div className="re-toggle" role="group" aria-label="Feed source">
            <button type="button" className={source === 'demo' ? 'active' : ''} onClick={() => switchSource('demo')}>
              Synthetic demo
            </button>
            <button type="button" className={source === 'live' ? 'active' : ''} onClick={() => switchSource('live')}>
              Real public payments
            </button>
          </div>
          {streaming ? (
            <button type="button" className="btn btn-ghost" onClick={stop}><Square size={13} /> Stop feed</button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={start}><Play size={13} /> Start feed</button>
          )}
          <button type="button" className="btn btn-ghost" onClick={refresh} aria-label="Refresh numbers">
            <RefreshCw size={13} />
          </button>
        </div>
      </header>

      <p className="re-status" role="status">
        {state.status === 'failed' && <span className="re-bad">Feed stopped: {state.error}</span>}
        {state.status === 'connecting' && 'Connecting…'}
        {state.status === 'streaming' && source === 'live'
          && `Scoring real Bitcoin payments from mempool.space on a private engine (${state.counters?.payments ?? 0} so far).`}
        {state.status === 'streaming' && source === 'demo'
          && `Streaming synthetic decisions${traffic ? ` (demo traffic: ${traffic.state})` : ''}.`}
        {(state.status === 'idle' || state.status === 'stopped' || state.status === 'ended')
          && (source === 'live'
            ? 'Real public payments carry no session or customer data: only the mule, payee and behaviour engines can speak.'
            : 'Showing the latest decisions. Start the feed to follow them live.')}
      </p>

      <div className="re-tiles">
        <Tile label="Decisions" value={total.toLocaleString('en-IN')} detail="since this server started" />
        <Tile label="Approved" value={total ? formatPct((bands.APPROVE || 0) / total) : '—'} />
        <Tile label="Step-up" value={total ? formatPct((bands.STEP_UP || 0) / total) : '—'} detail="verify, not block" />
        <Tile label="Review" value={total ? formatPct((bands.REVIEW || 0) / total) : '—'} detail="held for a person" />
        <Tile label="Decision p95" value={metrics?.latency_ms?.p95 != null ? `${metrics.latency_ms.p95} ms` : '—'}
          detail={`${metrics?.latency_ms?.samples || 0} samples, measured on this server`} />
        {labelled?.genuine_payments > 0 && (
          <Tile label="Genuine interrupted" value={formatPct(labelled.genuine_interrupted_rate, 2)}
            detail={`synthetic labels, ${labelled.genuine_payments.toLocaleString('en-IN')} payments`} />
        )}
      </div>

      <div className="re-engines">
        {ENGINE_ORDER.map((k) => <EnginePanel key={k} engine={k} metrics={metrics} />)}
      </div>

      <section className="re-panel" aria-label="Decision feed">
        <div className="re-panel-head"><h2>Decisions</h2>
          <span className="re-muted">Select a decision to see why</span></div>
        <DecisionFeed decisions={decisions} onOpen={setSelected} selectedId={selected?.decision_id} />
      </section>

      <ScenarioRunner scenarios={scenarios} onRan={(r) => { setSelected(r.decisions[r.decisions.length - 1]); refresh(); }} />
      <ModelPerformance evaluation={evaluation} missing={evaluationMissing} />
      <DataSources feeds={feeds} />

      {selected && (
        <ExplanationDrawer initial={selected} role={user?.role} onClose={() => setSelected(null)}
          onUpdated={() => refresh()} />
      )}
    </div>
  );
}
