import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from './AuthContext';

const b64url = obj => btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const jwt = claims => `${b64url({ alg: 'HS256', typ: 'JWT' })}.${b64url(claims)}.signature`;
const accessToken = (sub, role) => jwt({ sub, role, type: 'access', exp: Math.floor(Date.now() / 1000) + 900 });

const reply = (status, data) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve({ data }) });

function Probe() {
  const { user, isGuest, login, loginAsGuest } = useAuth();
  return (
    <div>
      <button type="button" onClick={() => login('supervisor', 'pw')}>sign in</button>
      <button type="button" onClick={loginAsGuest}>guest</button>
      <span data-testid="user">{user ? `${user.username}:${user.role || 'none'}` : 'signed out'}</span>
      <span data-testid="guest">{String(isGuest)}</span>
    </div>
  );
}

describe('AuthProvider sign-in', () => {
  let meCalls;

  beforeEach(() => {
    localStorage.clear();
    meCalls = 0;
    global.fetch = jest.fn(url => {
      if (url.endsWith('/api/v1/auth/me')) {
        meCalls += 1;
        return reply(401, null);
      }
      if (url.endsWith('/api/v1/auth/login')) {
        return reply(200, { access_token: accessToken('supervisor', 'SUPERVISOR'), refresh_token: 'r' });
      }
      if (url.endsWith('/api/v1/auth/guest')) {
        return reply(200, { access_token: accessToken('guest', 'GUEST'), refresh_token: 'r' });
      }
      return reply(404, null);
    });
  });

  afterEach(() => {
    delete global.fetch;
  });

  it('knows the role straight after a form sign-in, without a reload', async () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(meCalls).toBe(1));

    await userEvent.click(screen.getByRole('button', { name: 'sign in' }));

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('supervisor:SUPERVISOR'));
    expect(meCalls).toBe(1);
  });

  it('keeps the session when the access token has expired, by refreshing it', async () => {
    const fresh = accessToken('investigator', 'INVESTIGATOR');
    localStorage.setItem('mulecatch_access_token', 'expired-access-token');
    localStorage.setItem('mulecatch_refresh_token', 'refresh-1');
    // Behaves like the backend: RefreshRequest takes { token } and rejects anything else with 422.
    global.fetch = jest.fn((url, options = {}) => {
      if (url.endsWith('/api/v1/auth/me')) {
        const auth = options.headers?.Authorization;
        return auth === `Bearer ${fresh}`
          ? reply(200, { user_id: 'investigator', username: 'investigator', role: 'INVESTIGATOR' })
          : reply(401, null);
      }
      if (url.endsWith('/api/v1/auth/refresh')) {
        const sent = JSON.parse(options.body || '{}');
        return sent.token === 'refresh-1' ? reply(200, { access_token: fresh }) : reply(422, null);
      }
      return reply(404, null);
    });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('investigator:INVESTIGATOR'));
    expect(localStorage.getItem('mulecatch_access_token')).toBe(fresh);
  });

  it('marks a guest session as a guest with the GUEST role', async () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(meCalls).toBe(1));

    await userEvent.click(screen.getByRole('button', { name: 'guest' }));

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('guest:GUEST'));
    expect(screen.getByTestId('guest')).toHaveTextContent('true');
  });
});
