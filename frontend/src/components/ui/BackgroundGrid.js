import React, { useEffect, useRef, useCallback } from 'react';
import gsap from 'gsap';
import { useTheme } from '../../ThemeContext';

// Intelligence Command Center background:
// Deep space base + electric indigo/violet/cyan volumetric orbs
// + constellation particle mesh + scanning sweep + aurora edge lines

export default function BackgroundGrid() {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const orb1Ref = useRef(null);
  const orb2Ref = useRef(null);
  const orb3Ref = useRef(null);
  const orb4Ref = useRef(null);
  const scanRef = useRef(null);
  const animFrameRef = useRef(null);
  const { theme } = useTheme();
  const isLight = theme === 'light';

  // Particle constellation mesh
  const drawParticles = useCallback((canvas) => {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = window.innerWidth;
    const height = canvas.height = window.innerHeight;
    const particleCount = Math.min(Math.floor((width * height) / 18000), 80);
    const connectionDistance = 140;

    const particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 1.5 + 0.5,
      opacity: Math.random() * 0.4 + 0.1,
    }));

    const animate = () => {
      ctx.clearRect(0, 0, width, height);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;
      }

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < connectionDistance) {
            const alpha = (1 - dist / connectionDistance) * 0.15;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = isLight
              ? `rgba(99,102,241,${alpha * 0.6})`
              : `rgba(139,92,246,${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Draw particles
      for (const p of particles) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = isLight
          ? `rgba(99,102,241,${p.opacity * 0.7})`
          : `rgba(167,139,250,${p.opacity})`;
        ctx.fill();
      }

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animate();
  }, [isLight]);

  useEffect(() => {
    const canvas = canvasRef.current;
    drawParticles(canvas);

    const handleResize = () => drawParticles(canvas);
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [drawParticles]);

  useEffect(() => {
    const ctx = gsap.context(() => {
      // Indigo primary orb — top right
      gsap.to(orb1Ref.current, {
        x: '-15vw', y: '20vh', scale: 1.25,
        duration: 28, repeat: -1, yoyo: true, ease: 'sine.inOut',
      });
      // Cyan orb — bottom left
      gsap.to(orb2Ref.current, {
        x: '20vw', y: '-15vh', scale: 1.4,
        duration: 38, repeat: -1, yoyo: true, ease: 'sine.inOut', delay: 5,
      });
      // Violet accent orb — center
      gsap.to(orb3Ref.current, {
        x: '-8vw', y: '12vh', scale: 1.15,
        duration: 24, repeat: -1, yoyo: true, ease: 'sine.inOut', delay: 10,
      });
      // Rose accent orb — subtle, top left
      gsap.to(orb4Ref.current, {
        x: '12vw', y: '8vh', scale: 1.3,
        duration: 35, repeat: -1, yoyo: true, ease: 'sine.inOut', delay: 18,
      });
      // Scanline sweep
      if (!isLight && scanRef.current) {
        gsap.fromTo(scanRef.current,
          { y: '-5px', opacity: 0 },
          {
            y: '100vh', opacity: 1,
            duration: 4, repeat: -1, ease: 'none',
            delay: 3, repeatDelay: 22,
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
        background: isLight ? '#F7FAFC' : '#050A18',
        transition: 'background 0.5s ease',
      }}
    >
      {/* Particle constellation canvas */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute', inset: 0,
          opacity: isLight ? 0.4 : 0.6,
        }}
      />

      {/* Indigo primary orb */}
      <div ref={orb1Ref} style={{
        position: 'absolute', top: '-15%', right: '-5%',
        width: '52vw', height: '52vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(99,102,241,0.06) 0%, transparent 65%)'
          : 'radial-gradient(circle, rgba(99,102,241,0.16) 0%, transparent 65%)',
        borderRadius: '50%', filter: 'blur(80px)',
      }} />

      {/* Cyan orb */}
      <div ref={orb2Ref} style={{
        position: 'absolute', bottom: '-20%', left: '-5%',
        width: '60vw', height: '60vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(34,211,238,0.05) 0%, transparent 70%)'
          : 'radial-gradient(circle, rgba(34,211,238,0.10) 0%, transparent 70%)',
        borderRadius: '50%', filter: 'blur(100px)',
      }} />

      {/* Violet accent orb */}
      <div ref={orb3Ref} style={{
        position: 'absolute', top: '40%', right: '20%',
        width: '30vw', height: '30vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(139,92,246,0.04) 0%, transparent 60%)'
          : 'radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 60%)',
        borderRadius: '50%', filter: 'blur(70px)',
      }} />

      {/* Rose/pink subtle accent orb */}
      <div ref={orb4Ref} style={{
        position: 'absolute', top: '10%', left: '15%',
        width: '25vw', height: '25vw',
        background: isLight
          ? 'radial-gradient(circle, rgba(244,63,94,0.02) 0%, transparent 60%)'
          : 'radial-gradient(circle, rgba(244,63,94,0.05) 0%, transparent 60%)',
        borderRadius: '50%', filter: 'blur(60px)',
      }} />

      {/* Hex dot grid overlay */}
      {!isLight && (
        <>
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: 'radial-gradient(circle, rgba(99,102,241,0.12) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
            opacity: 0.35,
            maskImage: 'radial-gradient(ellipse 85% 75% at 50% 50%, black 20%, transparent 100%)',
            WebkitMaskImage: 'radial-gradient(ellipse 85% 75% at 50% 50%, black 20%, transparent 100%)',
          }} />
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: 'radial-gradient(circle, rgba(139,92,246,0.06) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
            backgroundPosition: '16px 16px',
            opacity: 0.25,
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
            linear-gradient(rgba(99,102,241,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99,102,241,0.03) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }} />
      )}

      {/* Intelligence scanline sweep */}
      {!isLight && (
        <div ref={scanRef} style={{
          position: 'absolute', left: 0, right: 0, height: '2px',
          background: 'linear-gradient(90deg, transparent 0%, rgba(99,102,241,0.6) 25%, rgba(139,92,246,0.8) 50%, rgba(34,211,238,0.6) 75%, transparent 100%)',
          boxShadow: '0 0 20px rgba(99,102,241,0.4), 0 0 6px rgba(139,92,246,0.6), 0 -4px 16px rgba(99,102,241,0.15), 0 4px 16px rgba(99,102,241,0.15)',
          opacity: 0,
        }} />
      )}

      {/* Aurora edge lines */}
      {!isLight && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '1px',
          background: 'linear-gradient(90deg, transparent 0%, rgba(99,102,241,0.3) 30%, rgba(139,92,246,0.4) 50%, rgba(34,211,238,0.3) 70%, transparent 100%)',
        }} />
      )}

      {/* Edge vignette */}
      <div style={{
        position: 'absolute', inset: 0,
        background: isLight
          ? 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.04) 100%)'
          : 'radial-gradient(ellipse at center, transparent 30%, rgba(5,10,24,0.90) 100%)',
      }} />
    </div>
  );
}
