import React, { useState, useEffect, useCallback } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { alertPath, isSafeInternalPath } from '../utils/safeNavigation';
import { NAV_SECTIONS } from './navItems';

const PAGES = NAV_SECTIONS.flatMap(section => section.items)
  .map(({ path, label, icon }) => ({ name: label, path, Icon: icon }));

export default function CommandPalette({ alerts: alertsProp }) {
  const alerts = alertsProp || [];
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const onSelect = useCallback((value) => {
    setOpen(false);
    if (isSafeInternalPath(value)) {
      navigate(value);
    }
  }, [navigate]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 9990,
              background: 'var(--overlay-bg)',
              backdropFilter: 'blur(4px)',
            }}
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            style={{
              position: 'fixed',
              top: '20%',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 9991,
              width: 560,
              maxHeight: 420,
            }}
          >
            <Command
              label="Command Palette"
              style={{
                background: 'var(--tooltip-bg)',
                border: '1px solid var(--tooltip-border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-lg)',
              }}
            >
              <Command.Input
                placeholder="Search alerts, accounts, pages..."
                style={{
                  width: '100%',
                  padding: '14px 20px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 14,
                  outline: 'none',
                }}
              />
              <Command.List
                style={{
                  maxHeight: 340,
                  overflowY: 'auto',
                  padding: '8px',
                }}
              >
                <Command.Empty style={{
                  padding: '24px',
                  textAlign: 'center',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 12,
                }}>
                  No results found.
                </Command.Empty>

                <Command.Group
                  heading={<span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', letterSpacing: 1, padding: '4px 8px' }}>Pages</span>}
                >
                  {PAGES.map(page => (
                    <Command.Item
                      key={page.path}
                      value={`${page.name} ${page.path}`}
                      onSelect={() => onSelect(page.path)}
                      style={{
                        padding: '10px 12px',
                        borderRadius: 8,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-sans)',
                        fontWeight: 500,
                      }}
                      data-cmdk-item=""
                    >
                      <page.Icon size={16} aria-hidden="true" />
                      {page.name}
                    </Command.Item>
                  ))}
                </Command.Group>

                {alerts.length > 0 && (
                  <Command.Group
                    heading={<span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', padding: '4px 8px' }}>Matching alerts</span>}
                  >
                    {alerts.slice(0, 20).map(alert => (
                      <Command.Item
                        key={alert.alert_id}
                        value={`${alert.alert_id} ${alert.severity} ${alert.reason_codes?.[0] || ''}`}
                        onSelect={() => onSelect(alertPath(alert.alert_id))}
                        style={{
                          padding: '10px 12px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          fontSize: 13,
                          color: 'var(--text-primary)',
                        }}
                        data-cmdk-item=""
                      >
                        <span className={`badge badge-${alert.severity}`} style={{ flexShrink: 0 }}>{alert.severity}</span>
                        <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--accent)' }}>{alert.alert_id}</span>
                        <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                          {(alert.risk_score * 100).toFixed(0)}%
                        </span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
              </Command.List>

              {/* Footer */}
              <div style={{
                padding: '8px 16px',
                borderTop: '1px solid var(--border)',
                display: 'flex',
                gap: 16,
                alignItems: 'center',
              }}>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)' }}>
                  \u2191\u2193 Navigate
                </span>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)' }}>
                  \u23CE Select
                </span>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)' }}>
                  ESC Close
                </span>
              </div>
            </Command>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
