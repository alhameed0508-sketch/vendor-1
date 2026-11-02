import React from 'react';
import { MapPin } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';
import { formatAmount } from '../graph_viz/graphModel';

const SEVERITIES = [
  ['critical', 'Critical', 'criticalCount'],
  ['high', 'High', 'highCount'],
  ['medium', 'Medium', 'mediumCount'],
];

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;

function CityRow({ city, rank, isSelected, onCityClick }) {
  return (
    <button
      type="button"
      className="region-row"
      aria-pressed={isSelected}
      onClick={() => onCityClick?.(city.name)}
    >
      <span className="region-rank">{rank}</span>
      <span className="region-city">
        <span className="region-city-head">
          <span className="region-city-name">{city.name}</span>
          <span className="region-city-meta">
            {plural(city.accountCount, 'account')}, {formatAmount(city.totalVolume)}
          </span>
        </span>
        <span className="region-badges">
          {SEVERITIES.filter(([, , key]) => city[key] > 0).map(([tone, label, key]) => (
            <span key={tone} className={`region-badge region-badge--${tone}`}>{label} {city[key]}</span>
          ))}
        </span>
      </span>
    </button>
  );
}

export default function RegionalStatsPanel({ cityData = [], selectedCity, onCityClick }) {
  const totalAlerts = cityData.reduce((s, c) => s + c.alertCount, 0);
  const totalVolume = cityData.reduce((s, c) => s + c.totalVolume, 0);
  const top5 = cityData.slice(0, 5);

  return (
    <GlassCard hover={false} className="region-panel" style={{ padding: 0 }}>
      <div className="region-head">
        <MapPin size={14} aria-hidden="true" />
        <span>Regional Overview</span>
      </div>

      <div className="region-totals">
        <div>
          <div className="region-total-label">Total Alerts</div>
          <div className="region-total-value">{totalAlerts}</div>
        </div>
        <div>
          <div className="region-total-label">Suspicious Vol.</div>
          <div className="region-total-value">{formatAmount(totalVolume)}</div>
        </div>
      </div>

      <div className="region-list">
        {top5.length === 0 && <p className="region-empty">No city data available</p>}
        {top5.map((city, i) => (
          <CityRow key={city.name} city={city} rank={i + 1}
            isSelected={selectedCity === city.name} onCityClick={onCityClick} />
        ))}
      </div>

      {cityData.length > 5 && (
        <div className="region-more">+{cityData.length - 5} more cities</div>
      )}
    </GlassCard>
  );
}
