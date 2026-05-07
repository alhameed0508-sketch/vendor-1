import React from 'react';
import { motion } from 'framer-motion';

export function GlassCard({
  children,
  className = '',
  glow = false,
  glowColor = 'var(--gradient-brand-glow)',
  onClick,
  hover = true,
  as = 'div',
  accent,
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
        ...style,
        ...(glow ? {
          boxShadow: `var(--shadow), 0 0 20px ${glowColor}`,
        } : {}),
        cursor: onClick ? 'pointer' : undefined,
      }}
      whileHover={hover ? { y: -2, transition: { type: 'spring', stiffness: 400, damping: 30 } } : undefined}
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
    <GlassCard className={`p-5 text-center ${className}`} accent={accent} glow glowColor={color ? `${color}18` : undefined}>
      {icon && (
        <div style={{ marginBottom: 6, display: 'flex', justifyContent: 'center', color: color || 'var(--accent-gold)' }}>
          {icon}
        </div>
      )}
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 28,
          fontWeight: 700,
          letterSpacing: '-0.5px',
          color: color || 'var(--text-primary)',
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--text-muted)',
          marginTop: 8,
          letterSpacing: '1.5px',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </div>
      {children}
    </GlassCard>
  );
}

export default GlassCard;
