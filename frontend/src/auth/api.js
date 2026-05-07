/**
 * Authenticated fetch wrapper.
 * Adds Authorization header and handles 401 with token refresh + retry.
 */

const TOKEN_KEY = 'mulecatch_access_token';
const REFRESH_KEY = 'mulecatch_refresh_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token) {
  localStorage.setItem(REFRESH_KEY, token);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/**
 * Attempt to refresh the access token using the refresh token.
 * Returns the new access token on success, or null on failure.
 */
async function attemptRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) return null;

    const body = await res.json();
    const data = body?.data || body;
    if (data.access_token) {
      setToken(data.access_token);
      if (data.refresh_token) {
        setRefreshToken(data.refresh_token);
      }
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Drop-in replacement for fetch() that attaches the Bearer token.
 * On 401: attempts one token refresh and retries.
 * If refresh also fails, clears tokens and redirects to /login.
 */
export async function apiFetch(url, options = {}) {
  const token = getToken();

  const headers = {
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    const newToken = await attemptRefresh();
    if (newToken) {
      const retryHeaders = {
        ...options.headers,
        Authorization: `Bearer ${newToken}`,
      };
      return fetch(url, { ...options, headers: retryHeaders });
    }

    // Refresh failed — clear state and redirect
    clearTokens();
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    return res;
  }

  return res;
}
