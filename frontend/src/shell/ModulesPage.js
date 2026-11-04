import React, { useEffect, useState } from 'react';
import ModuleCard from './ModuleCard';
import { fetchModules } from './shellApi';

export default function ModulesPage() {
  const [modules, setModules] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchModules().then(setModules).catch(() => setFailed(true));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Detection modules</h1>
        <div className="page-meta">What each module can do today, and what it still needs before it can do more.</div>
      </div>
      {failed && <div role="alert" className="shell-error">Could not load the modules. Check that the API is running.</div>}
      <div className="shell-grid">
        {modules?.map(m => <ModuleCard key={m.module_id} module={m} detailed />)}
      </div>
    </div>
  );
}
