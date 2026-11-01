import React, { useMemo, useRef } from 'react';
import { graphModel } from './graphModel';
import { forceLayout } from './forceLayout';
import './LiveGraph.css';

const VIEW = { width: 800, height: 520 };
const WARM_ITERATIONS = 30;
const LEGEND = [
  { id: 'high', label: 'Ring, high risk' },
  { id: 'review', label: 'Ring, review' },
  { id: 'account', label: 'Other account' },
];

function curve(a, b) {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const bend = 0.18;
  return `M ${a.x} ${a.y} Q ${mx - (b.y - a.y) * bend} ${my + (b.x - a.x) * bend} ${b.x} ${b.y}`;
}

function linkClass(link, selected) {
  const classes = ['live-graph__link'];
  if (link.flagged) classes.push('live-graph__link--flag');
  if (selected) classes.push(link.from === selected || link.to === selected ? 'live-graph__link--active' : 'live-graph__link--dim');
  return classes.join(' ');
}

export default function GraphCanvas({ edges, rings, stats, selected, onSelect }) {
  const { nodes, links } = useMemo(() => graphModel({ edges, rings, stats }), [edges, rings, stats]);
  const previous = useRef({});
  const positions = useMemo(() => {
    const warm = Object.keys(previous.current).length > 0;
    const next = forceLayout({
      nodes: nodes.map((n) => n.id),
      links,
      ...VIEW,
      previous: previous.current,
      ...(warm ? { iterations: WARM_ITERATIONS } : {}),
    });
    previous.current = next;
    return next;
  }, [nodes, links]);
  const neighbours = useMemo(
    () => new Set(links.filter((l) => l.from === selected || l.to === selected).flatMap((l) => [l.from, l.to])),
    [links, selected]
  );

  return (
    <div className="live-graph">
      <svg viewBox={`0 0 ${VIEW.width} ${VIEW.height}`} role="group" aria-label="Account network. Select an account to see its details.">
        {links.map((l) =>
          positions[l.from] && positions[l.to] ? (
            <path key={l.id} className={linkClass(l, selected)} d={curve(positions[l.from], positions[l.to])} strokeWidth={Math.min(1 + l.count * 0.6, 4)} />
          ) : null
        )}
        {nodes.map((n) => {
          const p = positions[n.id];
          const dim = selected && n.id !== selected && !neighbours.has(n.id);
          const select = () => onSelect(n.id === selected ? null : n.id);
          return (
            <g
              key={n.id}
              className={`live-graph__node live-graph__node--${n.category}${n.id === selected ? ' is-selected' : ''}${dim ? ' is-dim' : ''}`}
              style={{ transform: `translate(${p.x}px, ${p.y}px)` }}
              role="button"
              tabIndex={0}
              aria-label={`Account ${n.id}`}
              aria-pressed={n.id === selected}
              onClick={select}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  select();
                }
              }}
            >
              <circle r={n.radius} />
              {(n.category !== 'account' || n.id === selected) && (
                <text y={n.radius + 11} textAnchor="middle">{n.id}</text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="live-graph__legend" aria-label="Legend">
        <div className="live-graph__legend-title">Account types</div>
        {LEGEND.map((item) => (
          <div key={item.id} className="live-graph__legend-item">
            <span className={`live-graph__dot live-graph__dot--${item.id}`} aria-hidden="true" />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
