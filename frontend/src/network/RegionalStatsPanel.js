import React from 'react';
import { motion } from 'framer-motion';
import { MapPin } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';

function formatVolume(amount) {
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
  if (amount >= 100000)   return `₹${(amount / 100000).toFixed(1)}L`;
  if (amount >= 1000)     return `₹${(amount / 1000).toFixed(0)}K`;
  return `₹${Math.round(amount)}`;
}

function SeverityBadge({ label, count, color }) {
  if (!count) return null;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 3,
      padding: '1px 6px',
      borderRadius: 4,
      fontSize: 12,
      fontFamily: 'var(--font-sans)',
      fontWeight: 700,
      background: `${color}18`,
      color,
      border: `1px solid ${color}30`,
    }}>
      {label} {count}
    </span>
  );
}

export default function RegionalStatsPanel({ cityData = [], selectedCity, onCityClick }) {
  const totalAlerts = cityData.reduce((s, c) => s + c.alertCount, 0);
  const totalVolume = cityData.reduce((s, c) => s + c.totalVolume, 0);
  const top5 = cityData.slice(0, 5);

  return (
    <GlassCard hover={false} style={{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <MapPin size={14} style={{ color: 'var(--accent-cyan)', opacity: 0.7 }} />
          <span style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-primary)',
            letterSpacing: '0.3px',
          }}>
            Regional Overview
          </span>
        </div>
      </div>

      {/* Summary row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 1,
        background: 'rgba(255,255,255,0.03)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ padding: '12px 20px', background: 'var(--bg-card)' }}>
          <div style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--text-muted)',
            marginBottom: 4,
          }}>Total Alerts</div>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: 22,
            fontWeight: 700,
            color: '#F43F5E',
            letterSpacing: '-0.5px',
            lineHeight: 1,
          }}>{totalAlerts}</div>
        </div>
        <div style={{ padding: '12px 20px', background: 'var(--bg-card)' }}>
          <div style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--text-muted)',
            marginBottom: 4,
          }}>Suspicious Vol.</div>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: 22,
            fontWeight: 700,
            color: '#FB923C',
            letterSpacing: '-0.5px',
            lineHeight: 1,
          }}>{formatVolume(totalVolume)}</div>
        </div>
      </div>

      {/* Top 5 cities list */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
        {top5.length === 0 && (
          <div style={{
            padding: '24px 20px',
            textAlign: 'center',
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--text-muted)',
          }}>
            No city data available
          </div>
        )}
        {top5.map((city, i) => {
          const isSelected = selectedCity === city.name;
          return (
            <motion.div
              key={city.name}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05, duration: 0.25, ease: 'easeOut' }}
              onClick={() => onCityClick?.(city.name)}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '10px 20px',
                cursor: onCityClick ? 'pointer' : 'default',
                background: isSelected ? 'rgba(62,231,255,0.06)' : 'transparent',
                borderLeft: isSelected ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                transition: 'background 0.15s, border-color 0.15s',
              }}
              whileHover={{
                background: isSelected ? 'rgba(62,231,255,0.08)' : 'rgba(255,255,255,0.02)',
              }}
            >
              {/* Rank */}
              <div style={{
                width: 20,
                height: 20,
                borderRadius: 5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: 'var(--font-sans)',
                fontSize: 12,
                fontWeight: 700,
                flexShrink: 0,
                background: i === 0 ? 'rgba(244,63,94,0.15)' : 'rgba(255,255,255,0.05)',
                color: i === 0 ? '#F43F5E' : 'var(--text-muted)',
                border: `1px solid ${i === 0 ? 'rgba(244,63,94,0.3)' : 'rgba(255,255,255,0.08)'}`,
              }}>
                {i + 1}
              </div>

              {/* City details */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                  <span style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: 13,
                    fontWeight: 600,
                    color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)',
                  }}>
                    {city.name}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: 12,
                    color: 'var(--text-muted)',
                    flexShrink: 0,
                    marginLeft: 8,
                  }}>
                    {city.accountCount} accts · {formatVolume(city.totalVolume)}
                  </span>
                </div>

                {/* Severity badges */}
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <SeverityBadge label="CRIT" count={city.criticalCount} color="#EF4444" />
                  <SeverityBadge label="HIGH" count={city.highCount} color="#F97316" />
                  <SeverityBadge label="MED" count={city.mediumCount} color="#FBBF24" />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Footer: remaining city count */}
      {cityData.length > 5 && (
        <div style={{
          padding: '8px 20px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          fontFamily: 'var(--font-sans)',
          fontSize: 12,
          color: 'var(--text-muted)',
          textAlign: 'center',
        }}>
          +{cityData.length - 5} more cities
        </div>
      )}
    </GlassCard>
  );
}
