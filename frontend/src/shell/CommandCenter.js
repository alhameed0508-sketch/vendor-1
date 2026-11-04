import React, { useEffect, useState } from 'react';
import LivePrevention from './LivePrevention';
import ModuleCard from './ModuleCard';
import { fetchCommandCenter } from './shellApi';

function Stat({ label, value }) {
  return (
    <div className="premium-card">
      <div className="meta-label">{label}</div>
      <div className="data-value">{value}</div>
    </div>
  );
}

export default function CommandCenter() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchCommandCenter().then(setData).catch(() => setFailed(true));
  }, []);

  const severity = data?.alerts.by_severity || {};
  return (
    <div className="page">
      <div className="page-header">
        <h1>Command center</h1>
      </div>
      <LivePrevention />
      {failed && <div role="alert" className="shell-error">Could not load the Command center. Check that the API is running.</div>}
      {data?.data_source === 'synthetic' && (
        <div role="status" className="shell-notice">
          Synthetic demonstration data: generated for this demo, not taken from a bank.
        </div>
      )}
      {data && (
        <>
          <div className="shell-stats">
            <Stat label="Alerts" value={data.alerts.total} />
            <Stat label="Critical" value={severity.CRITICAL || 0} />
            <Stat label="High" value={severity.HIGH || 0} />
            <Stat label="Pending escalations" value={data.escalations.pending} />
          </div>
          <div className="shell-grid">
            {data.modules.map(m => <ModuleCard key={m.module_id} module={m} />)}
          </div>
        </>
      )}
    </div>
  );
}
