import React from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from './StatusBadge';
import './shell.css';

function Findings({ count }) {
  return count == null
    ? <div className="shell-module__findings">No findings source yet</div>
    : <div className="shell-module__findings"><span className="data-value">{count}</span> findings</div>;
}

function Capabilities({ capabilities }) {
  return (
    <ul className="shell-caps">
      {capabilities.map(c => (
        <li key={c.name}>
          <StatusBadge status={c.status} /> <span className="shell-caps__name">{c.name}</span>
          {c.note && <div className="shell-caps__note">{c.note}</div>}
        </li>
      ))}
    </ul>
  );
}

/** One fraud module: its honest status, what it has found, and a link only if it has a page. */
export default function ModuleCard({ module, detailed = false }) {
  const { name, purpose, status, workspace_path: path, findings, capabilities, data_requirements: needs } = module;
  return (
    <article className="premium-card shell-module">
      <header className="shell-module__head">
        <h2 className="shell-module__name">{name}</h2>
        <StatusBadge status={status} />
      </header>
      {purpose && <p className="shell-module__purpose">{purpose}</p>}
      {!detailed && <Findings count={findings} />}
      {detailed && capabilities && <Capabilities capabilities={capabilities} />}
      {detailed && needs?.length > 0 && (
        <div className="shell-module__needs">
          <div className="meta-label">Data it needs</div>
          <ul>{needs.map(n => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      {path && <Link className="shell-module__link" to={path}>Open workspace</Link>}
    </article>
  );
}
