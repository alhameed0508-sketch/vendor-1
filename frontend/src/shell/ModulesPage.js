import React, { useEffect, useState } from 'react';
import LivePrevention from './LivePrevention';
import ModuleSummary from './ModuleSummary';
import { fetchModuleFindings, fetchModules } from './shellApi';

/** Detection modules: the live money view first, then what each module has found in the loaded data. */
export default function ModulesPage() {
  const [modules, setModules] = useState(null);
  const [findings, setFindings] = useState({});
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchModules()
      .then(list => {
        if (!alive) return;
        setModules(list);
        list.forEach(m => {
          fetchModuleFindings(m.module_id)
            .then(f => alive && setFindings(prev => ({ ...prev, [m.module_id]: f })))
            .catch(() => alive && setFindings(prev => ({ ...prev, [m.module_id]: { kind: 'error' } })));
        });
      })
      .catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, []);

  const synthetic = Object.values(findings).some(f => f?.data_source === 'synthetic');
  return (
    <div className="page">
      <div className="page-header">
        <h1>Detection modules</h1>
        <div className="page-meta">Live payments, and what each module has found in the loaded data.</div>
      </div>
      <LivePrevention />
      {failed && <div role="alert" className="shell-error">Could not load the modules. Check that the API is running.</div>}
      <h2 className="shell-section-title">Modules</h2>
      {synthetic && (
        <div role="status" className="shell-notice">
          Findings below come from synthetic demonstration data, generated for this demo, not taken from a bank.
        </div>
      )}
      <div className="shell-grid">
        {modules?.map(m => <ModuleSummary key={m.module_id} module={m} findings={findings[m.module_id]} />)}
      </div>
    </div>
  );
}
