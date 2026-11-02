import React from 'react';

/**
 * Canonical StatCard — one component replacing 4 duplicated variants.
 * Uses .stat-card CSS class. No Framer Motion for hover.
 * `tone` ('critical' or 'high') colours the number for a risk level; `index` staggers its entrance.
 */
export default function StatCard({ label, value, icon: Icon, sub, tone, index }) {
  return (
    <div
      className={tone ? `stat-card stat-card--${tone}` : 'stat-card'}
      style={index === undefined ? undefined : { '--i': index }}
    >
      <div className="stat-card__header">
        <div className="text-metric-label">{label}</div>
        {Icon && (
          <div className="stat-card__icon">
            <Icon size={14} />
          </div>
        )}
      </div>

      <div className="text-metric-value" style={{ marginBottom: sub ? 8 : 0 }}>
        {value}
      </div>

      {sub && <div className="stat-card__sub">{sub}</div>}
    </div>
  );
}
