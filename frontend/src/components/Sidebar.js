import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle, BarChart2,
  Moon, Sun, Zap, FileCheck,
  Network, Upload
} from 'lucide-react';
import { useTheme } from '../ThemeContext';

const NAV_SECTIONS = [
  {
    label: 'Intelligence',
    items: [
      { path: '/',              label: 'Dashboard',      icon: AlertTriangle,  end: true },
      { path: '/queue',         label: 'Triage Queue',   icon: Zap },
      { path: '/network',       label: 'Network Graph',  icon: Network },
    ],
  },
  {
    label: 'Operations',
    items: [
      { path: '/analytics',     label: 'ROI Analytics',  icon: BarChart2 },
      { path: '/compliance',    label: 'Compliance',     icon: FileCheck },
      { path: '/data-import',  label: 'Data Import',   icon: Upload },
    ],
  },
];

// ── Animation constants ──────────────────────────────────────────────
const SIDEBAR_SPRING = { type: 'spring', stiffness: 280, damping: 28 };
const CONTENT_SPRING = { type: 'spring', stiffness: 300, damping: 28 };

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

// ── Hamburger bar component — 3 bars that morph into X ───────────────
function HamburgerIcon({ isOpen }) {
  const barStyle = {
    display: 'block',
    width: 14,
    height: 1.5,
    borderRadius: 1,
    backgroundColor: '#fff',
    transformOrigin: 'center',
  };

  return (
    <motion.div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 0,
        width: 14,
        height: 14,
        position: 'relative',
      }}
    >
      {/* Top bar → rotates 45° down to form X */}
      <motion.span
        style={{ ...barStyle, position: 'absolute' }}
        animate={{
          rotate: isOpen ? 45 : 0,
          y: isOpen ? 0 : -4,
          width: isOpen ? 12 : 14,
        }}
        transition={{ type: 'spring', stiffness: 400, damping: 22 }}
      />
      {/* Middle bar → fades and scales out */}
      <motion.span
        style={{ ...barStyle, position: 'absolute' }}
        animate={{
          opacity: isOpen ? 0 : 1,
          scaleX: isOpen ? 0.3 : 1,
        }}
        transition={{ duration: 0.15, ease: 'easeInOut' }}
      />
      {/* Bottom bar → rotates -45° up to form X */}
      <motion.span
        style={{ ...barStyle, position: 'absolute' }}
        animate={{
          rotate: isOpen ? -45 : 0,
          y: isOpen ? 0 : 4,
          width: isOpen ? 12 : 14,
        }}
        transition={{ type: 'spring', stiffness: 400, damping: 22 }}
      />
    </motion.div>
  );
}

export default function Sidebar({ stats, collapsed, onToggle }) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const totalAlerts = stats
    ? (stats.critical || 0) + (stats.high || 0) + (stats.medium || 0)
    : 0;

  // Flatten nav items for stagger index
  let itemIndex = 0;

  return (
    <motion.aside
      className="sidebar"
      animate={{ width: collapsed ? 64 : 236 }}
      transition={SIDEBAR_SPRING}
      style={{ overflow: 'hidden' }}
    >

      {/* ── Hamburger + Logo ── */}
      <div className="sidebar-logo">
        <motion.button
          className="sidebar-hamburger"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.92 }}
          transition={{ type: 'spring', stiffness: 400, damping: 22 }}
        >
          <HamburgerIcon isOpen={!collapsed} />
        </motion.button>

        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0, x: -10 }}
              animate={{ opacity: 1, width: 'auto', x: 0 }}
              exit={{ opacity: 0, width: 0, x: -10 }}
              transition={{ ...CONTENT_SPRING, delay: 0.06 }}
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
            initial={{ opacity: 0, x: -10, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, x: 0, height: 'auto', marginBottom: 0 }}
            exit={{ opacity: 0, x: -10, height: 0, marginBottom: 0 }}
            transition={{ ...CONTENT_SPRING, delay: 0.1 }}
          >
            // IOB Fraud Intelligence
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── System health indicator ── */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, x: -10, height: 0 }}
            animate={{ opacity: 1, x: 0, height: 'auto' }}
            exit={{ opacity: 0, x: -10, height: 0 }}
            transition={{ ...CONTENT_SPRING, delay: 0.14 }}
            style={{
              margin: '0 12px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              overflow: 'hidden',
            }}
          >
            <div className="sidebar-health-dot" />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              letterSpacing: '0.5px',
            }}>Online</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Divider ── */}
      <div className="sidebar-divider" />

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
                  initial={{ opacity: 0, x: -10, height: 0, paddingTop: 0, paddingBottom: 0 }}
                  animate={{ opacity: 1, x: 0, height: 'auto', paddingTop: 12, paddingBottom: 6 }}
                  exit={{ opacity: 0, x: -10, height: 0, paddingTop: 0, paddingBottom: 0 }}
                  transition={{ ...CONTENT_SPRING, delay: 0.06 }}
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
              const staggerDelay = 0.03 * itemIndex++;

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
                    style={{ position: 'relative', justifyContent: collapsed ? 'center' : 'flex-start' }}
                  >
                    {/* Shared layout active bar — slides between routes */}
                    {isActive && (
                      <motion.div
                        className="sidebar-active-bar"
                        layoutId="sidebar-active"
                        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                      />
                    )}
                    <motion.span
                      className="sidebar-link-icon"
                      animate={{ scale: collapsed && isActive ? 1.15 : 1 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    >
                      <Icon size={collapsed ? 16 : 14} />
                    </motion.span>
                    <AnimatePresence>
                      {!collapsed && (
                        <motion.span
                          initial={{ opacity: 0, width: 0, x: -8 }}
                          animate={{ opacity: 1, width: 'auto', x: 0 }}
                          exit={{ opacity: 0, width: 0, x: -8 }}
                          transition={{ ...CONTENT_SPRING, delay: staggerDelay }}
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
            transition={{ ...CONTENT_SPRING, delay: 0.12 }}
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
          whileHover={{ y: -1, borderColor: 'var(--accent-primary)' }}
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
                initial={{ opacity: 0, width: 0, x: -6 }}
                animate={{ opacity: 1, width: 'auto', x: 0 }}
                exit={{ opacity: 0, width: 0, x: -6 }}
                transition={CONTENT_SPRING}
                style={{ letterSpacing: '0.5px', overflow: 'hidden', whiteSpace: 'nowrap' }}
              >
                {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </div>
    </motion.aside>
  );
}
