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

const mockApi = routes => {
  global.fetch = jest.fn(url => {
    const route = Object.keys(routes).find(suffix => url.endsWith(suffix));
    return route ? routes[route] : reply(401, null);
  });
};

const GUEST_SESSION = () => reply(200, { access_token: 'guest.e30.sig', refresh_token: 'guest-refresh' });

beforeEach(() => {
  localStorage.clear();
  mockApi({ '/auth/guest': GUEST_SESSION() });
});

afterEach(() => { delete global.fetch; });

const fillCredentials = async (username = 'investigator', password = 'secret-pass') => {
  await userEvent.type(await screen.findByLabelText('Username'), username);
  await userEvent.type(screen.getByLabelText('Password'), password);
};

describe('LoginPage guest access', () => {
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
    mockApi({
      '/auth/guest': Promise.resolve({ ok: false, status: 403, json: () => Promise.resolve({
        success: false, data: null, error: { code: 'AUTHORIZATION_ERROR', message: 'Guest access is only available in the demo' },
      }) }),
    });
    renderLogin();
    await userEvent.click(await screen.findByRole('button', { name: 'View as guest' }));

    expect(await screen.findByText('Guest access is only available in the demo')).toBeInTheDocument();
  });
});

describe('LoginPage hero', () => {
  it('says what the product does in plain words', async () => {
    renderLogin();
    expect(await screen.findByRole('heading', { level: 1, name: 'Trace mule accounts. Close fraud complaints on time.' })).toBeInTheDocument();
    expect(screen.getByText(/tamper-evident evidence chain for every fraud complaint/)).toBeInTheDocument();
  });

  it('lists only what the product really does', async () => {
    renderLogin();
    const features = await screen.findByRole('list', { name: 'What MuleCatch gives you' });
    expect(features).toHaveTextContent('Role-based access');
    expect(features).toHaveTextContent('Hash-chained evidence');
    expect(features).toHaveTextContent('RBI complaint deadlines');
    expect(document.body).not.toHaveTextContent(/AES-256|ISO 27001|OAuth2|Certified/);
  });

  it('draws the money-flow example with a text description for screen readers', async () => {
    renderLogin();
    expect(await screen.findByRole('img', { name: /three source accounts feed one aggregator/ })).toBeInTheDocument();
  });
});

describe('LoginPage sign-in form', () => {
  it('labels both fields so they can be found by name', async () => {
    renderLogin();
    expect(await screen.findByLabelText('Username')).toHaveAttribute('placeholder', 'Enter username');
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
  });

  it('keeps Sign In disabled until both fields are filled', async () => {
    renderLogin();
    const submit = await screen.findByRole('button', { name: /^Sign In/ });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Username'), 'investigator');
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Password'), 'secret-pass');
    expect(submit).toBeEnabled();
  });

  it('signs in and opens the home page', async () => {
    mockApi({ '/auth/login': reply(200, { access_token: 'user.e30.sig', refresh_token: 'user-refresh', user: { username: 'investigator' } }) });
    renderLogin();
    await fillCredentials();
    await userEvent.click(screen.getByRole('button', { name: /^Sign In/ }));

    expect(await screen.findByText('home page')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ username: 'investigator', password: 'secret-pass' }),
    }));
    expect(getToken()).toBe('user.e30.sig');
  });

  it('shows the server message when the password is wrong, as an alert', async () => {
    mockApi({ '/auth/login': reply(401, { detail: 'Invalid username or password' }) });
    renderLogin();
    await fillCredentials();
    await userEvent.click(screen.getByRole('button', { name: /^Sign In/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password');
    expect(screen.queryByText('home page')).not.toBeInTheDocument();
  });

  it('tells a locked-out user to contact the administrator', async () => {
    mockApi({ '/auth/login': reply(423, { detail: 'Account locked for 15 minutes' }) });
    renderLogin();
    await fillCredentials();
    await userEvent.click(screen.getByRole('button', { name: /^Sign In/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Account locked. Please contact your administrator.');
  });

  it('shows and hides the password on request', async () => {
    renderLogin();
    const password = await screen.findByLabelText('Password');
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
  });

  it('answers "Forgot password?" on the page, without a browser pop-up', async () => {
    window.alert = jest.fn();
    renderLogin();
    const forgot = await screen.findByRole('button', { name: 'Forgot password?' });
    expect(forgot).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(forgot);

    expect(forgot).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('note')).toHaveTextContent('Password resets go through your bank administrator.');
    expect(window.alert).not.toHaveBeenCalled();
  });
});
