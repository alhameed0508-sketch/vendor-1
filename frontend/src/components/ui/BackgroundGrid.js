import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { useTheme } from '../../ThemeContext';

// Darktrace/Palantir-inspired background:
// Obsidian base + emerald/cyan volumetric orbs + hex grid + scanline sweep

export default function BackgroundGrid() {
  const containerRef = useRef(null);
  const orb1Ref = useRef(null);
  const orb2Ref = useRef(null);
  const orb3Ref = useRef(null);
  const scanRef = useRef(null);
  const { theme } = useTheme();
  const isLight = theme === 'light';

  useEffect(() => {
    const ctx = gsap.context(() => {
      // Emerald primary orb — top right
      gsap.to(orb1Ref.current, {
        x: '-15vw', y: '20vh', scale: 1.25,
        duration: 32, repeat: -1, yoyo: true, ease: 'sine.inOut',
      });
      // Cyan secondary orb — bottom left
      gsap.to(orb2Ref.current, {
        x: '20vw', y: '-15vh', scale: 1.4,
        duration: 42, repeat: -1, yoyo: true, ease: 'sine.inOut', delay: 7,
      });
      // Violet accent orb — center-right
      gsap.to(orb3Ref.current, {
        x: '-8vw', y: '12vh', scale: 1.15,
        duration: 27, repeat: -1, yoyo: true, ease: 'sine.inOut', delay: 14,
      });
      // Scanline sweep — threat detection feel
      if (!isLight && scanRef.current) {
        gsap.fromTo(scanRef.current,
          { y: '-5px', opacity: 0 },
          {
            y: '100vh', opacity: 1,
            duration: 5, repeat: -1, ease: 'none',
            delay: 4, repeatDelay: 18,
          }
        );
      }
    }, containerRef);
    return () => ctx.revert();
  }, [isLight]);

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed', inset: 0, zIndex: 0,
        pointerEvents: 'none', overflow: 'hidden',
        background: isLight ? '#F7FAFC' : '#0B1020',
        transition: 'background 0.5s ease',
      }}
    >
      {/* Emerald primary orb — signals "healthy detection active" */}
      <div ref={orb1Ref} style={{
        position: 'absolute', top: '-15%', right: '-5%',
        width: '52vw', height: '52vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(62,231,255,0.06) 0%, transparent 65%)'
          : 'radial-gradient(circle, rgba(62,231,255,0.13) 0%, transparent 65%)',
        borderRadius: '50%', filter: 'blur(80px)',
      }} />

      {/* Cyan orb — signals "intelligence / graph analysis" */}
      <div ref={orb2Ref} style={{
        position: 'absolute', bottom: '-20%', left: '-5%',
        width: '60vw', height: '60vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(0,194,168,0.04) 0%, transparent 70%)'
          : 'radial-gradient(circle, rgba(0,194,168,0.09) 0%, transparent 70%)',
        borderRadius: '50%', filter: 'blur(100px)',
      }} />

      {/* Violet accent orb — brand/system signal */}
      <div ref={orb3Ref} style={{
        position: 'absolute', top: '40%', right: '20%',
        width: '30vw', height: '30vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(124,58,237,0.03) 0%, transparent 60%)'
          : 'radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 60%)',
        borderRadius: '50%', filter: 'blur(70px)',
      }} />

      {/* Hexagonal dot grid — cybersecurity intelligence feel */}
      {!isLight && (
        <>
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: 'radial-gradient(circle, rgba(62,231,255,0.1) 1px, transparent 1px)',
            backgroundSize: '28px 28px',
            opacity: 0.4,
            maskImage: 'radial-gradient(ellipse 85% 75% at 50% 50%, black 20%, transparent 100%)',
            WebkitMaskImage: 'radial-gradient(ellipse 85% 75% at 50% 50%, black 20%, transparent 100%)',
          }} />
          {/* Secondary offset grid layer for hex illusion */}
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: 'radial-gradient(circle, rgba(0,194,168,0.06) 1px, transparent 1px)',
            backgroundSize: '28px 28px',
            backgroundPosition: '14px 14px',
            opacity: 0.3,
            maskImage: 'radial-gradient(ellipse 70% 70% at 60% 40%, black 10%, transparent 100%)',
            WebkitMaskImage: 'radial-gradient(ellipse 70% 70% at 60% 40%, black 10%, transparent 100%)',
          }} />
        </>
      )}

      {/* Light mode subtle grid */}
      {isLight && (
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `
            linear-gradient(rgba(0,0,0,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.025) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }} />
      )}

      {/* Threat-detection scanline sweep */}
      {!isLight && (
        <div ref={scanRef} style={{
          position: 'absolute', left: 0, right: 0, height: '1px',
          background: 'linear-gradient(90deg, transparent 0%, rgba(62,231,255,0.5) 30%, rgba(0,194,168,0.7) 50%, rgba(62,231,255,0.5) 70%, transparent 100%)',
          boxShadow: '0 0 16px rgba(62,231,255,0.3), 0 0 4px rgba(0,194,168,0.5)',
          opacity: 0,
        }} />
      )}

      {/* Horizontal glowing edge lines — top and bottom depth */}
      {!isLight && (
        <>
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, height: '1px',
            background: 'linear-gradient(90deg, transparent 0%, rgba(62,231,255,0.2) 40%, rgba(0,194,168,0.3) 50%, rgba(62,231,255,0.2) 60%, transparent 100%)',
          }} />
        </>
      )}

      {/* Edge vignette — frames the content area */}
      <div style={{
        position: 'absolute', inset: 0,
        background: isLight
          ? 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.04) 100%)'
          : 'radial-gradient(ellipse at center, transparent 35%, rgba(11,16,32,0.85) 100%)',
      }} />
    </div>
  );
}
