import React, { useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthContext from '../auth/AuthContext';

/**
 * Tells a guest the app is view-only and offers the way to sign in.
 * Hidden for staff, and outside an AuthProvider (e.g. isolated tests).
 */
export default function GuestBanner() {
  const auth = useContext(AuthContext);
  const navigate = useNavigate();

  if (!auth?.isGuest) return null;

  const signIn = () => {
    auth.logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="guest-banner" role="status">
      <span>You are viewing as a guest. Sign in to change anything.</span>
      <button type="button" className="btn btn-ghost btn-sm" onClick={signIn}>Sign in</button>
    </div>
  );
}
