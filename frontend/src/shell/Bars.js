import React from 'react';
import './shell.css';

const pct = (part, total) => (total > 0 ? Math.round((part / total) * 1000) / 10 : 0);

/** One stacked bar: each segment's share of the whole, with a legend that carries the numbers. */
export function SplitBar({ segments, format = v => v, label }) {
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value || 0), 0);
  const summary = segments.map(s => `${s.label} ${format(s.value)} (${pct(s.value, total)}%)`).join(', ');
  return (
    <figure className="split">
      <div className="split__bar" role="img" aria-label={`${label}: ${summary}`}>
        {total > 0
          ? segments.filter(s => s.value > 0).map(s => (
            <span key={s.label} className={`split__seg split__seg--${s.tone}`} style={{ width: `${pct(s.value, total)}%` }} />
          ))
          : <span className="split__seg split__seg--empty" style={{ width: '100%' }} />}
      </div>
      <figcaption className="split__legend">
        {segments.map(s => (
          <span key={s.label} className="split__item">
            <span className={`split__dot split__seg--${s.tone}`} aria-hidden="true" />
            <span className="split__name">{s.label}</span>
            <span className="data-value split__value">{format(s.value)}</span>
            <span className="split__pct">{pct(s.value, total)}%</span>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

/** Horizontal bars, longest first: what a module found, by rule or by severity. */
export function RankBars({ items, tone = 'accent', label }) {
  const top = Math.max(1, ...items.map(i => i.value));
  if (!items.length) return null;
  return (
    <ul className="rank" aria-label={label}>
      {items.map(i => (
        <li key={i.key || i.label} className="rank__row">
          <span className="rank__label" title={i.title || i.label}>{i.label}</span>
          <span className="rank__track" aria-hidden="true">
            <span className={`rank__fill rank__fill--${i.tone || tone}`} style={{ width: `${Math.max(3, (i.value / top) * 100)}%` }} />
          </span>
          <span className="data-value rank__value">{i.value}</span>
        </li>
      ))}
    </ul>
  );
}
