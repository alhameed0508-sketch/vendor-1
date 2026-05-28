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
      initial={{ opacity: 0 }}
      animate={{ opacity: 0.35 }}
      transition={{ duration: 1.5, delay }}
      style={{
        position: 'absolute',
        left: x,
        top: y,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 10px',
        background: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: 16,
        pointerEvents: 'none',
        zIndex: 1,
      }}
    >
      <Icon size={10} color="var(--text-muted)" />
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: 'var(--text-muted)',
        letterSpacing: '0.5px',
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
        <GlassCard className="p-8" hover={false} style={{
          background: 'rgba(14, 14, 22, 0.92)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          {/* Logo */}
          <div style={{ textAlign: 'center', marginBottom: 36 }}>
            <motion.div
              style={{
                width: 56,
                height: 56,
                borderRadius: 14,
                background: 'linear-gradient(135deg, #6366F1 0%, #818CF8 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
                boxShadow: '0 0 24px rgba(99,102,241,0.25), 0 4px 12px rgba(0,0,0,0.4)',
              }}
              initial={{ scale: 0, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 180, damping: 14, delay: 0.2 }}
            >
              <span style={{
                color: '#fff',
                fontSize: 20,
                fontWeight: 700,
                fontFamily: 'var(--font-display)',
                letterSpacing: '-0.5px',
              }}>
                MC
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              style={{
                fontSize: 24,
                fontWeight: 700,
                fontFamily: 'var(--font-display)',
                color: 'var(--text-primary)',
                letterSpacing: '-0.3px',
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
                    padding: '10px 14px',
                    background: 'var(--bg-elevated)',
                    border: `1px solid ${focused === 'username' ? 'rgba(99,102,241,0.35)' : 'var(--border-strong)'}`,
                    borderRadius: 8,
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                    fontSize: 13,
                    outline: 'none',
                    transition: 'border-color 0.15s ease',
                    boxSizing: 'border-box',
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
                    padding: '10px 42px 10px 14px',
                    background: 'var(--bg-elevated)',
                    border: `1px solid ${focused === 'password' ? 'rgba(99,102,241,0.35)' : 'var(--border-strong)'}`,
                    borderRadius: 8,
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                    fontSize: 13,
                    outline: 'none',
                    transition: 'border-color 0.15s ease',
                    boxSizing: 'border-box',
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
                padding: '12px',
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: '0.3px',
                fontFamily: 'var(--font-sans)',
                borderRadius: 10,
                border: 'none',
                cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
                background: loading || !username || !password
                  ? 'rgba(99,102,241,0.15)'
                  : '#6366F1',
                color: loading || !username || !password ? 'rgba(255,255,255,0.35)' : '#fff',
                boxShadow: loading || !username || !password
                  ? 'none'
                  : '0 2px 10px rgba(99,102,241,0.25), 0 1px 4px rgba(0,0,0,0.3)',
                transition: 'all 0.2s ease',
                position: 'relative',
                overflow: 'hidden',
              }}
              whileHover={!loading && username && password ? {
                boxShadow: '0 4px 20px rgba(99,102,241,0.35), 0 2px 8px rgba(0,0,0,0.4)',
                y: -1,
              } : {}}
              whileTap={!loading && username && password ? { scale: 0.98, y: 0 } : {}}
            >
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
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
