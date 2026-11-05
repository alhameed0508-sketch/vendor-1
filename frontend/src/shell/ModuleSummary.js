import React from 'react';
import { Link } from 'react-router-dom';
import { RankBars } from './Bars';
import { Capabilities } from './ModuleCard';
import StatusBadge from './StatusBadge';
import './shell.css';

const SEVERITY_TONE = { CRITICAL: 'critical', HIGH: 'high', MEDIUM: 'medium' };

/** Bars for what a module found: alerts by severity (mule) or findings by rule (rule modules). */
export function findingBars(findings) {
  if (!findings) return [];
  if (findings.kind === 'alerts') {
    return ['CRITICAL', 'HIGH', 'MEDIUM']
      .map(s => ({ label: s.charAt(0) + s.slice(1).toLowerCase(), value: findings.alerts?.by_severity?.[s] || 0, tone: SEVERITY_TONE[s] }))
      .filter(i => i.value > 0);
  }
  if (findings.kind === 'rules') {
    return (findings.by_rule || []).map(r => ({ key: r.rule_code, label: `${r.rule_code} ${r.label}`, title: r.label, value: r.findings }));
  }
  return [];
}

/** The line under a rule module's count: how much data it looked at, live or loaded. */
export function rulesSub(findings) {
  const live = findings.data_source === 'live';
  if (live && !findings.live_payments) return 'waiting for live payments';
  if (!findings.rows_considered) {
    return live ? 'nothing in its scope in the live payments yet' : 'no payments in its scope in the loaded data';
  }
  const cases = findings.cases != null ? `${findings.cases} cases · ` : '';
  return `${cases}${findings.accounts_flagged} accounts across ${findings.rows_considered} ${live ? 'live ' : ''}payments`;
}

function CapabilityTally({ capabilities }) {
  const count = s => capabilities.filter(c => c.status === s).length;
  return (
    <div className="mod-card__caps">
      <span>● {count('IMPLEMENTED')} implemented</span>
      <span>◐ {count('PARTIAL')} partial</span>
      <span>○ {count('PLANNED')} planned</span>
    </div>
  );
}

/** One module on the Detection modules page: what it found, at a glance, and a way into its workspace. */
export default function ModuleSummary({ module, findings }) {
  const { name, purpose, status, workspace_path: path, capabilities = [], data_requirements: needs = [] } = module;
  const bars = findingBars(findings).slice(0, 5);
  const none = findings?.kind === 'none';
  const sub = findings?.kind === 'rules' ? rulesSub(findings) : findings?.kind === 'alerts' ? 'mule-ring alerts' : '';
  return (
    <article className="premium-card shell-module" aria-label={name}>
      <header className="shell-module__head">
        <h2 className="shell-module__name">{name}</h2>
        <StatusBadge status={status} />
      </header>
      {purpose && <p className="shell-module__purpose">{purpose}</p>}
      {!findings && <div className="mod-card__sub">Loading findings…</div>}
      {findings && !none && (
        <>
          <div className="mod-card__metric">
            <span className="data-value">{findings.findings_total}</span>
            <span className="mod-card__sub">findings{sub ? ` · ${sub}` : ''}</span>
          </div>
          {bars.length > 0
            ? <RankBars items={bars} label={`${name}: findings breakdown`} />
            : <div className="mod-card__sub">{findings.data_source === 'live' ? 'Nothing found in the live payments yet.' : 'Nothing found in the loaded data.'}</div>}
          {findings.signals_skipped?.length > 0 && (
            <div className="mod-card__sub">
              {findings.signals_skipped.length} signal{findings.signals_skipped.length > 1 ? 's' : ''} could not run on this data
              ({findings.signals_skipped.map(s => s.rule_code).join(', ')}).
            </div>
          )}
        </>
      )}
      {none && <div className="mod-card__empty">No findings source yet. Needs: {needs.join(', ')}.</div>}
      <CapabilityTally capabilities={capabilities} />
      <details className="shell-details shell-details--compact">
        <summary>What it can do</summary>
        <Capabilities capabilities={capabilities} />
        {needs.length > 0 && (
          <div className="shell-module__needs">
            <div className="meta-label">Data it needs</div>
            <ul>{needs.map(n => <li key={n}>{n}</li>)}</ul>
          </div>
        )}
      </details>
      {path && <Link className="shell-module__link" to={path}>Open workspace →</Link>}
    </article>
  );
}
