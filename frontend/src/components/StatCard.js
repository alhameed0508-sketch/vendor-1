import React from 'react';

/**
 * Canonical StatCard — one component replacing 4 duplicated variants.
 * Uses .stat-card CSS class. No Framer Motion for hover.
 */
export default function StatCard({ label, value, icon: Icon, sub }) {
  return (
    <div className="stat-card">
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
