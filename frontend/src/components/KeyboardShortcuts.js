import React, { useEffect, useState, useCallback } from 'react';

const SHORTCUTS = [
  { keys: ['J'], desc: 'Next alert in queue' },
  { keys: ['K'], desc: 'Previous alert in queue' },
  { keys: ['Enter'], desc: 'Open selected alert' },
  { keys: ['Escape'], desc: 'Go back / close modal' },
  { keys: ['?'], desc: 'Show keyboard shortcuts' },
  { keys: ['R'], desc: 'Refresh data' },
  { keys: ['/'], desc: 'Focus search' },
];

export function ShortcutsModal({ open, onClose }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === 'Escape' || e.key === '?') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'color-mix(in srgb, var(--bg-void) 70%, transparent)', backdropFilter: 'blur(4px)',
        animation: 'fadeIn 0.2s ease both',
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{
          width: 400, maxHeight: '80vh', overflow: 'auto',
          animation: 'fadeInUp 0.3s ease both',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>Keyboard Shortcuts</h3>
          <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 12 }} onClick={onClose}>ESC</button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {SHORTCUTS.map(s => (
            <div key={s.desc} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{s.desc}</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {s.keys.map(k => (
                  <kbd key={k} style={{
                    background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                    borderRadius: 4, padding: '2px 8px', fontSize: 12,
                    fontFamily: 'var(--font-sans)', color: 'var(--text-primary)',
                    minWidth: 28, textAlign: 'center',
                  }}>{k}</kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function useKeyboardShortcuts({ onNavigate, selectedIndex, setSelectedIndex, alertCount, enabled = true }) {
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const handler = useCallback((e) => {
    if (!enabled) return;
    // Don't capture when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    switch (e.key) {
      case '?':
        e.preventDefault();
        setShortcutsOpen(prev => !prev);
        break;
      case 'j':
      case 'J':
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, alertCount - 1));
        break;
      case 'k':
      case 'K':
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        if (selectedIndex >= 0 && onNavigate) {
          e.preventDefault();
          onNavigate(selectedIndex);
        }
        break;
      case 'Escape':
        setShortcutsOpen(false);
        break;
      case 'r':
      case 'R':
        if (!e.ctrlKey && !e.metaKey) {
          e.preventDefault();
          window.location.reload();
        }
        break;
      default:
        break;
    }
  }, [enabled, selectedIndex, alertCount, onNavigate, setSelectedIndex]);

  useEffect(() => {
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handler]);

  return { shortcutsOpen, setShortcutsOpen };
}
