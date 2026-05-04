import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useTheme } from '../ThemeContext';

/* ── Minimal SVG icons ── */
const Icons = {
  alerts: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      <circle cx="8" cy="10.5" r="0.6" fill="currentColor"/>
      <line x1="8" y1="6" x2="8" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  ),
  roi: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <polyline points="2,11 5,7 8,9 11,4 14,6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="14" cy="6" r="1" fill="currentColor"/>
    </svg>
  ),
  compliance: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
      <line x1="6" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
      <line x1="6" y1="9" x2="10" y2="9" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
      <line x1="6" y1="12" x2="8" y2="12" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
    </svg>
  ),
  judge: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M3 14c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <path d="M5.5 5L8 2.5 10.5 5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

const NAV_ITEMS = [
  { path: '/', label: 'Alert Queue', icon: 'alerts', end: true },
  { path: '/roi', label: 'ROI Analytics', icon: 'roi' },
  { path: '/compliance', label: 'Compliance / STR', icon: 'compliance' },
  { path: '/presentation', label: 'Presentation', icon: 'judge' },
];

const STAT_COLOR = {
  Critical: 'var(--critical)',
  High: 'var(--high)',
  Medium: 'var(--accent-blue)',
};

export default function Sidebar({ stats, onStartDemo, tourActive, demoMode, collapsed, onToggle }) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const getBadge = (path) => {
    if (!stats) return null;
    if (path === '/') return stats.total_alerts;
    if (path === '/compliance') {
      const strPending = stats.critical + stats.high;
      return strPending > 0 ? strPending : null;
    }
    return null;
  };

  return (
    <motion.aside
      className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}
      layout
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      {/* ── Logo ── */}
      <div className="sidebar-logo">
        <motion.div
          className="logo-monogram"
          whileHover={{ scale: 1.08 }}
          transition={{ type: 'spring', stiffness: 400, damping: 15 }}
        >
          MC
        </motion.div>
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              className="logo-text"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
            >
              MuleCatch
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {!collapsed && (
          <motion.div
            className="sidebar-tag"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            IOB Fraud Intelligence
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Navigation ── */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(item => {
          const badge = getBadge(item.path);
          const isActive = item.end
            ? location.pathname === item.path
            : location.pathname.startsWith(item.path);

          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.end}
              className={({ isActive: active }) =>
                `sidebar-link ${active ? 'sidebar-link-active' : ''}`
              }
              title={collapsed ? item.label : undefined}
              style={{ position: 'relative' }}
            >
              {/* Gradient active indicator */}
              {isActive && (
                <motion.div
                  layoutId="sidebar-active-indicator"
                  className="sidebar-active-bar"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}

              <span className="sidebar-link-icon">
                {Icons[item.icon]}
              </span>

              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    className="sidebar-link-label"
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>

              <AnimatePresence>
                {!collapsed && badge != null && (
                  <motion.span
                    className="sidebar-badge"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 25 }}
                  >
                    {badge}
                  </motion.span>
                )}
              </AnimatePresence>
            </NavLink>
          );
        })}
      </nav>

      {/* ── Stats — dash-separated minimal ── */}
      <AnimatePresence>
        {!collapsed && stats && (
          <motion.div
            className="sidebar-stats"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            {[
              { label: 'Critical', value: stats.critical },
              { label: 'High',     value: stats.high },
              { label: 'Medium',   value: stats.medium },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                className="sidebar-stat-row"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <span
                  className="sidebar-stat-dash"
                  style={{ color: STAT_COLOR[s.label] }}
                >
                  —
                </span>
                <span className="sidebar-stat-label">
                  <span style={{ color: STAT_COLOR[s.label], fontWeight: 600 }}>{s.value}</span>
                  {' '}{s.label}
                </span>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Footer ── */}
      <div className="sidebar-footer">
        <AnimatePresence>
          {!collapsed && !tourActive && (
            <motion.button
              className="btn btn-primary sidebar-demo-btn"
              onClick={onStartDemo}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              ▶ Start Demo
            </motion.button>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {!collapsed && demoMode && (
            <motion.span
              className="sidebar-demo-tag"
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
            >
              // DEMO MODE
            </motion.span>
          )}
        </AnimatePresence>

        <motion.button
          className={`theme-toggle ${collapsed ? 'theme-toggle-collapsed' : ''}`}
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.95 }}
        >
          {theme === 'dark' ? (
            <>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1.06 1.06M11.54 11.54l1.06 1.06M3.4 12.6l1.06-1.06M11.54 4.46l1.06-1.06" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
              {!collapsed && <span>Light Mode</span>}
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M13.5 9.5a5.5 5.5 0 01-7-7 5.5 5.5 0 107 7z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              {!collapsed && <span>Dark Mode</span>}
            </>
          )}
        </motion.button>

        <motion.button
          className="btn btn-ghost sidebar-collapse-btn"
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          whileHover={{ opacity: 1 }}
          whileTap={{ scale: 0.9 }}
        >
          {collapsed ? '»' : '«'}
        </motion.button>
      </div>
    </motion.aside>
  );
}
