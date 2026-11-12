import React, { createContext, useContext, useEffect, useState } from 'react';
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom';
import { api } from './api';
import { ErrorNote, Spinner } from './parts';
import IntentStudio from './IntentStudio';
import Discovery from './Discovery';
import Monitor from './Monitor';
import Receipt from './Receipt';
import Activity from './Activity';
import './intentlock.css';
import './intentlock-more.css';

const ConfigContext = createContext(null);
export const useConfig = () => useContext(ConfigContext);

const STEPS = [
  { label: 'Your instructions', match: /^\/$/ },
  { label: 'Choose a product', match: /^\/mandate\// },
  { label: 'Pay with PayPal', match: /^\/checkout\// },
  { label: 'Receipt', match: /^\/(receipt|r)\// },
];

function Shell({ children, config }) {
  const { pathname } = useLocation();
  const current = STEPS.findIndex((s) => s.match.test(pathname)); // -1 on pages outside the purchase flow
  return (
    <div className="il">
      <header className="il-top">
        <div className="il-top-in">
          <Link to="/" className="brand" aria-label="Netrava IntentLock, start a new purchase">
            <span className="brand-mark" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <rect x="3" y="7" width="10" height="7" rx="1.6" /><path d="M5.2 7V4.8a2.8 2.8 0 0 1 5.6 0V7" />
              </svg>
            </span>
            <span>Netrava IntentLock<small>Purchase intent integrity for AI commerce</small></span>
          </Link>
          <nav aria-label="Progress" className="grow">
            <ol className="steps">
              {STEPS.map((s, i) => (
                <li key={s.label} className={i === current ? 'on' : i < current ? 'done' : ''} aria-current={i === current ? 'step' : undefined}>
                  <b>{i < current ? '✓' : i + 1}</b>{s.label}
                </li>
              ))}
            </ol>
          </nav>
          <Link to="/activity" className={`nav-link ${pathname === '/activity' ? 'on' : ''}`}>Activity</Link>
        </div>
      </header>
      <main className="il-main">
        {config && !config.database_durable && (
          <div className="notice" style={{ marginBottom: 20 }}>
            This instance stores data in a temporary database, so records are lost when it restarts. Connect PostgreSQL for a durable deployment.
          </div>
        )}
        {children}
      </main>
      <footer className="il-foot">
        <div>
          <span>PayPal {config ? config.paypal_env : ''}: no real money moves.</span>
          <span>Catalogue: synthetic demo products.</span>
          <span>IntentLock checks purchases made through this app only.</span>
          {config && <span className="mono">{config.policy_version}</span>}
        </div>
      </footer>
    </div>
  );
}

function Loaded() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const load = () => { setError(null); api.config().then(setConfig).catch(setError); };
  useEffect(load, []);
  return (
    <ConfigContext.Provider value={config}>
      <Shell config={config}>
        {error ? <ErrorNote error={error} onRetry={load} /> : !config ? <Spinner label="Loading" /> : (
          <Routes>
            <Route path="/" element={<IntentStudio />} />
            <Route path="/mandate/:mandateId" element={<Discovery />} />
            <Route path="/checkout/:checkoutId" element={<Monitor />} />
            <Route path="/receipt/:receiptId" element={<Receipt />} />
            <Route path="/r/:token" element={<Receipt />} />
            <Route path="/activity" element={<Activity />} />
            <Route path="*" element={<div className="card"><h2>Page not found</h2><p className="lede"><Link to="/">Start a new purchase</Link></p></div>} />
          </Routes>
        )}
      </Shell>
    </ConfigContext.Provider>
  );
}

export default function IntentLockApp() {
  return <BrowserRouter><Loaded /></BrowserRouter>;
}
