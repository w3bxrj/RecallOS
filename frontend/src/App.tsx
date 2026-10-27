import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LazyMotion, domAnimation } from 'motion/react';
import { appConfig } from './api/config';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ConfigErrorScreen } from './components/layout/ConfigErrorScreen';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';

import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';

// Route-level code splitting for protected pages
const DashboardPage = React.lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const UploadPage = React.lazy(() =>
  import('./pages/UploadPage').then((m) => ({ default: m.UploadPage }))
);
const DecksPage = React.lazy(() =>
  import('./pages/DecksPage').then((m) => ({ default: m.DecksPage }))
);
const ReviewPage = React.lazy(() =>
  import('./pages/ReviewPage').then((m) => ({ default: m.ReviewPage }))
);
const SettingsPage = React.lazy(() =>
  import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);

const RouteLoadingFallback: React.FC = () => (
  <div className="space-y-6 max-w-4xl mx-auto p-4 animate-pulse" aria-label="Loading page">
    <div className="h-8 w-44 bg-surface-muted rounded-xl border border-border-subtle" />
    <div className="h-4 w-72 bg-surface-muted rounded-lg border border-border-subtle" />
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
      <div className="h-28 bg-surface-muted rounded-2xl border border-border-subtle" />
      <div className="h-28 bg-surface-muted rounded-2xl border border-border-subtle" />
      <div className="h-28 bg-surface-muted rounded-2xl border border-border-subtle" />
    </div>
    <div className="h-64 bg-surface-muted rounded-3xl border border-border-subtle" />
  </div>
);

export const App: React.FC = () => {
  // If production environment configuration is invalid, show visible error screen
  if (!appConfig.isValid) {
    return <ConfigErrorScreen message={appConfig.errorMessage} />;
  }

  const enableDuel = import.meta.env.VITE_ENABLE_DUEL === 'true';

  return (
    <ThemeProvider>
      <LazyMotion features={domAnimation}>
        <BrowserRouter>
          <ToastProvider>
            <AuthProvider>
              <Routes>
                {/* Public Auth Routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />

                {/* Protected Routes wrapped in AppLayout */}
                <Route
                  element={
                    <ProtectedRoute>
                      <AppLayout />
                    </ProtectedRoute>
                  }
                >
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route
                    path="/dashboard"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <DashboardPage />
                      </Suspense>
                    }
                  />
                  <Route
                    path="/upload"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <UploadPage />
                      </Suspense>
                    }
                  />
                  <Route
                    path="/decks"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <DecksPage />
                      </Suspense>
                    }
                  />
                  <Route
                    path="/review"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <ReviewPage />
                      </Suspense>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <SettingsPage />
                      </Suspense>
                    }
                  />

                  {/* Quiz Duel route - completely hidden if VITE_ENABLE_DUEL is not true */}
                  {enableDuel && (
                    <Route
                      path="/duel"
                      element={
                        <div className="text-center py-12">
                          <h2 className="text-xl font-bold text-txt-primary">Quiz Duel</h2>
                          <p className="text-txt-muted">Duel engine coming in Phase 7.</p>
                        </div>
                      }
                    />
                  )}
                </Route>

                {/* Fallback route */}
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </AuthProvider>
          </ToastProvider>
        </BrowserRouter>
      </LazyMotion>
    </ThemeProvider>
  );
};

export default App;
