import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import Dashboard from './investigator_dashboard/Dashboard';
import AlertDetail from './alert_detail/AlertDetail';
import ROIDashboard from './roi_dashboard/ROIDashboard';
import LoginPage from './login/LoginPage';
import CompliancePortal from './compliance_portal/CompliancePortal';
import NetworkOverview from './network/NetworkOverview';
import AlertQueue from './alert_queue/AlertQueue';
import DataImportPage from './data_import/DataImportPage';
import Sidebar from './components/Sidebar';
import ErrorBoundary from './components/ErrorBoundary';
import BackgroundGrid from './components/ui/BackgroundGrid';
import { ThemeProvider, useTheme } from './ThemeContext';
import { AuthProvider } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import { apiFetch } from './auth/api';

function ThemedToaster() {
  const { theme } = useTheme();
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          borderRadius: 6,
        },
      }}
      theme={theme}
    />
  );
}

function AppContent() {
  const [stats, setStats] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();

  const isLoginPage = location.pathname === '/login';

  useEffect(() => {
    apiFetch('/api/v1/graph/stats')
      .then(r => r.json())
      .then(body => setStats(body?.data || body))
      .catch(err => console.error('[App] Failed to load graph stats:', err));
  }, []);

  return (
    <div className="app-layout">
      <BackgroundGrid />
      <ThemedToaster />

      {!isLoginPage && (
        <Sidebar
          stats={stats}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(prev => !prev)}
        />
      )}

      <div className="app-content">
        <main className="app-main">
          <ErrorBoundary>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/queue" element={<ProtectedRoute><AlertQueue /></ProtectedRoute>} />
              <Route path="/alert/:alertId" element={<ProtectedRoute><AlertDetail /></ProtectedRoute>} />
              <Route path="/network" element={<ProtectedRoute><NetworkOverview /></ProtectedRoute>} />
              <Route path="/analytics" element={<ProtectedRoute><ROIDashboard /></ProtectedRoute>} />
              <Route path="/compliance" element={<ProtectedRoute><CompliancePortal /></ProtectedRoute>} />
              <Route path="/data-import" element={<ProtectedRoute><DataImportPage /></ProtectedRoute>} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppContent />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
