import React from 'react';
import { roleLabel } from './graphModel';
import { LEGEND_ROLES, edgeStyle, roleStyle, shapePath } from './graphStyle';

function EdgeSwatch({ flagged }) {
  const { stroke, dash } = edgeStyle(flagged);
  return (
    <svg width={24} height={8} aria-hidden="true">
      <line x1={0} y1={4} x2={24} y2={4} stroke={stroke} strokeWidth={2} strokeDasharray={dash || undefined} />
    </svg>
  );
}

/** Key for shapes, line styles and the risk ring. */
export default function GraphLegend() {
  return (
    <div className="graph-legend">
      {LEGEND_ROLES.map(role => {
        const { color, shape, fill } = roleStyle(role);
        return (
          <span key={role} className="graph-legend-item">
            <svg width={16} height={16} viewBox="-8 -8 16 16" aria-hidden="true">
              <path d={shapePath(shape, 5.5)} fill={color} fillOpacity={fill} stroke={color} strokeWidth={1.5} />
            </svg>
            {roleLabel(role)}
          </span>
        );
      })}
      <span className="graph-legend-item"><EdgeSwatch flagged />Flagged transfer</span>
      <span className="graph-legend-item"><EdgeSwatch flagged={false} />Other transfer</span>
      <span className="graph-legend-item">
        <svg width={16} height={16} viewBox="-8 -8 16 16" aria-hidden="true">
          <circle r={6} fill="none" stroke="var(--text-primary)" strokeWidth={2.5} strokeDasharray="28 40" />
        </svg>
        Thicker ring, higher risk
      </span>
    </div>
  );
}
