import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../auth/AuthContext';
import { getToken } from '../auth/api';
import LoginPage from './LoginPage';

const reply = (status, data) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve({ data }) });

const renderLogin = () => render(
  <AuthProvider>
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>home page</div>} />
      </Routes>
    </MemoryRouter>
  </AuthProvider>
);

beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn(url => (url.endsWith('/auth/guest')
    ? reply(200, { access_token: 'guest.e30.sig', refresh_token: 'guest-refresh' })
    : reply(401, null)));
});

afterEach(() => { delete global.fetch; });

describe('LoginPage', () => {
  it('lets a visitor in as a guest without a password', async () => {
    renderLogin();
    await userEvent.click(await screen.findByRole('button', { name: 'View as guest' }));

    expect(await screen.findByText('home page')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/auth/guest', expect.objectContaining({ method: 'POST' }));
    expect(getToken()).toBe('guest.e30.sig');
  });

  it('says guests can look but not change anything', async () => {
    renderLogin();
    expect(await screen.findByText('No password needed. Guests can look around but not change anything.')).toBeInTheDocument();
  });

  it('shows the reason when guest access is refused', async () => {
    global.fetch = jest.fn(url => (url.endsWith('/auth/guest')
      ? Promise.resolve({ ok: false, status: 403, json: () => Promise.resolve({
        success: false, data: null, error: { code: 'AUTHORIZATION_ERROR', message: 'Guest access is only available in the demo' },
      }) })
      : reply(401, null)));
    renderLogin();
    await userEvent.click(await screen.findByRole('button', { name: 'View as guest' }));

    expect(await screen.findByText('Guest access is only available in the demo')).toBeInTheDocument();
  });
});
