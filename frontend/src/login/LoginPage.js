import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../auth/AuthContext';
import { GlassCard } from '../components/ui/GlassCard';
import { Shield, Lock, Fingerprint, Eye, EyeOff } from 'lucide-react';

/* ── Animated typing tagline ── */
function TypewriterText({ texts, speed = 80, pause = 2200 }) {
  const [displayed, setDisplayed] = useState('');
  const [textIndex, setTextIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const current = texts[textIndex];
    let timeout;

    if (!deleting && charIndex < current.length) {
      timeout = setTimeout(() => setCharIndex(prev => prev + 1), speed);
    } else if (!deleting && charIndex === current.length) {
      timeout = setTimeout(() => setDeleting(true), pause);
    } else if (deleting && charIndex > 0) {
      timeout = setTimeout(() => setCharIndex(prev => prev - 1), speed / 2);
    } else if (deleting && charIndex === 0) {
      setDeleting(false);
      setTextIndex(prev => (prev + 1) % texts.length);
    }

    setDisplayed(current.substring(0, charIndex));
    return () => clearTimeout(timeout);
  }, [charIndex, deleting, textIndex, texts, speed, pause]);

  return (
    <span>
      {displayed}
      <span style={{
        display: 'inline-block',
        width: 1,
        height: '1em',
        background: '#818CF8',
        marginLeft: 2,
        animation: 'cursorBlink 1s step-end infinite',
        verticalAlign: 'text-bottom',
      }} />
    </span>
  );
}

/* ── Floating security badges ── */
function FloatingBadge({ icon: Icon, label, delay, x, y }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{
        opacity: [0, 0.6, 0.4],
        scale: [0.5, 1, 0.95],
        y: [0, -8, 0, 8, 0],
      }}
      transition={{
        opacity: { duration: 1.5, delay },
        scale: { duration: 1.5, delay },
        y: { duration: 6, repeat: Infinity, ease: 'easeInOut', delay: delay + 1 },
      }}
      style={{
        position: 'absolute',
        left: x,
        top: y,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 12px',
        background: 'rgba(99, 102, 241, 0.06)',
        border: '1px solid rgba(99, 102, 241, 0.12)',
        borderRadius: 20,
        backdropFilter: 'blur(12px)',
        pointerEvents: 'none',
        zIndex: 1,
      }}
    >
      <Icon size={11} color="#818CF8" />
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: 'rgba(129, 140, 248, 0.7)',
        letterSpacing: '0.8px',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}>
        {label}
      </span>
    </motion.div>
  );
}

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [focused, setFocused] = useState(null);

  if (isAuthenticated) {
    navigate('/', { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      const message = err.message || 'Login failed';
      if (message.toLowerCase().includes('lock')) {
        setError('Account locked. Please contact your administrator.');
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Floating security badges */}
      <FloatingBadge icon={Shield} label="AES-256 Encrypted" delay={0.8} x="8%" y="20%" />
      <FloatingBadge icon={Lock} label="JWT Auth" delay={1.2} x="75%" y="15%" />
      <FloatingBadge icon={Fingerprint} label="RBAC Secured" delay={1.6} x="5%" y="72%" />
      <FloatingBadge icon={Shield} label="RBI Compliant" delay={2.0} x="78%" y="75%" />

      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
        style={{ width: '100%', maxWidth: 420, padding: 24, position: 'relative', zIndex: 2 }}
      >
        {/* Outer glow ring */}
        <div style={{
          position: 'absolute',
          inset: -1,
          borderRadius: 17,
          background: 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2), rgba(34,211,238,0.15), rgba(99,102,241,0.3))',
          backgroundSize: '300% 300%',
          animation: 'borderShimmer 6s ease infinite',
          filter: 'blur(1px)',
          zIndex: -1,
        }} />

        <GlassCard className="p-8" hover={false} style={{
          background: 'rgba(8, 14, 30, 0.88)',
          backdropFilter: 'blur(40px) saturate(200%)',
          border: '1px solid rgba(99, 102, 241, 0.12)',
        }}>
          {/* Logo */}
          <div style={{ textAlign: 'center', marginBottom: 36 }}>
            <motion.div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: 'linear-gradient(135deg, #6366F1 0%, #A78BFA 50%, #22D3EE 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
                boxShadow: '0 0 40px rgba(99,102,241,0.45), 0 0 80px rgba(139,92,246,0.20), 0 0 120px rgba(34,211,238,0.10)',
                position: 'relative',
              }}
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.2 }}
            >
              {/* Logo shimmer */}
              <div style={{
                position: 'absolute',
                inset: -2,
                borderRadius: 18,
                background: 'conic-gradient(from 0deg, transparent 0%, rgba(255,255,255,0.1) 10%, transparent 20%)',
                animation: 'spin 4s linear infinite',
              }} />
              <span style={{
                color: '#fff',
                fontSize: 22,
                fontWeight: 800,
                fontFamily: 'var(--font-display)',
                letterSpacing: '-0.5px',
                position: 'relative',
                zIndex: 1,
              }}>
                MC
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              style={{
                fontSize: 26,
                fontWeight: 700,
                fontFamily: 'var(--font-display)',
                background: 'linear-gradient(135deg, #F1F5F9 0%, #A78BFA 50%, #22D3EE 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                marginBottom: 8,
              }}
            >
              MuleCatch
            </motion.h1>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--text-muted)',
                letterSpacing: '1.5px',
                textTransform: 'uppercase',
                height: 16,
              }}
            >
              <TypewriterText
                texts={[
                  'Fraud Intelligence Platform',
                  'Mule Account Detection',
                  'AML Compliance Engine',
                  'Graph Neural Networks',
                ]}
              />
            </motion.div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit}>
            <motion.div
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 }}
              style={{ marginBottom: 18 }}
            >
              <label style={{
                display: 'block',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                color: focused === 'username' ? '#818CF8' : 'var(--text-secondary)',
                marginBottom: 7,
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
                transition: 'color 0.2s',
              }}>
                Username
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  required
                  autoComplete="username"
                  onFocus={() => setFocused('username')}
                  onBlur={() => setFocused(null)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    background: focused === 'username' ? 'rgba(99,102,241,0.06)' : 'var(--bg-elevated)',
                    border: `1px solid ${focused === 'username' ? 'rgba(99,102,241,0.4)' : 'var(--border)'}`,
                    borderRadius: 10,
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13,
                    outline: 'none',
                    transition: 'all 0.25s ease',
                    boxSizing: 'border-box',
                    boxShadow: focused === 'username' ? '0 0 20px rgba(99,102,241,0.12)' : 'none',
                  }}
                />
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 }}
              style={{ marginBottom: 26 }}
            >
              <label style={{
                display: 'block',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                color: focused === 'password' ? '#818CF8' : 'var(--text-secondary)',
                marginBottom: 7,
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
                transition: 'color 0.2s',
              }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                  autoComplete="current-password"
                  onFocus={() => setFocused('password')}
                  onBlur={() => setFocused(null)}
                  style={{
                    width: '100%',
                    padding: '11px 42px 11px 14px',
                    background: focused === 'password' ? 'rgba(99,102,241,0.06)' : 'var(--bg-elevated)',
                    border: `1px solid ${focused === 'password' ? 'rgba(99,102,241,0.4)' : 'var(--border)'}`,
                    borderRadius: 10,
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13,
                    outline: 'none',
                    transition: 'all 0.25s ease',
                    boxSizing: 'border-box',
                    boxShadow: focused === 'password' ? '0 0 20px rgba(99,102,241,0.12)' : 'none',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(prev => !prev)}
                  style={{
                    position: 'absolute',
                    right: 12,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 4,
                    display: 'flex',
                    alignItems: 'center',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = '#818CF8'}
                  onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </motion.div>

            {/* Error message */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -8, height: 0 }}
                  animate={{ opacity: 1, y: 0, height: 'auto' }}
                  exit={{ opacity: 0, y: -8, height: 0 }}
                  style={{
                    marginBottom: 18,
                    padding: '10px 14px',
                    borderRadius: 10,
                    background: 'rgba(244,63,94,0.08)',
                    border: '1px solid rgba(244,63,94,0.2)',
                    color: 'var(--critical)',
                    fontSize: 12,
                    fontFamily: 'var(--font-mono)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <Shield size={13} />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            <motion.button
              type="submit"
              disabled={loading || !username || !password}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              style={{
                width: '100%',
                padding: '13px',
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: '0.5px',
                fontFamily: 'var(--font-sans)',
                borderRadius: 10,
                border: 'none',
                cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
                background: loading || !username || !password
                  ? 'rgba(99,102,241,0.2)'
                  : 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A78BFA 100%)',
                color: loading || !username || !password ? 'rgba(255,255,255,0.4)' : '#fff',
                boxShadow: loading || !username || !password
                  ? 'none'
                  : '0 0 20px rgba(99,102,241,0.35), 0 4px 12px rgba(0,0,0,0.4)',
                transition: 'all 0.3s ease',
                position: 'relative',
                overflow: 'hidden',
              }}
              whileHover={!loading && username && password ? {
                boxShadow: '0 0 32px rgba(99,102,241,0.50), 0 0 60px rgba(139,92,246,0.20), 0 4px 16px rgba(0,0,0,0.5)',
                y: -1,
              } : {}}
              whileTap={!loading && username && password ? { scale: 0.98, y: 0 } : {}}
            >
              {/* Button shimmer */}
              {!loading && username && password && (
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.08) 45%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.08) 55%, transparent 60%)',
                  animation: 'shimmer 3s ease-in-out infinite',
                }} />
              )}
              <span style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                {loading && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%' }}
                  />
                )}
                {loading ? 'Authenticating...' : 'Sign In'}
              </span>
            </motion.button>
          </form>

          {/* Footer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
            style={{
              marginTop: 28,
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
            }}>
              {['BCRYPT', 'HS256', 'RBAC'].map((badge, i) => (
                <span key={badge} style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 8,
                  color: 'var(--text-faint)',
                  letterSpacing: '1.2px',
                  padding: '2px 6px',
                  border: '1px solid rgba(255,255,255,0.04)',
                  borderRadius: 3,
                }}>
                  {badge}
                </span>
              ))}
            </div>
            <div style={{
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-faint)',
              letterSpacing: '0.5px',
            }}>
              IOB Fraud Intelligence // Secure Access
            </div>
          </motion.div>
        </GlassCard>
      </motion.div>
    </div>
  );
}
