import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle, BarChart2, ChevronLeft,
  Moon, Sun, Zap, FileCheck, UserCheck, Presentation,
  Network, Search, Fingerprint, TrendingUp, ShieldAlert, Flag,
  Scan, Target, Settings, Upload
} from 'lucide-react';
import { useTheme } from '../ThemeContext';

const NAV_SECTIONS = [
  {
    label: 'Intelligence',
    items: [
      { path: '/',              label: 'Dashboard',      icon: AlertTriangle,  end: true },
      { path: '/queue',         label: 'Triage Queue',   icon: Zap },
      { path: '/network',       label: 'Network Graph',  icon: Network },
      { path: '/investigation', label: 'Investigation',  icon: Search },
      { path: '/typology',      label: 'Typology',       icon: Fingerprint },
      { path: '/propensity',    label: 'Propensity',     icon: TrendingUp },
      { path: '/scam',          label: 'Scam Detection', icon: ShieldAlert },
      { path: '/india',         label: 'India',          icon: Flag },
      { path: '/screening',    label: 'Screening',     icon: Scan },
    ],
  },
  {
    label: 'Operations',
    items: [
      { path: '/analytics',     label: 'ROI Analytics',  icon: BarChart2 },
      { path: '/compliance',    label: 'Compliance',     icon: FileCheck },
      { path: '/onboarding',    label: 'Onboarding',     icon: UserCheck },
      { path: '/benchmark',    label: 'Benchmarks',    icon: Target },
      { path: '/judge',         label: 'Judge View',     icon: Presentation },
      { path: '/data-import',  label: 'Data Import',   icon: Upload },
      { path: '/system',       label: 'System Ops',    icon: Settings },
    ],
  },
];

// Staggered nav container
const navContainerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

// Individual nav item spring-in
const navItemVariants = {
  hidden: { opacity: 0, x: -12 },
  show: {
    opacity: 1,
    x: 0,
    transition: { type: 'spring', stiffness: 300, damping: 24 },
  },
};

export default function Sidebar({ stats, collapsed, onToggle }) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const totalAlerts = stats
    ? (stats.critical || 0) + (stats.high || 0) + (stats.medium || 0)
    : 0;

  return (
    <motion.aside
      className="sidebar"
      animate={{ width: collapsed ? 64 : 236 }}
      transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
      style={{ overflow: 'hidden' }}
    >

      {/* ── Logo ── */}
      <div className="sidebar-logo">
        <motion.div
          className="logo-monogram"
          whileHover={{ scale: 1.08, boxShadow: '0 0 28px rgba(37,99,235,0.60), 0 4px 12px rgba(0,0,0,0.40)' }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
        >
          MC
        </motion.div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.2 }}
              style={{ overflow: 'hidden', minWidth: 0 }}
            >
              <div className="logo-text logo-text-gradient">MuleCatch</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── System tag ── */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            className="logo-tagline"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.2 }}
          >
            // IOB Fraud Intelligence
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── System health indicator ── */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.2 }}
            style={{
              margin: '0 12px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <div style={{
              width: 5, height: 5, borderRadius: '50%',
              background: '#10B981',
              flexShrink: 0,
            }} />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              letterSpacing: '0.5px',
            }}>Online</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Nav ── */}
      <motion.nav
        className="sidebar-nav"
        variants={navContainerVariants}
        initial="hidden"
        animate="show"
      >
        {NAV_SECTIONS.map(section => (
          <React.Fragment key={section.label}>
            <AnimatePresence>
              {!collapsed && (
                <motion.div
                  className="sidebar-section-label"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  {section.label}
                </motion.div>
              )}
            </AnimatePresence>
            {section.items.map(item => {
              const isActive = item.end
                ? location.pathname === item.path
                : location.pathname.startsWith(item.path);
              const Icon = item.icon;

              return (
                <motion.div
                  key={item.path}
                  variants={navItemVariants}
                  whileTap={{ scale: 0.98 }}
                >
                  <NavLink
                    to={item.path}
                    end={item.end}
                    className={`sidebar-link ${isActive ? 'sidebar-link-active' : ''}`}
                    title={collapsed ? item.label : undefined}
                    style={{ position: 'relative' }}
                  >
                    {/* Shared layout active bar — slides between routes */}
                    {isActive && (
                      <motion.div
                        className="sidebar-active-bar"
                        layoutId="sidebar-active"
                        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                      />
                    )}
                    <span className="sidebar-link-icon">
                      <Icon size={14} />
                    </span>
                    <AnimatePresence>
                      {!collapsed && (
                        <motion.span
                          initial={{ opacity: 0, width: 0 }}
                          animate={{ opacity: 1, width: 'auto' }}
                          exit={{ opacity: 0, width: 0 }}
                          transition={{ duration: 0.18 }}
                          style={{ fontFamily: 'var(--font-sans)', fontSize: 13, overflow: 'hidden', whiteSpace: 'nowrap' }}
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </NavLink>
                </motion.div>
              );
            })}
          </React.Fragment>
        ))}
      </motion.nav>

      {/* ── Alert Stats ── */}
      <AnimatePresence>
        {!collapsed && stats && totalAlerts > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            style={{ padding: '0 8px 6px', overflow: 'hidden' }}
          >
            <div style={{
              borderTop: '1px solid var(--border)',
              padding: '10px 8px 4px',
            }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: 'var(--text-faint)',
                letterSpacing: '1px',
                textTransform: 'uppercase',
                marginBottom: 6,
                fontWeight: 600,
              }}>Queue</div>

              {[
                { label: 'Critical', value: stats.critical, color: 'var(--critical)' },
                { label: 'High',     value: stats.high,     color: 'var(--high)' },
                { label: 'Medium',   value: stats.medium,   color: 'var(--medium)' },
              ].map(s => (
                <div key={s.label} style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 3,
                  gap: 8,
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    color: 'var(--text-muted)',
                  }}>{s.label}</span>
                  <motion.span
                    key={s.value}
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11,
                      color: s.color,
                      fontWeight: 600,
                    }}
                  >
                    {s.value}
                  </motion.span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Footer ── */}
      <div className="sidebar-footer">
        <motion.button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.97 }}
        >
          <motion.div
            animate={{ rotate: theme === 'dark' ? 0 : 180 }}
            transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {theme === 'dark'
              ? <Sun size={12} />
              : <Moon size={12} />
            }
          </motion.div>
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.18 }}
                style={{ letterSpacing: '0.5px', overflow: 'hidden', whiteSpace: 'nowrap' }}
              >
                {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>

        <motion.button
          className="btn btn-ghost sidebar-collapse-btn"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          whileHover={{ opacity: 1, scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <motion.div
            animate={{ rotate: collapsed ? 180 : 0 }}
            transition={{ duration: 0.3 }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <ChevronLeft size={13} />
          </motion.div>
        </motion.button>
      </div>
    </motion.aside>
  );
}
