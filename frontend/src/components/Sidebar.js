import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  AlertTriangle, BarChart2, Shield, ChevronLeft, ChevronRight,
  Activity, Moon, Sun, Zap, FileCheck, UserCheck, Presentation,
  Network, Search, Brain, Fingerprint, TrendingUp, ShieldAlert, Flag,
  Scan, Target, Settings
} from 'lucide-react';
import { useTheme } from '../ThemeContext';

const NAV_SECTIONS = [
  {
    label: 'Intelligence',
    items: [
      { path: '/',              label: 'Alert Queue',    icon: AlertTriangle,  end: true },
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
      { path: '/system',       label: 'System Ops',    icon: Settings },
    ],
  },
];

export default function Sidebar({ stats, collapsed, onToggle }) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const totalAlerts = stats
    ? (stats.critical || 0) + (stats.high || 0) + (stats.medium || 0)
    : 0;

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>

      {/* ── Logo ── */}
      <div className="sidebar-logo">
        <div className="logo-monogram">MC</div>
        {!collapsed && (
          <div style={{ overflow: 'hidden', minWidth: 0 }}>
            <div className="logo-text logo-text-gradient">MuleCatch</div>
          </div>
        )}
      </div>

      {/* ── System tag ── */}
      {!collapsed && (
        <div className="logo-tagline">// IOB Fraud Intelligence</div>
      )}

      {/* ── System health indicator ── */}
      {!collapsed && (
        <div style={{
          margin: '0 8px 8px',
          padding: '8px 10px',
          background: 'rgba(99,102,241,0.06)',
          border: '1px solid rgba(99,102,241,0.15)',
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          gap: 7,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#818CF8',
            animation: 'emeraldPulse 2s ease-in-out infinite',
            flexShrink: 0,
          }} />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: '#818CF8',
            letterSpacing: '0.8px',
            textTransform: 'uppercase',
          }}>System Online</span>
        </div>
      )}

      {/* ── Nav ── */}
      <nav className="sidebar-nav">
        {NAV_SECTIONS.map(section => (
          <React.Fragment key={section.label}>
            {!collapsed && (
              <div className="sidebar-section-label">{section.label}</div>
            )}
            {section.items.map(item => {
              const isActive = item.end
                ? location.pathname === item.path
                : location.pathname.startsWith(item.path);
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.end}
                  className={`sidebar-link ${isActive ? 'sidebar-link-active' : ''}`}
                  title={collapsed ? item.label : undefined}
                >
                  {isActive && <div className="sidebar-active-bar" />}
                  <span className="sidebar-link-icon">
                    <Icon size={14} />
                  </span>
                  {!collapsed && (
                    <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13 }}>
                      {item.label}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </React.Fragment>
        ))}
      </nav>

      {/* ── Alert Stats ── */}
      {!collapsed && stats && totalAlerts > 0 && (
        <div style={{ padding: '0 8px 8px' }}>
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '10px 12px',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--text-faint)',
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              marginBottom: 8,
              fontWeight: 700,
            }}>Live Queue</div>

            {[
              { label: 'Critical', value: stats.critical, color: 'var(--critical)' },
              { label: 'High',     value: stats.high,     color: 'var(--high)' },
              { label: 'Medium',   value: stats.medium,   color: 'var(--medium)' },
            ].map(s => (
              <div key={s.label} style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 5,
                gap: 8,
              }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                }}>{s.label}</span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: s.color,
                  fontWeight: 700,
                  background: `${s.color}15`,
                  padding: '1px 6px',
                  borderRadius: 4,
                }}>{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Footer ── */}
      <div className="sidebar-footer">
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === 'dark'
            ? <Sun size={12} />
            : <Moon size={12} />
          }
          {!collapsed && (
            <span style={{ letterSpacing: '0.5px' }}>
              {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </span>
          )}
        </button>

        <button
          className="btn btn-ghost sidebar-collapse-btn"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed
            ? <ChevronRight size={13} />
            : <ChevronLeft  size={13} />
          }
        </button>
      </div>
    </aside>
  );
}
