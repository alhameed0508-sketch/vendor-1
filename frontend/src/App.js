import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import Dashboard from './investigator_dashboard/Dashboard';
import AlertDetail from './alert_detail/AlertDetail';
import ROIDashboard from './roi_dashboard/ROIDashboard';
import LoginPage from './login/LoginPage';
import CompliancePortal from './compliance_portal/CompliancePortal';
import NetworkOverview from './network/NetworkOverview';
import RiskEnginePage from './risk_engine/RiskEnginePage';
import AlertQueue from './alert_queue/AlertQueue';
import DataImportPage from './data_import/DataImportPage';
import RiskOperationsPage from './risk_operations/RiskOperationsPage';
import BenchmarkPage from './benchmark/BenchmarkPage';
import LiveStream from './live_stream/LiveStream';
import ComplaintsPage from './complaints/ComplaintsPage';
import CaseView from './complaints/CaseView';
import ReturnsPage from './returns/ReturnsPage';
import ClaimView from './returns/ClaimView';
import CapturePage from './returns/CapturePage';
import CommandCenter from './shell/CommandCenter';
import ModulesPage from './shell/ModulesPage';
import EntityView from './shell/EntityView';
import ModuleWorkspace from './shell/ModuleWorkspace';
import InvestigationsPage from './shell/InvestigationsPage';
import Sidebar from './components/Sidebar';
import MobileNav from './components/MobileNav';
import GuestBanner from './components/GuestBanner';
import ErrorBoundary from './components/ErrorBoundary';
import { ThemeProvider, useTheme } from './ThemeContext';
import { AuthProvider } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import { EXTRA_PAGES_ENABLED } from './config/features';
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
          fontFamily: 'var(--font-sans)',
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
      <ThemedToaster />

      {!isLoginPage && (
        <Sidebar
          stats={stats}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(prev => !prev)}
        />
      )}
      {!isLoginPage && <MobileNav />}

      <div className="app-content">
        <main className="app-main">
          {!isLoginPage && <GuestBanner />}
          <ErrorBoundary>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/command-center" element={<ProtectedRoute><CommandCenter /></ProtectedRoute>} />
              <Route path="/modules" element={<ProtectedRoute><ModulesPage /></ProtectedRoute>} />
              <Route path="/modules/:moduleId" element={<ProtectedRoute><ModuleWorkspace /></ProtectedRoute>} />
              <Route path="/investigations" element={<ProtectedRoute><InvestigationsPage /></ProtectedRoute>} />
              <Route path="/entities/:entityId" element={<ProtectedRoute><EntityView /></ProtectedRoute>} />
              <Route path="/queue" element={<ProtectedRoute><AlertQueue /></ProtectedRoute>} />
              <Route path="/alert/:alertId" element={<ProtectedRoute><AlertDetail /></ProtectedRoute>} />
              <Route path="/network" element={<ProtectedRoute><NetworkOverview /></ProtectedRoute>} />
              <Route path="/risk-engine" element={<ProtectedRoute><RiskEnginePage /></ProtectedRoute>} />
              <Route path="/benchmarks" element={<ProtectedRoute><BenchmarkPage /></ProtectedRoute>} />
              <Route path="/live" element={<ProtectedRoute><LiveStream /></ProtectedRoute>} />
              {EXTRA_PAGES_ENABLED && (
                <>
                  <Route path="/analytics" element={<ProtectedRoute><ROIDashboard /></ProtectedRoute>} />
                  <Route path="/complaints" element={<ProtectedRoute><ComplaintsPage /></ProtectedRoute>} />
                  <Route path="/complaints/:complaintId" element={<ProtectedRoute><CaseView /></ProtectedRoute>} />
                  <Route path="/returns" element={<ProtectedRoute><ReturnsPage /></ProtectedRoute>} />
                  <Route path="/returns/capture" element={<ProtectedRoute><CapturePage /></ProtectedRoute>} />
                  <Route path="/returns/:claimId" element={<ProtectedRoute><ClaimView /></ProtectedRoute>} />
                  <Route path="/compliance" element={<ProtectedRoute><CompliancePortal /></ProtectedRoute>} />
                  <Route path="/data-import" element={<ProtectedRoute><DataImportPage /></ProtectedRoute>} />
                  <Route path="/risk-operations" element={<ProtectedRoute><RiskOperationsPage /></ProtectedRoute>} />
                </>
              )}
              <Route path="*" element={<Navigate to="/" replace />} />
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
