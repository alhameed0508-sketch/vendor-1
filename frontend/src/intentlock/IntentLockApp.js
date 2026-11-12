import React, { createContext, useContext, useEffect, useState } from 'react';
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api } from './api';
import Icon from './icons';
import { ErrorNote, Spinner } from './parts';
import Dashboard from './Dashboard';
import Ledger from './Ledger';
import { Checkouts, Mandates, Receipts } from './Lists';
import Rules from './Rules';
import Integrations from './Integrations';
import Demo from './DemoPage';
import IntentStudio from './IntentStudio';
import Discovery from './Discovery';
import Monitor from './Monitor';
import Receipt from './Receipt';
import './intentlock.css';

const ConfigContext = createContext(null);
export const useConfig = () => useContext(ConfigContext);

const NAV = [
  ['Monitor', [['/', 'Dashboard', 'dashboard'], ['/ledger', 'Ledger', 'ledger']]],
  ['Purchases', [['/new', 'New purchase', 'plus'], ['/mandates', 'Mandates', 'mandate'], ['/checkouts', 'Checkouts', 'checkout'], ['/receipts', 'Receipts', 'receipt']]],
  ['Controls', [['/rules', 'Policy rules', 'rules']]],
  ['System', [['/integrations', 'Integrations', 'plug'], ['/demo', 'Demo scenarios', 'play']]],
];
const TITLES = [
  [/^\/$/, 'Dashboard'], [/^\/ledger/, 'Ledger'], [/^\/new/, 'New purchase'], [/^\/mandates\/./, 'Choose a product'], [/^\/mandates/, 'Mandates'],
  [/^\/checkouts/, 'Checkouts'], [/^\/checkout\//, 'Checkout'], [/^\/receipts/, 'Receipts'], [/^\/receipt\//, 'Receipt'], [/^\/rules/, 'Policy rules'],
  [/^\/integrations/, 'Integrations'], [/^\/demo/, 'Demo scenarios'],
];
const FLOW = [['/new', 'Terms'], ['/mandates/', 'Product'], ['/checkout/', 'PayPal'], ['/receipt/', 'Receipt']];

function FlowBar({ pathname }) {
  const current = FLOW.findIndex(([prefix]) => (prefix.endsWith('/') ? pathname.startsWith(prefix) && pathname.length > prefix.length : pathname.startsWith(prefix)));
  if (current < 0) return null;
  return (
    <nav className="flowbar" aria-label="Purchase progress">
      <ol>{FLOW.map(([, label], i) => (
        <li key={label} className={i === current ? 'on' : i < current ? 'done' : ''} aria-current={i === current ? 'step' : undefined}><b>{i + 1}</b>{label}</li>
      ))}</ol>
    </nav>
  );
}

function Shell({ config, children }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [pathname]);
  const title = (TITLES.find(([re]) => re.test(pathname)) || [null, 'IntentLock'])[1];
  return (
    <div className={`il ${open ? 'open' : ''}`}>
      <aside className="rail" aria-label="Main navigation">
        <Link to="/" className="rail-brand">
          <span className="rail-mark"><Icon name="lock" size={17} /></span>
          <span><b>Netrava IntentLock</b><small>Merchant console</small></span>
        </Link>
        <nav>
          {NAV.map(([group, items]) => (
            <div key={group}>
              <div className="rail-group">{group}</div>
              {items.map(([to, label, icon]) => (
                <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav ${isActive ? 'on' : ''}`}><Icon name={icon} />{label}</NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="rail-foot">
          <span>PayPal {config ? config.paypal_env : ''}: no real money moves.</span>
          <span>Catalogue: synthetic demo products.</span>
          {config && <span className="mono">{config.policy_version}</span>}
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <div className="main">
        <header className="topbar">
          <button className="btn small menu-btn" aria-label="Open navigation" onClick={() => setOpen(true)}><Icon name="menu" /></button>
          <h1>{title}</h1>
          <span className="spacer" />
          {config && (
            <span className={`status hide-sm ${config.database_durable ? '' : 'warn'}`} title={config.database_durable ? 'Records are stored in PostgreSQL' : 'Records are lost when the server restarts'}>
              <i />PayPal {config.paypal_env} · {config.database_durable ? 'PostgreSQL' : 'temporary database'}
            </span>
          )}
          {!pathname.startsWith('/new') && <button className="btn primary" onClick={() => navigate('/new')}><Icon name="plus" size={16} />New purchase</button>}
        </header>
        <FlowBar pathname={pathname} />
        <main className="content" id="main">{children}</main>
      </div>
    </div>
  );
}

function PublicFrame({ children }) {
  return (
    <div className="il public" style={{ display: 'block' }}>
      <header className="public-head"><div>
        <Link to="/" className="rail-brand" style={{ border: 0, padding: 0 }}><span className="rail-mark"><Icon name="lock" size={17} /></span><span><b>Netrava IntentLock</b><small>Shared receipt</small></span></Link>
      </div></header>
      <main>{children}</main>
    </div>
  );
}

function Loaded() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const { pathname } = useLocation();
  const load = () => { setError(null); api.config().then(setConfig).catch(setError); };
  useEffect(load, []);

  if (pathname.startsWith('/r/')) {
    return <ConfigContext.Provider value={config}><PublicFrame><Routes><Route path="/r/:token" element={<Receipt />} /></Routes></PublicFrame></ConfigContext.Provider>;
  }
  return (
    <ConfigContext.Provider value={config}>
      <Shell config={config}>
        {error ? <ErrorNote error={error} onRetry={load} /> : !config ? <Spinner label="Loading" /> : (
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ledger" element={<Ledger />} />
            <Route path="/new" element={<IntentStudio />} />
            <Route path="/mandates" element={<Mandates />} />
            <Route path="/mandates/:mandateId" element={<Discovery />} />
            <Route path="/mandate/:mandateId" element={<Discovery />} />
            <Route path="/checkouts" element={<Checkouts />} />
            <Route path="/checkout/:checkoutId" element={<Monitor />} />
            <Route path="/receipts" element={<Receipts />} />
            <Route path="/receipt/:receiptId" element={<Receipt />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/integrations" element={<Integrations />} />
            <Route path="/demo" element={<Demo />} />
            <Route path="/activity" element={<Navigate to="/ledger?scope=mine" replace />} />
            <Route path="*" element={<div className="panel empty"><h2>Page not found</h2><Link to="/">Go to the dashboard</Link></div>} />
          </Routes>
        )}
      </Shell>
    </ConfigContext.Provider>
  );
}

export default function IntentLockApp() {
  return <BrowserRouter><Loaded /></BrowserRouter>;
}
