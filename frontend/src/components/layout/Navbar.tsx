import React, { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  Brain,
  Upload,
  Layers,
  BookOpen,
  Settings,
  Swords,
  LogOut,
  Menu,
  X,
  LayoutDashboard,
  Sun,
  Moon,
} from 'lucide-react';
import { m, AnimatePresence } from 'motion/react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const enableDuel = import.meta.env.VITE_ENABLE_DUEL === 'true';

  const navItems = [
    { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
    { label: 'Upload', to: '/upload', icon: Upload },
    { label: 'Decks', to: '/decks', icon: Layers },
    { label: 'Review', to: '/review', icon: BookOpen },
    { label: 'Settings', to: '/settings', icon: Settings },
    ...(enableDuel ? [{ label: 'Duel', to: '/duel', icon: Swords }] : []),
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-surface/85 border-b border-border-subtle transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo & Navigation */}
          <div className="flex items-center gap-8">
            <NavLink
              to="/dashboard"
              className="flex items-center gap-2.5 font-extrabold text-xl tracking-tight select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded-xl"
            >
              <div className="w-9 h-9 rounded-xl brand-gradient flex items-center justify-center text-white shadow-sm shadow-indigo-500/25">
                <Brain className="w-5 h-5" />
              </div>
              <span className="text-txt-primary">
                Recall<span className="brand-gradient-text">OS</span>
              </span>
            </NavLink>

            {/* Desktop Navigation Links with animated active pill */}
            <nav className="hidden md:flex items-center space-x-1" aria-label="Main Navigation">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname.startsWith(item.to);

                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={`relative flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                      isActive
                        ? 'text-brand'
                        : 'text-txt-secondary hover:text-txt-primary hover:bg-surface-muted/60'
                    }`}
                  >
                    {isActive && (
                      <m.div
                        layoutId="nav-active-pill"
                        className="absolute inset-0 rounded-xl bg-brand/10 dark:bg-brand/20 -z-10"
                        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                      />
                    )}
                    <Icon className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>
          </div>

          {/* Right Action Items (Desktop) */}
          <div className="hidden md:flex items-center gap-3">
            {/* Theme Toggle Button */}
            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-xl text-txt-secondary hover:text-txt-primary hover:bg-surface-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand cursor-pointer"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              <AnimatePresence mode="wait" initial={false}>
                <m.div
                  key={theme}
                  initial={{ rotate: -90, opacity: 0, scale: 0.8 }}
                  animate={{ rotate: 0, opacity: 1, scale: 1 }}
                  exit={{ rotate: 90, opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.18 }}
                >
                  {theme === 'dark' ? (
                    <Sun className="w-4 h-4 text-amber-400" />
                  ) : (
                    <Moon className="w-4 h-4 text-slate-700" />
                  )}
                </m.div>
              </AnimatePresence>
            </button>

            {/* User display badge */}
            {user && (
              <span className="text-xs font-semibold text-txt-secondary bg-surface-muted px-3 py-1.5 rounded-lg border border-border-subtle">
                {user.display_name}
              </span>
            )}

            {/* Logout button */}
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-txt-secondary hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 cursor-pointer"
              title="Log out"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Logout</span>
            </button>
          </div>

          {/* Mobile Right Bar */}
          <div className="flex md:hidden items-center gap-2">
            {/* Mobile Theme Toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-xl text-txt-secondary hover:text-txt-primary hover:bg-surface-muted transition-colors cursor-pointer"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5 text-amber-400" />
              ) : (
                <Moon className="w-5 h-5 text-slate-700" />
              )}
            </button>

            {/* Mobile menu trigger */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl text-txt-secondary hover:text-txt-primary hover:bg-surface-muted focus:outline-none cursor-pointer"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <m.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden border-t border-border-subtle bg-surface px-4 pt-3 pb-5 space-y-1 shadow-elevated overflow-hidden"
          >
            {user && (
              <div className="px-3 py-2 mb-2 text-xs font-semibold text-txt-muted uppercase tracking-wider border-b border-border-subtle">
                Signed in as <span className="text-txt-primary font-bold">{user.display_name}</span>
              </div>
            )}
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname.startsWith(item.to);

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                    isActive
                      ? 'bg-brand/10 text-brand dark:bg-brand/20'
                      : 'text-txt-secondary hover:text-txt-primary hover:bg-surface-muted'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
            <div className="pt-3 mt-2 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => {
                  setMobileMenuOpen(false);
                  handleLogout();
                }}
                className="w-full flex items-center gap-3 px-3.5 py-2.5 text-sm font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl transition-colors cursor-pointer"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </header>
  );
};
