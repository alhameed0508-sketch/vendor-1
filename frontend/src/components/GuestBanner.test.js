import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AuthContext from '../auth/AuthContext';
import GuestBanner from './GuestBanner';

const renderWithAuth = auth => render(
  <MemoryRouter initialEntries={['/queue']}>
    <AuthContext.Provider value={auth}>
      <Routes>
        <Route path="/queue" element={<GuestBanner />} />
        <Route path="/login" element={<div>login page</div>} />
      </Routes>
    </AuthContext.Provider>
  </MemoryRouter>
);

describe('GuestBanner', () => {
  it('stays hidden for signed-in staff', () => {
    renderWithAuth({ isAuthenticated: true, isGuest: false, logout: jest.fn() });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('stays hidden outside an AuthProvider', () => {
    render(<MemoryRouter><GuestBanner /></MemoryRouter>);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('tells a guest the view is read only', () => {
    renderWithAuth({ isAuthenticated: true, isGuest: true, logout: jest.fn() });
    expect(screen.getByRole('status')).toHaveTextContent('You are viewing as a guest. Sign in to change anything.');
  });

  it('ends the guest session and opens the sign-in page', async () => {
    const logout = jest.fn();
    renderWithAuth({ isAuthenticated: true, isGuest: true, logout });
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(logout).toHaveBeenCalled();
    expect(screen.getByText('login page')).toBeInTheDocument();
  });
});
