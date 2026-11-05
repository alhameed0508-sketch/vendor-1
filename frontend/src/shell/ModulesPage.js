import React, { useEffect, useState } from 'react';
import LivePrevention from './LivePrevention';
import ModuleSummary from './ModuleSummary';
import { fetchModuleFindings, fetchModules } from './shellApi';

// The findings follow the live payments above, so they refresh while the page is open.
export const REFRESH_MS = 10000;

/** Detection modules: real live data first, then what each module finds in the live public payments. */
export default function ModulesPage() {
  const [modules, setModules] = useState(null);
  const [findings, setFindings] = useState({});
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchModules()
      .then(list => { if (alive) setModules(list); })
      .catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!modules) return undefined;
    let alive = true;
    const load = () => modules.forEach(m => {
      fetchModuleFindings(m.module_id, 'live')
        .then(f => alive && setFindings(prev => ({ ...prev, [m.module_id]: f })))
        .catch(() => alive && setFindings(prev => ({ ...prev, [m.module_id]: { kind: 'error' } })));
    });
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => { alive = false; clearInterval(timer); };
  }, [modules]);

  const seen = Math.max(0, ...Object.values(findings).map(f => f?.live_payments || 0));
  return (
    <div className="page">
      <div className="page-header">
        <h1>Detection modules</h1>
        <div className="page-meta">Real live data, and what each module finds in it.</div>
      </div>
      <LivePrevention />
      {failed && <div role="alert" className="shell-error">Could not load the modules. Check that the API is running.</div>}
      <h2 className="shell-section-title">Modules</h2>
      <div role="status" className="shell-notice">
        {seen > 0
          ? `Findings below come from the last ${seen.toLocaleString('en-IN')} real public payments streamed above. No synthetic data.`
          : 'Findings appear here as real public payments stream in above. No synthetic data.'}
      </div>
      <div className="shell-grid">
        {modules?.map(m => <ModuleSummary key={m.module_id} module={m} findings={findings[m.module_id]} />)}
      </div>
    </div>
  );
}
