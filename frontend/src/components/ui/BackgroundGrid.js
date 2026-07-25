import React from 'react';
import { useTheme } from '../../ThemeContext';

// Subtle ambient background — static gradient + faint grid pattern
// No GSAP, no animated orbs

export default function BackgroundGrid() {
  const { theme } = useTheme();
  const isLight = theme === 'light';

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 0,
        pointerEvents: 'none', overflow: 'hidden',
        background: isLight ? '#F8FAFC' : 'var(--bg-base)',
        transition: 'background 0.4s ease',
      }}
    >
      {/* Static ambient gradient — uses existing CSS token */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'var(--gradient-bg)',
      }} />

      {/* Subtle dot grid — dark mode only */}
      {!isLight && (
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          maskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 100%)',
        }} />
      )}

      {/* Light mode grid — faint blue-tinted lines */}
      {isLight && (
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `
            linear-gradient(rgba(37,99,235,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37,99,235,0.03) 1px, transparent 1px)
          `,
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 40%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 40%, transparent 100%)',
        }} />
      )}

      {/* Edge vignette */}
      <div style={{
        position: 'absolute', inset: 0,
        background: isLight
          ? 'radial-gradient(ellipse at center, transparent 70%, rgba(37,99,235,0.02) 100%)'
          : 'radial-gradient(ellipse at center, transparent 40%, rgba(8,8,12,0.85) 100%)',
      }} />
    </div>
  );
}
