import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import { useAuth } from './AuthContext';

jest.mock('./AuthContext', () => ({
  useAuth: jest.fn(),
}));

function renderWithRouter(ui, { initialEntries = ['/protected'] } = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/protected" element={ui} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  it('renders children when authenticated', () => {
    useAuth.mockReturnValue({ isAuthenticated: true, isLoading: false });

    renderWithRouter(
      <ProtectedRoute><div>Secret Content</div></ProtectedRoute>
    );

    expect(screen.getByText('Secret Content')).toBeInTheDocument();
  });

  it('shows loading spinner while auth state resolves', () => {
    useAuth.mockReturnValue({ isAuthenticated: false, isLoading: true });

    renderWithRouter(
      <ProtectedRoute><div>Secret Content</div></ProtectedRoute>
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.queryByText('Secret Content')).not.toBeInTheDocument();
  });

  it('redirects to /login when not authenticated', () => {
    useAuth.mockReturnValue({ isAuthenticated: false, isLoading: false });

    renderWithRouter(
      <ProtectedRoute><div>Secret Content</div></ProtectedRoute>
    );

    expect(screen.queryByText('Secret Content')).not.toBeInTheDocument();
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });
});
