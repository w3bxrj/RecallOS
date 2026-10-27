import React from 'react';
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
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { DecksPage } from './pages/DecksPage';
import { ReviewPage } from './pages/ReviewPage';
import { SettingsPage } from './pages/SettingsPage';

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
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/upload" element={<UploadPage />} />
                  <Route path="/decks" element={<DecksPage />} />
                  <Route path="/review" element={<ReviewPage />} />
                  <Route path="/settings" element={<SettingsPage />} />

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
