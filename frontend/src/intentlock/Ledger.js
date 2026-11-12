import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ledgerAmount } from './api';
import { LEDGER_HEAD, LedgerRows } from './ledgerParts';
import { ErrorNote, Spinner } from './parts';

const FILTERS = [['all', 'All decisions'], ['allowed', 'Allowed'], ['stopped', 'Stopped'], ['agent', 'By an assistant']];

export default function Ledger() {
  const [params, setParams] = useSearchParams();
  const scope = params.get('scope') === 'mine' ? 'mine' : 'all';
  const [filter, setFilter] = useState('all');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => { setError(null); setData(null); api.ledger(scope).then(setData).catch(setError); }, [scope]);
  useEffect(load, [load]);

  const rows = data ? data.rows.filter((r) => filter === 'all' || (filter === 'allowed' ? r.decision === 'ALLOW' : filter === 'stopped' ? r.decision !== 'ALLOW' : r.proposed_by === 'agent')) : [];
  const cur = rows[0] ? rows[0].currency : 'USD';
  const capturedTotal = rows.reduce((a, r) => a + (r.captured ? r.total_minor || 0 : 0), 0);
  const stoppedTotal = rows.reduce((a, r) => a + (r.decision !== 'ALLOW' ? r.total_minor || 0 : 0), 0);

  return (
    <div className="stack">
      <div className="page-head">
        <p className="lede" style={{ margin: 0 }}>Every proposal, in the order it was made. Refusals are posted in red with the rule that stopped them.</p>
        <div className="row">
          <div className="seg" role="group" aria-label="Whose entries">
            <button type="button" aria-pressed={scope === 'all'} onClick={() => setParams({})}>Store-wide</button>
            <button type="button" aria-pressed={scope === 'mine'} onClick={() => setParams({ scope: 'mine' })}>Mine</button>
          </div>
          <div className="seg" role="group" aria-label="Filter">
            {FILTERS.map(([k, label]) => <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}</button>)}
          </div>
        </div>
      </div>
      {error ? <ErrorNote error={error} onRetry={load} /> : !data ? <Spinner label="Loading the ledger" /> : (
        <section className="panel">
          <div className="panel-head">
            <span className="range">{rows.length ? <>Showing <span className="mono">{rows[0].ref}</span> to <span className="mono">{rows[rows.length - 1].ref}</span> · {rows.length} of {data.total} entries</> : `0 of ${data.total} entries`}</span>
            <span className="small muted">{scope === 'all' ? 'Store-wide, without typed requests. Only your own entries open.' : 'Your entries in this browser.'}</span>
          </div>
          {rows.length === 0 ? (
            <div className="empty"><h2>No entries</h2><p>{scope === 'mine' ? <>You have not proposed a purchase yet. <Link to="/new">Start one</Link>.</> : 'Nothing matches this filter.'}</p></div>
          ) : (
            <div className="table-wrap">
              <table className="ledger">
                <thead>{LEDGER_HEAD}</thead>
                <tbody><LedgerRows rows={rows} /></tbody>
                <tfoot><tr>
                  <td colSpan="5">Totals for the entries shown: captured, and refused (in red)</td>
                  <td className="amt"><span className="cap">{ledgerAmount(capturedTotal, cur, false)}</span><br /><span className="neg">{ledgerAmount(stoppedTotal, cur, true)}</span></td>
                  <td>{cur}</td>
                </tr></tfoot>
              </table>
            </div>
          )}
          {data.total > data.limit && <p className="small muted" style={{ marginTop: 10 }}>The newest {data.limit} entries are shown.</p>}
        </section>
      )}
    </div>
  );
}
