import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, Eye, EyeOff, Shield } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import LoginHero, { BrandMark } from './LoginHero';
import './Login.css';

const LOCKED = 'Account locked. Please contact your administrator.';

export default function LoginPage() {
  const { login, loginAsGuest, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showResetNote, setShowResetNote] = useState(false);

  if (isAuthenticated) {
    navigate('/', { replace: true });
    return null;
  }

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      const message = err.message || 'Login failed';
      setError(message.toLowerCase().includes('lock') ? LOCKED : message);
    } finally {
      setLoading(false);
    }
  };

  const incomplete = loading || !username || !password;

  return (
    <div className="login">
      <LoginHero />

      <main className="login-panel">
        <motion.div
          className="login-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <div className="login-brand login-brand--compact">
            <BrandMark />
            <div className="login-brand__name">MuleCatch</div>
          </div>

          <h2 className="login-card__title">Sign in to MuleCatch</h2>
          <p className="login-card__lead">Enter your credentials to open the analyst workspace</p>

          <form onSubmit={handleSubmit}>
            <div className="login-field">
              <label htmlFor="login-username">Username</label>
              <input
                id="login-username"
                className="login-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
                autoComplete="username"
              />
            </div>

            <div className="login-field">
              <div className="login-field__row">
                <label htmlFor="login-password">Password</label>
                <button
                  type="button"
                  className="login-link"
                  aria-expanded={showResetNote}
                  onClick={() => setShowResetNote(open => !open)}
                >
                  Forgot password?
                </button>
              </div>
              <div className="login-field__control">
                <input
                  id="login-password"
                  className="login-input login-input--padded"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="login-reveal"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setShowPassword(prev => !prev)}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {showResetNote && (
                <p role="note" className="login-note">Password resets go through your bank administrator.</p>
              )}
            </div>

            <AnimatePresence>
              {error && (
                <motion.div
                  role="alert"
                  className="login-error"
                  initial={{ opacity: 0, y: -8, height: 0 }}
                  animate={{ opacity: 1, y: 0, height: 'auto' }}
                  exit={{ opacity: 0, y: -8, height: 0 }}
                >
                  <Shield size={14} aria-hidden="true" />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            <button type="submit" disabled={incomplete} className="btn btn-primary login-submit">
              {loading ? (
                <>
                  <span className="spinner login-submit__spinner" aria-hidden="true" />
                  Authenticating...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight size={16} aria-hidden="true" />
                </>
              )}
            </button>
          </form>

          <button type="button" onClick={handleGuest} disabled={loading} className="btn btn-ghost login-guest">
            View as guest
          </button>
          <p className="login-hint">No password needed. Guests can look around but not change anything.</p>

          <div className="login-footer">IOB Fraud Intelligence</div>
        </motion.div>
      </main>
    </div>
  );
}
