import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import LogoutButton from './LogoutButton';
import AuthContext from '../auth/AuthContext';

const renderWithAuth = (auth) =>
  render(
    <MemoryRouter initialEntries={['/live']}>
      <AuthContext.Provider value={auth}>
        <Routes>
          <Route path="/live" element={<LogoutButton collapsed={false} />} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>
  );

describe('LogoutButton', () => {
  it('renders nothing when the user is not signed in', () => {
    renderWithAuth({ isAuthenticated: false, logout: jest.fn() });
    expect(screen.queryByRole('button', { name: /log out/i })).not.toBeInTheDocument();
  });

  it('renders nothing outside an AuthProvider', () => {
    render(
      <MemoryRouter>
        <LogoutButton collapsed={false} />
      </MemoryRouter>
    );
    expect(screen.queryByRole('button', { name: /log out/i })).not.toBeInTheDocument();
  });

  it('logs out and goes to the login page', async () => {
    const logout = jest.fn();
    renderWithAuth({ isAuthenticated: true, logout });

    await userEvent.click(screen.getByRole('button', { name: /log out/i }));

    expect(logout).toHaveBeenCalledTimes(1);
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('keeps an accessible name when collapsed', () => {
    render(
      <MemoryRouter>
        <AuthContext.Provider value={{ isAuthenticated: true, logout: jest.fn() }}>
          <LogoutButton collapsed />
        </AuthContext.Provider>
      </MemoryRouter>
    );
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
    expect(screen.queryByText('Log out')).not.toBeInTheDocument();
  });
});
