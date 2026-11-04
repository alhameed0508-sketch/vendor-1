import { getToken, setToken, getRefreshToken, setRefreshToken, clearTokens, apiFetch } from './api';

describe('Token management', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and retrieves access token', () => {
    setToken('test-access-token');
    expect(getToken()).toBe('test-access-token');
  });

  it('stores and retrieves refresh token', () => {
    setRefreshToken('test-refresh-token');
    expect(getRefreshToken()).toBe('test-refresh-token');
  });

  it('clears both tokens', () => {
    setToken('access');
    setRefreshToken('refresh');
    clearTokens();
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});

describe('apiFetch', () => {
  beforeEach(() => {
    localStorage.clear();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('attaches Bearer header when token exists', async () => {
    setToken('my-token');
    global.fetch.mockResolvedValue({ status: 200, ok: true });

    await apiFetch('/api/v1/test');

    expect(global.fetch).toHaveBeenCalledWith('/api/v1/test', {
      headers: { Authorization: 'Bearer my-token' },
    });
  });

  it('does not attach Authorization header when no token', async () => {
    global.fetch.mockResolvedValue({ status: 200, ok: true });

    await apiFetch('/api/v1/test');

    expect(global.fetch).toHaveBeenCalledWith('/api/v1/test', {
      headers: {},
    });
  });

  it('attempts refresh on 401 response', async () => {
    setToken('expired-token');
    setRefreshToken('valid-refresh');

    // First call returns 401
    global.fetch.mockResolvedValueOnce({ status: 401, ok: false });
    // Refresh call succeeds
    global.fetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => ({ data: { access_token: 'new-token' } }),
    });
    // Retry call succeeds
    global.fetch.mockResolvedValueOnce({ status: 200, ok: true });

    const result = await apiFetch('/api/v1/protected');

    expect(result.status).toBe(200);
    expect(getToken()).toBe('new-token');
  });

  it('clears tokens and redirects on failed refresh', async () => {
    setToken('expired-token');
    setRefreshToken('also-expired');

    // Original call returns 401
    global.fetch.mockResolvedValueOnce({ status: 401, ok: false });
    // Refresh call fails
    global.fetch.mockResolvedValueOnce({ status: 401, ok: false });

    // Mock window.location
    delete window.location;
    window.location = { pathname: '/dashboard', href: '' };

    await apiFetch('/api/v1/protected');

    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(window.location.href).toBe('/login');
  });
});
