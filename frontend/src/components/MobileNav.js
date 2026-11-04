import React, { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { MoreHorizontal, Moon, Sun, X } from 'lucide-react';
import { useTheme } from '../ThemeContext';
import { NAV_SECTIONS, isActivePath } from './navItems';
import LogoutButton from './LogoutButton';

const [PLATFORM, INTELLIGENCE, OPERATIONS] = NAV_SECTIONS.map(section => section.items);
// Phone tab bar: Command center plus the intelligence pages. Everything else goes in the "More" sheet.
const CORE = [PLATFORM[0], ...INTELLIGENCE];
const OTHER = [...PLATFORM.slice(1), ...OPERATIONS];

/** Phone navigation: core pages in a bottom tab bar, the rest in a "More" sheet. */
export default function MobileNav() {
  const { pathname } = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const moreRef = useRef(null);
  const closeRef = useRef(null);

  const close = () => {
    setOpen(false);
    moreRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = event => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      moreRef.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const moreActive = OTHER.some(item => isActivePath(item, pathname));

  return (
    <>
      <nav className="mobile-tabs" aria-label="Main">
        {CORE.map(({ path, label, icon: Icon, end }) => (
          <NavLink
            key={path}
            to={path}
            end={end}
            className={({ isActive }) => `mobile-tab ${isActive ? 'mobile-tab-active' : ''}`}
          >
            <Icon size={20} aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
        <button
          ref={moreRef}
          type="button"
          className={`mobile-tab ${moreActive || open ? 'mobile-tab-active' : ''}`}
          aria-label="More pages"
          aria-expanded={open}
          onClick={() => setOpen(true)}
        >
          <MoreHorizontal size={20} aria-hidden="true" />
          <span>More</span>
        </button>
      </nav>

      {open && (
        <div className="mobile-sheet-layer">
          <button type="button" className="mobile-sheet-backdrop" tabIndex={-1} aria-hidden="true" onClick={close} />
          <div className="mobile-sheet" role="dialog" aria-modal="true" aria-label="More pages">
            <div className="mobile-sheet-head">
              <span>More pages</span>
              <button ref={closeRef} type="button" className="mobile-sheet-close" aria-label="Close" onClick={close}>
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            {OTHER.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) => `mobile-sheet-link ${isActive ? 'mobile-sheet-link-active' : ''}`}
                onClick={() => setOpen(false)}
              >
                <Icon size={18} aria-hidden="true" />
                {label}
              </NavLink>
            ))}
            <button type="button" className="mobile-sheet-link mobile-sheet-theme" onClick={toggleTheme}>
              {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
              {theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            </button>
            <LogoutButton variant="sheet" />
          </div>
        </div>
      )}
    </>
  );
}
