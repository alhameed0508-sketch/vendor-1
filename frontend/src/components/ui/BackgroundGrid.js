import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { useTheme } from '../../ThemeContext';

// Subtle ambient background — inspired by Mercury/Vercel
// Minimal: one gentle gradient orb + faint dot grid + vignette

export default function BackgroundGrid() {
  const containerRef = useRef(null);
  const orb1Ref = useRef(null);
  const orb2Ref = useRef(null);
  const { theme } = useTheme();
  const isLight = theme === 'light';

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.to(orb1Ref.current, {
        x: '-10vw', y: '15vh', scale: 1.15,
        duration: 40, repeat: -1, yoyo: true, ease: 'sine.inOut',
      });
      gsap.to(orb2Ref.current, {
        x: '12vw', y: '-10vh', scale: 1.2,
        duration: 50, repeat: -1, yoyo: true, ease: 'sine.inOut', delay: 10,
      });
    }, containerRef);
    return () => ctx.revert();
  }, [isLight]);

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed', inset: 0, zIndex: 0,
        pointerEvents: 'none', overflow: 'hidden',
        background: isLight ? '#F7FAFC' : 'var(--bg-base)',
        transition: 'background 0.4s ease',
      }}
    >
      {/* Primary ambient orb — very subtle */}
      <div ref={orb1Ref} style={{
        position: 'absolute', top: '-20%', right: '-10%',
        width: '60vw', height: '60vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(99,102,241,0.04) 0%, transparent 60%)'
          : 'radial-gradient(circle, rgba(99,102,241,0.06) 0%, transparent 60%)',
        borderRadius: '50%', filter: 'blur(100px)',
      }} />

      {/* Secondary ambient orb */}
      <div ref={orb2Ref} style={{
        position: 'absolute', bottom: '-25%', left: '-10%',
        width: '50vw', height: '50vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(99,102,241,0.03) 0%, transparent 60%)'
          : 'radial-gradient(circle, rgba(99,102,241,0.04) 0%, transparent 60%)',
        borderRadius: '50%', filter: 'blur(120px)',
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

      {/* Light mode grid */}
      {isLight && (
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `
            linear-gradient(rgba(0,0,0,0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.02) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }} />
      )}

      {/* Edge vignette */}
      <div style={{
        position: 'absolute', inset: 0,
        background: isLight
          ? 'radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.03) 100%)'
          : 'radial-gradient(ellipse at center, transparent 40%, rgba(8,8,12,0.85) 100%)',
      }} />
    </div>
  );
}
