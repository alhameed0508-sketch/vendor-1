import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../auth/AuthContext';
import { GlassCard } from '../components/ui/GlassCard';
import { Shield, Eye, EyeOff } from 'lucide-react';

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
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
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
                background: 'var(--gradient-brand)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
                boxShadow: '0 0 24px rgba(16,185,129,0.25), 0 4px 12px rgba(0,0,0,0.4)',
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
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

            <h1 style={{
              fontSize: 24,
              fontWeight: 700,
              fontFamily: 'var(--font-display)',
              color: 'var(--text-primary)',
              letterSpacing: '-0.3px',
              marginBottom: 8,
            }}>
              MuleCatch
            </h1>

            <div style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 12,
              color: 'var(--text-muted)',
              }}>
              Fraud Intelligence Platform
            </div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 18 }}>
              <label style={{
                display: 'block',
                fontSize: 12,
                fontFamily: 'var(--font-sans)',
                color: focused === 'username' ? 'var(--accent-secondary)' : 'var(--text-secondary)',
                marginBottom: 7,
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
                    border: `1px solid ${focused === 'username' ? 'rgba(16,185,129,0.35)' : 'var(--border-strong)'}`,
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
            </div>

            <div style={{ marginBottom: 26 }}>
              <label style={{
                display: 'block',
                fontSize: 12,
                fontFamily: 'var(--font-sans)',
                color: focused === 'password' ? 'var(--accent-secondary)' : 'var(--text-secondary)',
                marginBottom: 7,
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
                    border: `1px solid ${focused === 'password' ? 'rgba(16,185,129,0.35)' : 'var(--border-strong)'}`,
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
                  onMouseEnter={e => e.currentTarget.style.color = 'var(--accent-secondary)'}
                  onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

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
                    fontFamily: 'var(--font-sans)',
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

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="btn btn-primary"
              style={{
                width: '100%',
                padding: '12px',
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: '0.3px',
                borderRadius: 10,
                cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
                opacity: loading || !username || !password ? 0.5 : 1,
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                {loading && (
                  <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                )}
                {loading ? 'Authenticating...' : 'Sign In'}
              </span>
            </button>
          </form>

          {/* Footer */}
          <div style={{
            marginTop: 28,
            textAlign: 'center',
            fontSize: 12,
            fontFamily: 'var(--font-sans)',
            color: 'var(--text-faint)',
            }}>
            IOB Fraud Intelligence
          </div>
        </GlassCard>
      </motion.div>
    </div>
  );
}
