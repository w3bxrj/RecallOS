import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Brain,
  Lock,
  Mail,
  ArrowRight,
  AlertCircle,
  Info,
  Sparkles,
  Clock,
  BarChart3,
  Sun,
  Moon,
} from 'lucide-react';
import { m, AnimatePresence } from 'motion/react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { ApiClientError } from '../api/types';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isExpired = searchParams.get('expired') === '1';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string; server?: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    if (!email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    setErrors({});

    try {
      await login({ email: email.trim(), password });
      navigate('/dashboard');
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setErrors({ server: err.message });
      } else {
        setErrors({ server: 'An unexpected error occurred. Please try again.' });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-app text-txt-primary">
      {/* Left Brand Panel (Desktop) */}
      <div className="hidden lg:flex flex-col justify-between p-12 xl:p-16 brand-gradient text-white relative overflow-hidden">
        {/* Decorative backdrop shapes */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-white/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl pointer-events-none" />

        {/* Top brand */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center text-white shadow-lg">
            <Brain className="w-6 h-6" />
          </div>
          <span className="font-extrabold text-2xl tracking-tight">RecallOS</span>
        </div>

        {/* Middle Value Props */}
        <div className="relative z-10 space-y-8 my-auto py-8">
          <div className="space-y-3 max-w-md">
            <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight leading-tight">
              Master your coursework in half the time.
            </h1>
            <p className="text-indigo-100 text-sm xl:text-base leading-relaxed">
              Transform lecture notes, PDFs, and slide decks into high-yield flashcards with intelligent spaced repetition.
            </p>
          </div>

          <div className="space-y-4 max-w-lg">
            <div className="flex items-start gap-4 p-4 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/15">
              <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center shrink-0 text-white">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold">Notes to flashcards in seconds</h2>
                <p className="text-xs text-indigo-100 mt-0.5 leading-relaxed">
                  Upload PDFs, text, or slides. Multimodal AI extracts key definitions, equations, and core concepts.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/15">
              <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center shrink-0 text-white">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold">Smart review schedule</h2>
                <p className="text-xs text-indigo-100 mt-0.5 leading-relaxed">
                  FSRS spaced repetition algorithms prompt review right before memory decay sets in.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/15">
              <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center shrink-0 text-white">
                <BarChart3 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold">Know what to revise</h2>
                <p className="text-xs text-indigo-100 mt-0.5 leading-relaxed">
                  Real-time retention scores pinpoint weak topics before exam day.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom footer quote */}
        <div className="relative z-10 text-xs text-indigo-200">
          Designed for focused, distraction-free study sessions.
        </div>
      </div>

      {/* Right Form Panel */}
      <div className="flex flex-col justify-between p-6 sm:p-10 lg:p-12 xl:p-16 min-h-screen">
        {/* Top Bar with Theme Toggle */}
        <div className="flex justify-between items-center w-full">
          {/* Mobile Logo */}
          <div className="flex lg:hidden items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl brand-gradient flex items-center justify-center text-white shadow-sm">
              <Brain className="w-5 h-5" />
            </div>
            <span className="font-extrabold text-xl tracking-tight text-txt-primary">
              Recall<span className="brand-gradient-text">OS</span>
            </span>
          </div>
          <div className="hidden lg:block" />

          {/* Theme Toggle Button */}
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
        </div>

        {/* Form Container */}
        <div className="w-full max-w-md mx-auto my-auto py-8">
          <div className="mb-8">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-txt-primary tracking-tight">
              Sign in to your account
            </h2>
            <p className="mt-2 text-sm text-txt-secondary">
              Don't have an account?{' '}
              <Link to="/register" className="font-semibold text-brand hover:underline">
                Create an account
              </Link>
            </p>
          </div>

          {/* Session Expired Notice */}
          <AnimatePresence>
            {isExpired && (
              <m.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mb-6 p-4 rounded-2xl bg-amber-50 border border-amber-200/80 dark:bg-amber-950/40 dark:border-amber-900/60 flex items-start gap-3 text-amber-900 dark:text-amber-200 text-sm shadow-xs"
              >
                <Info className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Your session has expired. Please sign in again.</span>
              </m.div>
            )}
          </AnimatePresence>

          {/* Server Error Alert */}
          <AnimatePresence>
            {errors.server && (
              <m.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 dark:bg-rose-950/40 dark:border-rose-900/60 flex items-start gap-3 text-rose-900 dark:text-rose-200 text-sm shadow-xs"
              >
                <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                <span>{errors.server}</span>
              </m.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <Input
              id="email"
              name="email"
              type="email"
              label="Email address"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
              leftIcon={<Mail className="w-4 h-4" />}
              placeholder="you@college.edu"
            />

            <Input
              id="password"
              name="password"
              type="password"
              label="Password"
              isPassword
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={errors.password}
              leftIcon={<Lock className="w-4 h-4" />}
              placeholder="••••••••"
            />

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isSubmitting}
              rightIcon={<ArrowRight className="w-4 h-4" />}
              className="w-full mt-2"
            >
              Sign in
            </Button>
          </form>
        </div>

        {/* Bottom space or copyright */}
        <div className="text-center text-xs text-txt-muted py-2">
          RecallOS &copy; {new Date().getFullYear()} &bull; Spaced Repetition Study Engine
        </div>
      </div>
    </div>
  );
};
