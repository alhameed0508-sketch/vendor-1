import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { useTheme } from '../../ThemeContext';

export default function BackgroundGrid() {
  const containerRef = useRef(null);
  const orb1Ref = useRef(null);
  const orb2Ref = useRef(null);
  const orb3Ref = useRef(null);
  const { theme } = useTheme();

  const isLight = theme === 'light';

  useEffect(() => {
    // Extremely slow, ambient drifting motion for a "premium" feel
    const ctx = gsap.context(() => {
      gsap.to(orb1Ref.current, {
        x: '30vw',
        y: '20vh',
        rotation: 45,
        scale: 1.2,
        duration: 25,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.to(orb2Ref.current, {
        x: '-20vw',
        y: '-10vh',
        scale: 1.4,
        duration: 35,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      gsap.to(orb3Ref.current, {
        x: '15vw',
        y: '-30vh',
        scale: 1.1,
        duration: 20,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        overflow: 'hidden',
        background: isLight ? '#F5F5F7' : '#020305',
        transition: 'background 0.3s',
      }}
    >
      {/* Ambient Orbs — lighter in light theme */}
      <div
        ref={orb1Ref}
        style={{
          position: 'absolute',
          top: '-10%',
          left: '-10%',
          width: '50vw',
          height: '50vw',
          background: isLight
            ? 'radial-gradient(circle, rgba(0, 122, 255, 0.06) 0%, transparent 60%)'
            : 'radial-gradient(circle, rgba(124, 158, 255, 0.15) 0%, transparent 60%)',
          borderRadius: '50%',
          filter: 'blur(100px)',
        }}
      />
      <div
        ref={orb2Ref}
        style={{
          position: 'absolute',
          bottom: '-20%',
          right: '-10%',
          width: '60vw',
          height: '60vw',
          background: isLight
            ? 'radial-gradient(circle, rgba(88, 86, 214, 0.04) 0%, transparent 70%)'
            : 'radial-gradient(circle, rgba(6, 182, 212, 0.08) 0%, transparent 70%)',
          borderRadius: '50%',
          filter: 'blur(120px)',
        }}
      />
      <div
        ref={orb3Ref}
        style={{
          position: 'absolute',
          top: '30%',
          left: '40%',
          width: '40vw',
          height: '40vw',
          background: isLight
            ? 'radial-gradient(circle, rgba(0, 122, 255, 0.03) 0%, transparent 60%)'
            : 'radial-gradient(circle, rgba(30, 20, 80, 0.3) 0%, transparent 60%)',
          borderRadius: '50%',
          filter: 'blur(80px)',
          opacity: 0.8,
        }}
      />

      {/* Grid lines — invisible in light theme */}
      {!isLight && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundSize: '100px 100px',
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.01) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.01) 1px, transparent 1px)
            `,
            opacity: 0.5,
          }}
        />
      )}

      {/* Film grain — hidden in light theme */}
      {!isLight && <div className="grain-overlay" style={{ opacity: 0.02 }} />}
    </div>
  );
}
