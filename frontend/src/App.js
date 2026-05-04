import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import Dashboard from './investigator_dashboard/Dashboard';
import AlertDetail from './alert_detail/AlertDetail';
import ROIDashboard from './roi_dashboard/ROIDashboard';
import CompliancePortal from './compliance_portal/CompliancePortal';
import JudgePresentation from './judge_view/JudgePresentation';
import SplashScreen from './splash/SplashScreen';
import DemoTour from './demo/DemoTour';
import Sidebar from './components/Sidebar';
import ErrorBoundary from './components/ErrorBoundary';
import CommandPalette from './components/CommandPalette';
import BackgroundGrid from './components/ui/BackgroundGrid';
import { ShortcutsModal } from './components/KeyboardShortcuts';
import { ThemeProvider, useTheme } from './ThemeContext';

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  enter: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

const pageTransition = {
  type: 'tween',
  ease: [0.25, 0.1, 0.25, 1],
  duration: 0.3,
};

function ThemedToaster() {
  const { theme } = useTheme();
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'var(--tooltip-bg)',
          backdropFilter: 'blur(12px)',
          border: '1px solid var(--tooltip-border)',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-display)',
          fontSize: 13,
          boxShadow: 'var(--shadow)',
          borderRadius: 'var(--radius)',
        },
      }}
      theme={theme}
    />
  );
}

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial="initial"
        animate="enter"
        exit="exit"
        variants={pageVariants}
        transition={pageTransition}
      >
        <Routes location={location}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/alert/:alertId" element={<AlertDetail />} />
          <Route path="/roi" element={<ROIDashboard />} />
          <Route path="/compliance" element={<CompliancePortal />} />
          <Route path="/presentation" element={<JudgePresentation />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function AppContent() {
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [demoMode, setDemoMode] = useState(true);
  const [showSplash, setShowSplash] = useState(
    () => !sessionStorage.getItem('splashShown')
  );
  const [tourActive, setTourActive] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    fetch('/api/auth/me')
      .then(r => {
        if (r.status === 401) setDemoMode(false);
        return r.json();
      })
      .then(data => {
        if (data?.auth_enabled === false) setDemoMode(true);
      })
      .catch(() => setDemoMode(true));

    fetch('/api/graph/stats')
      .then(r => r.json())
      .then(setStats)
      .catch(() => {});

    // Fetch alerts for command palette
    fetch('/api/alerts?limit=50')
      .then(r => r.json())
      .then(data => setAlerts(data.alerts || []))
      .catch(() => {});
  }, []);

  // Global ? shortcut for help
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      if (e.key === '?') {
        e.preventDefault();
        setShortcutsOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleSplashComplete = useCallback(() => {
    sessionStorage.setItem('splashShown', 'true');
    setShowSplash(false);
  }, []);

  const startTour = () => setTourActive(true);
  const endTour = () => setTourActive(false);

  if (showSplash) {
    return <SplashScreen onComplete={handleSplashComplete} />;
  }

  return (
    <motion.div
      className="app-layout"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <BackgroundGrid />

      <ThemedToaster />

      <CommandPalette alerts={alerts} />

      <Sidebar
        stats={stats}
        onStartDemo={startTour}
        tourActive={tourActive}
        demoMode={demoMode}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(prev => !prev)}
      />

      <div className="app-content" style={{ position: 'relative', zIndex: 1 }}>
        {/* Top bar — corner weighted */}
        <header className="app-topbar">
          <div className="topbar-left">
            <span className="topbar-system-tag">[SYSTEM]</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.3px' }}>
              Graph Intelligence · Mule Account Detection
            </span>
          </div>
          <div className="topbar-right">
            {stats && <>
              <motion.span
                className="stat-pill critical"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3, duration: 0.3 }}
              >
                {stats.critical} Critical
              </motion.span>
              <motion.span
                className="stat-pill high"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4, duration: 0.3 }}
              >
                {stats.high} High
              </motion.span>
            </>}
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: 'var(--text-muted)',
                padding: '3px 8px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                letterSpacing: '1px',
                textTransform: 'uppercase',
              }}
            >
              Ctrl+K
            </motion.span>
            <motion.button
              className="btn btn-ghost"
              style={{ padding: '4px 10px', fontSize: 10, letterSpacing: '0.5px' }}
              onClick={() => setShortcutsOpen(true)}
              title="Keyboard shortcuts (?)"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              ?
            </motion.button>
          </div>
        </header>

        <main className="app-main">
          <ErrorBoundary>
            <AnimatedRoutes />
          </ErrorBoundary>
        </main>
      </div>

      {tourActive && <DemoTour onEnd={endTour} />}
      <ShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </motion.div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ThemeProvider>
  );
}
