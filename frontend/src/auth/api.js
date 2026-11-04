/**
 * Authenticated fetch wrapper.
 * Adds Authorization header and handles 401 with token refresh + retry.
 *
 * Base URL resolution:
 * - In development (npm start), CRA proxy forwards /api/* to the backend.
 * - In production builds, set REACT_APP_API_URL to the backend origin
 *   (e.g., "http://localhost:8000") so fetch calls reach the right server.
 */

const TOKEN_KEY = 'mulecatch_access_token';
const REFRESH_KEY = 'mulecatch_refresh_token';

/**
 * The backend base URL. Empty string means "same origin" (works with CRA proxy
 * in dev or when frontend is served by the same host as the backend).
 * Set REACT_APP_API_URL in .env for production builds where frontend and
 * backend run on different origins.
 */
const API_BASE = process.env.REACT_APP_API_URL || '';

/**
 * Resolve a URL path against the API base.
 * If the url is already absolute (starts with http), return as-is.
 * Otherwise prepend API_BASE.
 */
function resolveUrl(url) {
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  return `${API_BASE}${url}`;
}

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
 * The only refresh call in the app: AuthContext reuses it, so the request body
 * stays in step with RefreshRequest in backend/api/v1/schemas/auth.py ({ token }).
 */
export async function attemptRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(resolveUrl('/api/v1/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: refreshToken }),
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
 *
 * URL paths (e.g., '/api/v1/alerts') are resolved against API_BASE.
 * Absolute URLs are used as-is.
 */
export async function apiFetch(url, options = {}) {
  const resolvedUrl = resolveUrl(url);
  const token = getToken();

  const headers = {
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(resolvedUrl, { ...options, headers });

  if (res.status === 401) {
    const newToken = await attemptRefresh();
    if (newToken) {
      const retryHeaders = {
        ...options.headers,
        Authorization: `Bearer ${newToken}`,
      };
      return fetch(resolvedUrl, { ...options, headers: retryHeaders });
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

/** Export resolveUrl for use in components that need the base URL. */
export { resolveUrl, API_BASE };
