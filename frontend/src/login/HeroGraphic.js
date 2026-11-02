import React from 'react';
import { edgeStyle, roleStyle, shapePath } from '../graph_viz/graphStyle';

const DESCRIPTION = 'Example money flow: three source accounts feed one aggregator, which pays out to three mule accounts.';

const SOURCES = [{ x: 64, y: 52 }, { x: 64, y: 130 }, { x: 64, y: 208 }];
const AGGREGATOR = { x: 250, y: 130 };
const MULES = [{ x: 436, y: 52 }, { x: 436, y: 130 }, { x: 436, y: 208 }];
// Ordinary accounts that touch nothing suspicious: the grey majority of the real graph.
const BYSTANDERS = [{ x: 156, y: 22 }, { x: 156, y: 238 }, { x: 344, y: 22 }, { x: 344, y: 238 }];

const FLOW = [
  ...SOURCES.map(from => ({ from, to: AGGREGATOR })),
  ...MULES.map(to => ({ from: AGGREGATOR, to })),
];
const SIDE_LINKS = [
  { from: BYSTANDERS[0], to: SOURCES[0] },
  { from: BYSTANDERS[1], to: SOURCES[2] },
  { from: BYSTANDERS[2], to: MULES[0] },
  { from: BYSTANDERS[3], to: MULES[2] },
];

const keyOf = ({ from, to }) => `${from.x}-${from.y}-${to.x}-${to.y}`;

function Edge({ from, to, flagged }) {
  const { stroke, opacity, dash } = edgeStyle(flagged);
  return (
    <line
      x1={from.x} y1={from.y} x2={to.x} y2={to.y}
      stroke={stroke} strokeOpacity={opacity} strokeDasharray={dash || undefined} strokeWidth="1.5"
    />
  );
}

// A solid base under the tinted fill, so an edge running to the centre does not show through the shape.
function Node({ role, at, size }) {
  const { color, shape, fill } = roleStyle(role);
  const d = shapePath(shape, size);
  return (
    <g transform={`translate(${at.x} ${at.y})`}>
      <path d={d} fill="var(--bg-surface)" />
      <path d={d} fill={color} fillOpacity={fill} stroke={color} strokeWidth="2" />
    </g>
  );
}

function Caption({ x, children }) {
  return <text x={x} y={252} textAnchor="middle" className="login-graphic__caption">{children}</text>;
}

/** The pattern the product looks for, drawn with the same role shapes, colours and edges as the live graph. */
export default function HeroGraphic() {
  return (
    <svg className="login-graphic" viewBox="0 0 500 260" role="img" aria-label={DESCRIPTION}>
      {SIDE_LINKS.map(link => <Edge key={keyOf(link)} {...link} flagged={false} />)}
      {FLOW.map(link => <Edge key={keyOf(link)} {...link} flagged />)}
      {FLOW.map(({ from, to }) => (
        <line
          key={`pulse-${keyOf({ from, to })}`}
          className="login-graphic__pulse"
          x1={from.x} y1={from.y} x2={to.x} y2={to.y}
        />
      ))}
      {BYSTANDERS.map(at => <Node key={`${at.x}-${at.y}`} role="LEGITIMATE" at={at} size={6} />)}
      {SOURCES.map(at => <Node key={at.y} role="SOURCE" at={at} size={13} />)}
      <Node role="AGGREGATOR" at={AGGREGATOR} size={20} />
      {MULES.map(at => <Node key={at.y} role="MULE" at={at} size={11} />)}
      <Caption x={SOURCES[0].x}>Sources</Caption>
      <Caption x={AGGREGATOR.x}>Aggregator</Caption>
      <Caption x={MULES[0].x}>Mules</Caption>
    </svg>
  );
}
