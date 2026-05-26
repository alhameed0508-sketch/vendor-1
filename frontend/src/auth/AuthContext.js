import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  getToken,
  setToken,
  getRefreshToken,
  setRefreshToken,
  clearTokens,
  resolveUrl,
} from './api';

const AuthContext = createContext(null);

/**
 * Decode JWT payload to extract expiry (exp) without a library.
 * Returns the payload object or null if parsing fails.
 */
function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);
  const refreshIntervalRef = useRef(null);

  /**
   * Refresh the access token using the stored refresh token.
   */
  const refreshToken = useCallback(async () => {
    const currentRefresh = getRefreshToken();
    if (!currentRefresh) return false;

    try {
      const res = await fetch(resolveUrl('/api/v1/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: currentRefresh }),
      });

      if (!res.ok) return false;

      const body = await res.json();
      const data = body?.data || body;
      if (data.access_token) {
        setToken(data.access_token);
        if (data.refresh_token) {
          setRefreshToken(data.refresh_token);
        }
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  /**
   * Set up auto-refresh interval based on token expiry.
   * Refreshes 60 seconds before expiry.
   */
  const scheduleRefresh = useCallback((token) => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }

    const payload = decodeJwtPayload(token);
    if (!payload || !payload.exp) {
      // If no expiry, refresh every 4 minutes as a safe default
      refreshIntervalRef.current = setInterval(refreshToken, 4 * 60 * 1000);
      return;
    }

    const expiresInMs = payload.exp * 1000 - Date.now();
    // Refresh 60s before expiry, but at least every 30s
    const refreshInMs = Math.max(expiresInMs - 60000, 30000);

    refreshIntervalRef.current = setInterval(refreshToken, refreshInMs);
  }, [refreshToken]);

  /**
   * Login with username and password.
   */
  const login = useCallback(async (username, password) => {
    const res = await fetch(resolveUrl('/api/v1/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const body = await res.json();
    const data = body?.data || body;

    if (!res.ok) {
      const error = data?.detail || data?.message || 'Login failed';
      throw new Error(error);
    }

    if (data.access_token) {
      setToken(data.access_token);
      if (data.refresh_token) {
        setRefreshToken(data.refresh_token);
      }
      setUser(data.user || { username });
      setIsAuthenticated(true);
      setAuthError(null);
      scheduleRefresh(data.access_token);
      return data;
    }

    throw new Error('No access token in response');
  }, [scheduleRefresh]);

  /**
   * Logout — clear tokens and state.
   */
  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setIsAuthenticated(false);
    setAuthError(null);
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
  }, []);

  /**
   * On mount, check token validity via /api/v1/auth/me.
   */
  useEffect(() => {
    const checkAuth = async () => {
      const token = getToken();

      try {
        const res = await fetch(resolveUrl('/api/v1/auth/me'), {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

        if (res.ok) {
          const body = await res.json();
          const data = body?.data || body;

          if (data?.auth_enabled === false) {
            // Auth is disabled on the server — allow access
            setIsAuthenticated(true);
            setUser(data.user || { username: data?.user_id || 'system' });
          } else if (token && (data?.username || data?.user_id)) {
            // Valid authenticated session
            setUser(data);
            setIsAuthenticated(true);
            scheduleRefresh(token);
          } else {
            // No valid session
            setIsAuthenticated(false);
          }
        } else if (res.status === 401) {
          // Try refreshing
          const refreshed = await refreshToken();
          if (refreshed) {
            // Retry /me with new token
            const newToken = getToken();
            const retryRes = await fetch(resolveUrl('/api/v1/auth/me'), {
              headers: { Authorization: `Bearer ${newToken}` },
            });
            if (retryRes.ok) {
              const retryBody = await retryRes.json();
              const retryData = retryBody?.data || retryBody;
              setUser(retryData);
              setIsAuthenticated(true);
              scheduleRefresh(newToken);
            } else {
              clearTokens();
              setIsAuthenticated(false);
            }
          } else {
            clearTokens();
            setIsAuthenticated(false);
          }
        } else {
          // Server error — require login
          setIsAuthenticated(false);
          setAuthError('Server unavailable. Please try again.');
        }
      } catch {
        // Network error — require login
        setIsAuthenticated(false);
        setAuthError('Cannot connect to server. Please check your connection.');
      }

      setIsLoading(false);
    };

    checkAuth();

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [refreshToken, scheduleRefresh]);

  const value = {
    user,
    isAuthenticated,
    isLoading,
    authError,
    login,
    logout,
    refreshToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
