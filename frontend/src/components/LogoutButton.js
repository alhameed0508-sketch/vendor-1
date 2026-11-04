import React, { useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LogOut } from 'lucide-react';
import AuthContext from '../auth/AuthContext';

/**
 * Logout button for the sidebar footer, or `variant="sheet"` for the phone
 * "More" sheet. Hidden when nobody is signed in, and when rendered
 * outside an AuthProvider (e.g. isolated Sidebar tests).
 */
export default function LogoutButton({ collapsed, variant = 'sidebar' }) {
  const auth = useContext(AuthContext);
  const navigate = useNavigate();

  if (!auth?.isAuthenticated) return null;

  const handleLogout = () => {
    auth.logout();
    navigate('/login', { replace: true });
  };

  if (variant === 'sheet') {
    return (
      <button type="button" className="mobile-sheet-link" onClick={handleLogout}>
        <LogOut size={18} aria-hidden="true" />
        Log out
      </button>
    );
  }

  return (
    <motion.button
      className="theme-toggle"
      onClick={handleLogout}
      aria-label="Log out"
      title={collapsed ? 'Log out' : undefined}
      whileHover={{ y: -1, borderColor: 'var(--accent-primary)' }}
      whileTap={{ scale: 0.97 }}
    >
      <LogOut size={12} />
      {!collapsed && <span style={{ whiteSpace: 'nowrap' }}>Log out</span>}
    </motion.button>
  );
}
