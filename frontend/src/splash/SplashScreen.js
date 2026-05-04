import React, { useState, useEffect, useRef } from 'react';
import gsap from 'gsap';

const TAGLINE = 'Explainable Graph Intelligence for Mule Account Detection';

export default function SplashScreen({ onComplete }) {
  const [typedChars, setTypedChars] = useState(0);
  const containerRef = useRef(null);
  const glowRef      = useRef(null);
  const logoRef      = useRef(null);
  const titleRef     = useRef(null);
  const taglineRef   = useRef(null);
  const iobRef       = useRef(null);
  const skipRef      = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline();

      tl.fromTo(glowRef.current,  { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 1.0, ease: 'elastic.out(1, 0.5)' });
      tl.fromTo(logoRef.current,  { opacity: 0, scale: 0.2, y: 24 }, { opacity: 1, scale: 1, y: 0, duration: 0.9, ease: 'back.out(2.5)' }, '-=0.6');
      tl.fromTo(titleRef.current, { opacity: 0, y: 28 }, { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' }, '-=0.3');
      tl.fromTo(taglineRef.current, { opacity: 0 }, { opacity: 1, duration: 0.4, ease: 'power2.out' }, '-=0.1');
      tl.fromTo(iobRef.current,   { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }, '+=0.2');
      tl.fromTo(skipRef.current,  { opacity: 0 }, { opacity: 1, duration: 0.3 }, '-=0.2');
      tl.to(containerRef.current, { opacity: 0, duration: 0.5, ease: 'power2.inOut', onComplete }, '+=1.2');
    }, containerRef);

    const typeTimer = setInterval(() => {
      setTypedChars(prev => {
        if (prev >= TAGLINE.length) { clearInterval(typeTimer); return prev; }
        return prev + 1;
      });
    }, 38);

    return () => { ctx.revert(); clearInterval(typeTimer); };
  }, [onComplete]);

  const skip = () => gsap.to(containerRef.current, { opacity: 0, duration: 0.3, ease: 'power2.inOut', onComplete });

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'var(--bg-primary)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      {/* Radial glow */}
      <div
        ref={glowRef}
        style={{
          position: 'absolute',
          width: 520,
          height: 520,
          borderRadius: '50%',
          opacity: 0,
          background:
            'radial-gradient(circle at 40% 50%, var(--gradient-brand-glow) 0%, rgba(6,182,212,0.06) 50%, transparent 75%)',
          filter: 'blur(40px)',
          pointerEvents: 'none',
        }}
      />

      {/* SVG Hexagon logo mark */}
      <div
        ref={logoRef}
        style={{ position: 'relative', marginBottom: 20, opacity: 0 }}
      >
        <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="hexGrad" x1="0" y1="0" x2="72" y2="72" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="var(--accent-violet)"/>
              <stop offset="100%" stopColor="var(--accent-indigo)"/>
            </linearGradient>
            <filter id="hexGlow">
              <feGaussianBlur stdDeviation="4" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>
          <polygon
            points="36,4 65,20 65,52 36,68 7,52 7,20"
            fill="none"
            stroke="url(#hexGrad)"
            strokeWidth="1.5"
            filter="url(#hexGlow)"
          />
          <polygon
            points="36,14 57,26 57,46 36,58 15,46 15,26"
            fill="var(--gradient-brand-glow)"
            stroke="var(--border-glow)"
            strokeWidth="0.75"
          />
          <text
            x="36" y="40"
            textAnchor="middle"
            fontFamily="'Inter', system-ui, sans-serif"
            fontWeight="700"
            fontSize="16"
            fill="var(--accent-violet)"
          >MC</text>
        </svg>
      </div>

      {/* Title */}
      <div
        ref={titleRef}
        style={{
          position: 'relative',
          fontFamily: "var(--font-display)",
          fontSize: 40,
          fontWeight: 700,
          letterSpacing: '-1.5px',
          marginBottom: 22,
          opacity: 0,
          color: 'var(--text-primary)',
        }}
      >
        MuleCatch
      </div>

      {/* Typewriter tagline */}
      <div
        ref={taglineRef}
        style={{
          position: 'relative',
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          color: 'var(--text-secondary)',
          height: 24,
          opacity: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <span style={{ color: 'var(--accent-violet)', opacity: 0.55, marginRight: 6 }}>//</span>
        <span>{TAGLINE.slice(0, typedChars)}</span>
        <span
          style={{
            borderRight: '2px solid var(--accent-violet)',
            animation: 'blink 0.8s step-end infinite',
            marginLeft: 1,
          }}
        >&nbsp;</span>
      </div>

      {/* IOB frosted pill */}
      <div
        ref={iobRef}
        style={{
          position: 'relative',
          marginTop: 36,
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
          padding: '5px 14px',
          border: '1px solid var(--border-glow)',
          borderRadius: 8,
          opacity: 0,
          backdropFilter: 'blur(8px)',
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}
      >
        <span style={{ color: 'var(--accent-violet)', opacity: 0.45, marginRight: 6 }}>//</span>
        Indian Overseas Bank
      </div>

      {/* Skip — bottom-right corner */}
      <button
        ref={skipRef}
        onClick={skip}
        style={{
          position: 'absolute',
          bottom: 28,
          right: 28,
          opacity: 0,
          background: 'transparent',
          border: '1px solid var(--border)',
          color: 'var(--text-muted)',
          padding: '5px 14px',
          borderRadius: 8,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '1px',
          textTransform: 'uppercase',
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
        onMouseOver={e => {
          e.currentTarget.style.color = 'var(--text-secondary)';
          e.currentTarget.style.borderColor = 'var(--border-bright)';
        }}
        onMouseOut={e => {
          e.currentTarget.style.color = 'var(--text-muted)';
          e.currentTarget.style.borderColor = 'var(--border)';
        }}
      >
        Skip
      </button>
    </div>
  );
}
