import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../auth/AuthContext';
import { Shield, Lock, Fingerprint, Eye, EyeOff, Activity, CheckCircle2, ArrowRight } from 'lucide-react';
import './Login.css';

/* ── Typewriter Tagline ── */
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
        width: 2,
        height: '1.1em',
        background: 'var(--accent-primary)',
        marginLeft: 4,
        animation: 'cursorBlink 1s step-end infinite',
        verticalAlign: 'text-bottom',
      }} />
    </span>
  );
}

/* ── SVG Network Visual Graphic for Left Panel ── */
function NetworkHeroGraphic() {
  return (
    <div style={{ width: '100%', height: 260, position: 'relative', overflow: 'hidden' }}>
      <svg width="100%" height="100%" viewBox="0 0 500 260" fill="none">
        {/* Connection Lines */}
        <line x1="80" y1="130" x2="210" y2="70" stroke="var(--border-strong)" strokeWidth="1.5" strokeDasharray="4 4" />
        <line x1="80" y1="130" x2="210" y2="190" stroke="var(--border-strong)" strokeWidth="1.5" strokeDasharray="4 4" />
        <line x1="210" y1="70" x2="350" y2="130" stroke="var(--accent-primary)" strokeWidth="2" opacity="0.6" />
        <line x1="210" y1="190" x2="350" y2="130" stroke="var(--critical)" strokeWidth="2" opacity="0.6" />
        <line x1="350" y1="130" x2="440" y2="130" stroke="var(--accent-primary)" strokeWidth="2" />

        {/* Pulsing Nodes */}
        <circle cx="80" cy="130" r="14" fill="var(--bg-elevated)" stroke="var(--border-strong)" strokeWidth="2" />
        <circle cx="80" cy="130" r="5" fill="var(--text-muted)" />

        <circle cx="210" cy="70" r="16" fill="var(--bg-elevated)" stroke="var(--accent-primary)" strokeWidth="2" />
        <circle cx="210" cy="70" r="6" fill="var(--accent-primary)" />

        <circle cx="210" cy="190" r="18" fill="var(--bg-elevated)" stroke="var(--critical)" strokeWidth="2" />
        <circle cx="210" cy="190" r="7" fill="var(--critical)" />

        <circle cx="350" cy="130" r="22" fill="var(--bg-elevated)" stroke="var(--high)" strokeWidth="2" />
        <circle cx="350" cy="130" r="8" fill="var(--high)" />

        <circle cx="440" cy="130" r="12" fill="var(--bg-elevated)" stroke="var(--accent-green)" strokeWidth="2" />
        <circle cx="440" cy="130" r="4" fill="var(--accent-green)" />
      </svg>
    </div>
  );
}

export default function LoginPage() {
  const { login, loginAsGuest, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
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
        setError('Account locked. Please contact your system administrator.');
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGuest = async () => {
    setError('');
    setLoading(true);
    try {
      await loginAsGuest();
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Guest access failed');
      setLoading(false);
    }
  };

  return (
    <div className="lg-shell" style={{
      minHeight: '100vh',
      width: '100vw',
      display: 'flex',
      background: 'var(--bg-base)',
      color: 'var(--text-primary)',
      overflow: 'hidden',
    }}>
      {/* ── Left Hero Panel (Enterprise Branding & Graphic) ── */}
      <div className="lg-hero" style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '48px 64px',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        position: 'relative',
      }}>
        {/* Header Branding */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 32 }}>
            <div style={{
              width: 38, height: 38,
              borderRadius: 10,
              background: 'var(--gradient-brand)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700,
              fontFamily: 'var(--font-display)',
              color: 'var(--on-accent)',
              fontSize: 14,
              boxShadow: 'var(--shadow-blue)',
            }}>
              MC
            </div>
            <div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, margin: 0, letterSpacing: '-0.3px' }}>
                MuleCatch
              </h2>
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', margin: 0, textTransform: 'uppercase', letterSpacing: '1px' }}>
                Enterprise Financial Intelligence
              </p>
            </div>
          </div>

          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 32,
            fontWeight: 700,
            lineHeight: 1.2,
            letterSpacing: '-0.8px',
            marginBottom: 16,
            maxWidth: 460,
          }}>
            Real-time Anti-Money Laundering & Mule Account Detection
          </h1>

          <p style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 14,
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
            maxWidth: 440,
            marginBottom: 24,
          }}>
            Empowering bank fraud analysts and FIU investigators with graph neural networks, typological risk scoring, and automated SAR report generation.
          </p>

          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--accent-primary)',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            minHeight: 24,
          }}>
            <Activity size={14} />
            <TypewriterText
              texts={[
                'Multi-Layer Mule Ring Detection Running',
                'UPI Velocity & Smurfing Pattern Analysis',
                'Automated FIU Compliance Export Enabled',
                'Graph Topological Centrality Engine Online',
              ]}
            />
          </div>
        </div>

        {/* Hero Graphic */}
        <NetworkHeroGraphic />

        {/* Footer Badges */}
        <div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
            {[
              { icon: Shield, label: 'Role-based access' },
              { icon: Lock, label: 'JWT sessions' },
              { icon: Fingerprint, label: 'Hash-chained evidence' },
              { icon: CheckCircle2, label: 'RBI complaint deadlines' },
            ].map(b => (
              <div key={b.label} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 'var(--radius)',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--text-muted)',
              }}>
                <b.icon size={12} color="var(--accent-primary)" />
                {b.label}
              </div>
            ))}
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-faint)', margin: 0 }}>
            © 2026 MuleCatch. Restricted portal for authorised bank staff.
          </p>
        </div>
      </div>

      {/* ── Right Auth Panel (Form Card) ── */}
      <div className="lg-form" style={{
        width: 480,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 40,
        background: 'var(--bg-base)',
      }}>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          style={{ width: '100%', maxWidth: 360 }}
        >
          <div className="lg-mobile-brand">
            <span className="lg-mobile-mark">MC</span>
            <span>MuleCatch</span>
          </div>

          <div style={{ marginBottom: 32 }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, margin: '0 0 6px', letterSpacing: '-0.4px' }}>
              Sign In to MuleCatch
            </h2>
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
              Enter your credentials to access the analyst workspace
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {/* Username Input */}
            <div style={{ marginBottom: 20 }}>
              <label htmlFor="login-username" style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                fontWeight: 600,
                color: focused === 'username' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                marginBottom: 8,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                transition: 'color 0.15s ease',
              }}>
                Username
              </label>
              <input
                id="login-username"
                className="lg-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="analyst@bank.com"
                required
                autoComplete="username"
                onFocus={() => setFocused('username')}
                onBlur={() => setFocused(null)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  background: 'var(--bg-input)',
                  border: `1px solid ${focused === 'username' ? 'var(--accent-primary)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 14,
                  outline: 'none',
                  boxShadow: focused === 'username' ? 'var(--shadow-glow)' : 'var(--shadow-xs)',
                  transition: 'all 0.15s ease',
                }}
              />
            </div>

            {/* Password Input */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <label htmlFor="login-password" style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                  color: focused === 'password' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  transition: 'color 0.15s ease',
                }}>
                  Password
                </label>
                <button
                  type="button"
                  className="lg-link"
                  style={{
                    background: 'none',
                    border: 'none',
                    fontFamily: 'var(--font-sans)',
                    fontSize: 11,
                    color: 'var(--accent-primary)',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                  onClick={() => alert('Please contact your FIU Security Administrator to reset your password.')}
                >
                  Forgot Password?
                </button>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  id="login-password"
                  className="lg-input"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  autoComplete="current-password"
                  onFocus={() => setFocused('password')}
                  onBlur={() => setFocused(null)}
                  style={{
                    width: '100%',
                    padding: '10px 40px 10px 14px',
                    background: 'var(--bg-input)',
                    border: `1px solid ${focused === 'password' ? 'var(--accent-primary)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                    fontSize: 14,
                    outline: 'none',
                    boxShadow: focused === 'password' ? 'var(--shadow-glow)' : 'var(--shadow-xs)',
                    transition: 'all 0.15s ease',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(prev => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="lg-reveal"
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
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Remember Me */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-start', marginBottom: 24 }}>
              <label
                htmlFor="remember"
                className="lg-remember"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  id="remember"
                  checked={rememberMe}
                  onChange={e => setRememberMe(e.target.checked)}
                  style={{
                    width: 16,
                    height: 16,
                    accentColor: 'var(--accent-primary)',
                    cursor: 'pointer',
                    margin: 0,
                  }}
                />
                <span>Remember session on this device</span>
              </label>
            </div>

            {/* Error Banner */}
            <AnimatePresence>
              {error && (
                <motion.div
                  role="alert"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  style={{
                    marginBottom: 20,
                    padding: '10px 14px',
                    borderRadius: 'var(--radius)',
                    background: 'var(--critical-dim)',
                    border: '1px solid var(--critical)',
                    color: 'var(--critical)',
                    fontSize: 12,
                    fontFamily: 'var(--font-mono)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <Shield size={14} />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !username || !password}
              className="btn"
              style={{
                width: '100%',
                padding: '12px',
                fontSize: 14,
                fontWeight: 600,
                borderRadius: 'var(--radius)',
                background: loading || !username || !password ? 'var(--border-strong)' : 'var(--accent-primary)',
                color: 'var(--on-accent)',
                border: 'none',
                cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                boxShadow: loading || !username || !password ? 'none' : 'var(--shadow-blue)',
                transition: 'all 0.2s ease',
              }}
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <button
            type="button"
            onClick={handleGuest}
            disabled={loading}
            className="btn btn-ghost lg-guest"
            style={{ width: '100%', marginTop: 12, padding: '12px', fontSize: 14, borderRadius: 'var(--radius)' }}
          >
            View as guest
          </button>
          <p style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', margin: '10px 0 0', textAlign: 'center' }}>
            No password needed. Guests can look around but not change anything.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
