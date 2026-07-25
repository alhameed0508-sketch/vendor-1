import React from 'react';
import { motion } from 'framer-motion';

export function GlassCard({
  children,
  className = '',
  glow = false,
  glowColor = 'rgba(37,99,235,0.08)',
  onClick,
  hover = true,
  as = 'div',
  accent,
  padding = 20,
  style,
  ...props
}) {
  const Component = motion[as] || motion.div;

  return (
    <Component
      className={`glass-card ${className}`}
      onClick={onClick}
      style={{
        position: 'relative',
        overflow: 'hidden',
        padding,
        ...style,
        ...(glow ? {
          boxShadow: `var(--shadow), 0 0 20px ${glowColor}`,
        } : {}),
        cursor: onClick ? 'pointer' : undefined,
      }}
      whileHover={hover ? {
        borderColor: 'rgba(37,99,235,0.20)',
        transition: { duration: 0.15 },
      } : undefined}
      {...props}
    >
      {accent && (
        <div
          className="card-accent-top"
          style={{ background: accent }}
        />
      )}
      {children}
    </Component>
  );
}

export function GlassCardMetric({ label, value, icon, color, accent, children, className = '' }) {
  return (
    <GlassCard className={className} style={{ textAlign: 'center' }} accent={accent} glow glowColor={color ? `${color}18` : undefined}>
      {icon && (
        <div style={{ marginBottom: 6, display: 'flex', justifyContent: 'center', color: color || 'var(--accent-gold)' }}>
          {icon}
        </div>
      )}
      <div className="text-metric-value" style={{ color: color || 'var(--text-primary)' }}>
        {value}
      </div>
      <div className="text-metric-label" style={{ marginTop: 8 }}>
        {label}
      </div>
      {children}
    </GlassCard>
  );
}

export default GlassCard;
