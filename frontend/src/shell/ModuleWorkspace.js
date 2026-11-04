import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { formatAmount } from '../utils/formatAmount';
import { RankBars } from './Bars';
import LivePrevention from './LivePrevention';
import { Capabilities } from './ModuleCard';
import { findingBars } from './ModuleSummary';
import StatusBadge from './StatusBadge';
import { fetchModule, fetchModuleFindings } from './shellApi';
import './shell.css';

// The mule module's own pages, kept as quick links under its workspace.
const PAGES = {
  mule: [
    { path: '/', label: 'Alerts' },
    { path: '/queue', label: 'Triage' },
    { path: '/network', label: 'Network' },
    { path: '/live', label: 'Live stream' },
  ],
};

function Tile({ label, value }) {
  return (
    <div className="premium-card">
      <div className="meta-label">{label}</div>
      <div className="data-value">{value}</div>
    </div>
  );
}

function MuleFindings({ findings }) {
  const sev = findings.alerts?.by_severity || {};
  return (
    <>
      <div className="shell-stats">
        <Tile label="Alerts" value={findings.findings_total} />
        <Tile label="Critical" value={sev.CRITICAL || 0} />
        <Tile label="High" value={sev.HIGH || 0} />
        <Tile label="Accounts in alerts" value={findings.accounts_in_alerts ?? 0} />
      </div>
      <div className="ws-grid">
        <section className="premium-card" aria-label="Alerts by severity">
          <div className="meta-label">Alerts by severity</div>
          <RankBars items={findingBars(findings)} label="Alerts by severity" />
        </section>
        <section className="premium-card shell-table__wrap" aria-label="Riskiest alerts">
          <div className="meta-label">Riskiest alerts</div>
          <table className="shell-table">
            <thead><tr><th>Alert</th><th>Severity</th><th>Risk</th><th>Accounts</th><th>Amount</th><th>Why</th></tr></thead>
            <tbody>
              {(findings.top_alerts || []).slice(0, 8).map(a => (
                <tr key={a.alert_id}>
                  <td><Link to={`/alert/${a.alert_id}`}>{a.alert_id}</Link></td>
                  <td>{a.severity}</td>
                  <td className="data-value">{Math.round((a.risk_score || 0) * 100)}%</td>
                  <td>{a.account_count}</td>
                  <td className="data-value">{formatAmount(a.total_amount || 0)}</td>
                  <td>{(a.reasons || []).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </>
  );
}

function RuleFindings({ findings, moduleName }) {
  return (
    <>
      <div className="shell-stats">
        <Tile label="Payments considered" value={findings.rows_considered} />
        <Tile label="Findings" value={findings.findings_total} />
        <Tile label="Accounts flagged" value={findings.accounts_flagged} />
        <Tile label="Signals run" value={(findings.signals_run || []).length} />
      </div>
      {findings.signals_skipped?.length > 0 && (
        <div role="status" className="shell-notice">
          Could not run on this data:{' '}
          {findings.signals_skipped.map(s => `${s.rule_code} (${s.reason})`).join('; ')}.
        </div>
      )}
      <div className="ws-grid">
        <section className="premium-card" aria-label="Findings by rule">
          <div className="meta-label">Findings by rule</div>
          {findings.by_rule?.length
            ? <RankBars items={findingBars(findings)} label={`${moduleName}: findings by rule`} />
            : <div className="mod-card__sub">Nothing found in the loaded data.</div>}
        </section>
        <section className="premium-card shell-table__wrap" aria-label="Flagged accounts">
          <div className="meta-label">Flagged accounts</div>
          <table className="shell-table">
            <thead><tr><th>Account</th><th>Rule</th><th>Why</th></tr></thead>
            <tbody>
              {(findings.findings || []).slice(0, 12).map((f, i) => (
                <tr key={`${f.account_id}-${f.rule_code}-${i}`}>
                  <td><Link to={`/entities/${encodeURIComponent(f.account_id)}`}>{f.account_id}</Link></td>
                  <td>{f.rule_code}</td>
                  <td>{f.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </>
  );
}

/** One module: what it has found, live where it can be, and what it can and cannot do. */
export default function ModuleWorkspace() {
  const { moduleId } = useParams();
  const [module, setModule] = useState(null);
  const [findings, setFindings] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setModule(null);
    setFindings(null);
    setFailed(false);
    fetchModule(moduleId).then(m => alive && setModule(m)).catch(() => alive && setFailed(true));
    fetchModuleFindings(moduleId).then(f => alive && setFindings(f)).catch(() => alive && setFindings({ kind: 'error' }));
    return () => { alive = false; };
  }, [moduleId]);

  const pages = PAGES[moduleId] || [];
  const kind = findings?.kind;
  return (
    <div className="page">
      <Link className="shell-back" to="/modules">← Detection modules</Link>
      {failed && <div role="alert" className="shell-error">Could not find this module.</div>}
      {module && (
        <>
          <div className="page-header">
            <h1>{module.name}</h1>
            <StatusBadge status={module.status} />
            <div className="page-meta">{module.purpose}</div>
          </div>
          {pages.length > 0 && (
            <nav aria-label="Module pages" className="shell-chips">
              {pages.map(p => <Link key={p.path} className="shell-chip" to={p.path}>{p.label}</Link>)}
            </nav>
          )}
          {moduleId === 'mule' && <LivePrevention />}
          {findings?.data_source === 'synthetic' && kind !== 'none' && (
            <div role="status" className="shell-notice">Findings come from synthetic demonstration data, not from a bank.</div>
          )}
          {kind === 'alerts' && <MuleFindings findings={findings} />}
          {kind === 'rules' && <RuleFindings findings={findings} moduleName={module.name} />}
          {kind === 'none' && (
            <div className="mod-card__empty">
              No findings source yet. This module needs: {(module.data_requirements || []).join(', ')}.
            </div>
          )}
          {kind === 'error' && <div role="alert" className="shell-error">Could not load this module's findings.</div>}
          <details className="shell-details" open={kind === 'none'}>
            <summary>What it can do</summary>
            <Capabilities capabilities={module.capabilities} />
            {module.data_requirements?.length > 0 && (
              <div className="shell-module__needs">
                <div className="meta-label">Data it needs</div>
                <ul>{module.data_requirements.map(n => <li key={n}>{n}</li>)}</ul>
              </div>
            )}
          </details>
        </>
      )}
    </div>
  );
}
