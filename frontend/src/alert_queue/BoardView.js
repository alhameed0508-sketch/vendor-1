import React from 'react';
import { BOARD_COLUMNS, groupByStatus } from './boardModel';

const DRAG_TYPE = 'text/plain';

function Card({ alert, onOpen, onMove }) {
  return (
    <div className="board-card glass-card" draggable="true"
         onDragStart={e => e.dataTransfer.setData(DRAG_TYPE, alert.alert_id)}>
      <button type="button" className="board-card-id" onClick={() => onOpen(alert.alert_id)}>
        {alert.alert_id}
      </button>
      <div className="board-card-meta">
        {alert.severity && <span className={`badge badge-${alert.severity}`}>{alert.severity}</span>}
      </div>
      <label className="board-card-move">
        <span className="sr-only">Move to</span>
        <select aria-label="Move to" value="" onChange={e => e.target.value && onMove(alert, e.target.value)}>
          <option value="">Move to…</option>
          {BOARD_COLUMNS.filter(c => c.status !== alert.status).map(c => (
            <option key={c.status} value={c.status}>{c.label}</option>
          ))}
        </select>
      </label>
    </div>
  );
}

export default function BoardView({ alerts, onMove, onOpen }) {
  const groups = groupByStatus(alerts);
  const byId = new Map(alerts.map(a => [a.alert_id, a]));
  const columns = groups.OTHER.length
    ? [...BOARD_COLUMNS, { status: 'OTHER', label: 'Other' }]
    : BOARD_COLUMNS;

  const drop = (e, toStatus) => {
    e.preventDefault();
    const alert = byId.get(e.dataTransfer.getData(DRAG_TYPE));
    if (alert && alert.status !== toStatus) onMove(alert, toStatus);
  };

  return (
    <div className="board">
      {columns.map(c => (
        <section key={c.status} className="board-column" aria-label={c.label}
                 onDragOver={e => e.preventDefault()}
                 onDrop={e => c.status !== 'OTHER' && drop(e, c.status)}>
          <header className="board-column-head">
            <span className="eyebrow">{c.label}</span>
            <span className="board-count">{groups[c.status].length}</span>
          </header>
          {groups[c.status].map(a => (
            <Card key={a.alert_id} alert={a} onOpen={onOpen} onMove={onMove} />
          ))}
        </section>
      ))}
    </div>
  );
}
