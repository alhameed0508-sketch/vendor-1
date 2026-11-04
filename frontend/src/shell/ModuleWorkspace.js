import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Capabilities } from './ModuleCard';
import StatusBadge from './StatusBadge';
import { fetchModule } from './shellApi';
import './shell.css';

// The mule module's pages already exist; the workspace gathers them under the module's name.
const PAGES = {
  mule: [
    { path: '/', label: 'Alerts' },
    { path: '/queue', label: 'Triage' },
    { path: '/network', label: 'Network' },
    { path: '/live', label: 'Live stream' },
  ],
};

/** One module: its status, what it can and cannot do, and the pages it owns. */
export default function ModuleWorkspace() {
  const { moduleId } = useParams();
  const [module, setModule] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setModule(null);
    setFailed(false);
    fetchModule(moduleId).then(setModule).catch(() => setFailed(true));
  }, [moduleId]);

  const pages = module?.workspace_path ? PAGES[moduleId] || [] : [];
  return (
    <div className="page">
      <Link className="shell-back" to="/command-center">← Command center</Link>
      {failed && <div role="alert" className="shell-error">Could not find this module.</div>}
      {module && (
        <>
          <div className="page-header">
            <h1>{module.name}</h1>
            <StatusBadge status={module.status} />
            <div className="page-meta">{module.purpose}</div>
          </div>
          {pages.length > 0 && (
            <nav aria-label="Module pages" className="shell-grid">
              {pages.map(p => <Link key={p.path} className="premium-card shell-module__link" to={p.path}>{p.label}</Link>)}
            </nav>
          )}
          <details className="shell-details" open={pages.length === 0}>
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
