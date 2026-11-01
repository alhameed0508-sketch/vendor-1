import React from 'react';
import { flowModel } from './flowModel';

const WIDTH = 320;
const ROW_Y = 70;
const PAD = 24;

export default function FlowView({ payments }) {
  const { nodes, links } = flowModel(payments);
  if (!nodes.length) return null;
  const step = nodes.length > 1 ? (WIDTH - PAD * 2) / (nodes.length - 1) : 0;
  const x = (id) => PAD + nodes.indexOf(id) * step;

  return (
    <svg className="live-stream__flow" viewBox={`0 0 ${WIDTH} 110`} role="img" aria-label="Money flow between ring accounts, left to right">
      {links.map((l) => {
        const mid = (x(l.from) + x(l.to)) / 2;
        const lift = 8 + Math.abs(x(l.to) - x(l.from)) / 3;
        return (
          <path
            key={l.id}
            className="live-stream__flow-link"
            d={`M ${x(l.from)} ${ROW_Y} Q ${mid} ${ROW_Y - lift} ${x(l.to)} ${ROW_Y}`}
            strokeWidth={l.width}
          />
        );
      })}
      {nodes.map((id) => (
        <g key={id}>
          <circle cx={x(id)} cy={ROW_Y} r="4" className="live-stream__flow-node" />
          <text x={x(id)} y={ROW_Y + 18} textAnchor="middle" className="live-stream__flow-label">{id}</text>
        </g>
      ))}
    </svg>
  );
}
