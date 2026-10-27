import React, { useEffect, useState, useCallback, Suspense } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Upload, Layers, Calendar, Sparkles, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiGetStatsOverview, apiGetStatsTopics, apiGetStatsForecast } from '../api/stats';
import type { StatsOverviewResponse, TopicAccuracyItem, ForecastResponse } from '../api/types';
import { formatIstDateFull } from '../utils/dateUtils';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { AnalyticsSkeleton } from '../components/dashboard/AnalyticsSkeleton';

// Lazy-load the heavy Recharts analytics component to keep the initial bundle light
const AnalyticsSection = React.lazy(
  () => import('../components/dashboard/AnalyticsSection')
);

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  // State for all 3 stats endpoints to support independent loading and error states
  const [overview, setOverview] = useState<StatsOverviewResponse | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [topics, setTopics] = useState<TopicAccuracyItem[] | null>(null);
  const [topicsError, setTopicsError] = useState<string | null>(null);

  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);

  const [loading, setLoading] = useState<boolean>(true);

  // Endpoint fetchers with individual error tracking
  const fetchOverview = useCallback(async () => {
    try {
      setOverviewError(null);
      const res = await apiGetStatsOverview();
      setOverview(res);
    } catch (err: any) {
      setOverviewError(err.message || 'Failed to load overview metrics');
    }
  }, []);

  const fetchTopics = useCallback(async () => {
    try {
      setTopicsError(null);
      const res = await apiGetStatsTopics();
      setTopics(res);
    } catch (err: any) {
      setTopicsError(err.message || 'Failed to load topic accuracy');
    }
  }, []);

  const fetchForecast = useCallback(async () => {
    try {
      setForecastError(null);
      const res = await apiGetStatsForecast();
      setForecast(res);
    } catch (err: any) {
      setForecastError(err.message || 'Failed to load forecast data');
    }
  }, []);

  // Fetch immediately on mount using Promise.allSettled so one failing endpoint does not blank the dashboard
  const fetchAll = useCallback(async () => {
    setLoading(true);
    await Promise.allSettled([
      fetchOverview(),
      fetchTopics(),
      fetchForecast(),
    ]);
    setLoading(false);
  }, [fetchOverview, fetchTopics, fetchForecast]);

  // Always refetch on mount so numbers are fresh when returning from review sessions
  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Welcome Hero Banner */}
      <div className="bg-gradient-to-r from-indigo-600 via-indigo-700 to-indigo-800 rounded-3xl p-8 sm:p-10 text-white shadow-xl shadow-indigo-100/50 relative overflow-hidden">
        <div className="absolute right-0 top-0 -mt-10 -mr-10 w-64 h-64 bg-white/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 backdrop-blur-md text-xs font-semibold uppercase tracking-wider mb-4 border border-white/20">
            <Sparkles className="w-3.5 h-3.5 text-indigo-200" />
            <span>Spaced Repetition Engine</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3">
            Welcome back, {user?.display_name || 'Scholar'}!
          </h1>
          <p className="text-indigo-100 text-sm sm:text-base leading-relaxed mb-6">
            RecallOS optimizes your study schedule using the SM-2 algorithm. Ready to keep your memory sharp today?
          </p>

          <div className="flex flex-wrap gap-4">
            <Link
              to="/review"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-indigo-700 hover:bg-indigo-50 font-semibold text-sm shadow-md transition-all duration-150"
            >
              <BookOpen className="w-4 h-4" />
              <span>Start Reviewing</span>
            </Link>
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-500/40 hover:bg-indigo-500/60 border border-white/20 text-white font-semibold text-sm transition-all duration-150 backdrop-blur-sm"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Notes</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Target Exam Date Notice */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-800">
              Exam Mode Status
            </h3>
            <p className="text-sm text-slate-500">
              {user?.exam_date ? (
                <>
                  Target Exam Date:{' '}
                  <span className="font-semibold text-slate-700">
                    {formatIstDateFull(user.exam_date)}
                  </span>{' '}
                  (adaptive priority active)
                </>
              ) : (
                'No exam date set. Set an exam date to prioritize weak topics automatically.'
              )}
            </p>
          </div>
        </div>
        <Link
          to="/settings"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700 shrink-0"
        >
          <span>{user?.exam_date ? 'Edit date' : 'Set exam date'}</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Analytics Section with ErrorBoundary and Suspense */}
      <ErrorBoundary fallbackMessage="A newer version of RecallOS might have been deployed. Please reload the page to load fresh analytics.">
        <Suspense fallback={<AnalyticsSkeleton />}>
          {loading && !overview && !topics && !forecast ? (
            <AnalyticsSkeleton />
          ) : (
            <AnalyticsSection
              overview={overview}
              overviewError={overviewError}
              onRetryOverview={fetchOverview}
              topics={topics}
              topicsError={topicsError}
              onRetryTopics={fetchTopics}
              forecast={forecast}
              forecastError={forecastError}
              onRetryForecast={fetchForecast}
            />
          )}
        </Suspense>
      </ErrorBoundary>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4">
        <Link
          to="/review"
          className="group bg-white p-6 rounded-2xl border border-slate-200/80 hover:border-indigo-300 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
              <BookOpen className="w-5 h-5" />
            </div>
            <h4 className="text-base font-semibold text-slate-900 mb-1">Daily Review</h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              Complete your daily queue of due flashcards with scientifically timed intervals.
            </p>
          </div>
          <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-emerald-600 group-hover:gap-2 transition-all">
            <span>Review cards</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </Link>

        <Link
          to="/upload"
          className="group bg-white p-6 rounded-2xl border border-slate-200/80 hover:border-indigo-300 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
              <Upload className="w-5 h-5" />
            </div>
            <h4 className="text-base font-semibold text-slate-900 mb-1">Upload Notes</h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              Drag and drop PDF or TXT notes to generate clean flashcards via AI in real time.
            </p>
          </div>
          <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-indigo-600 group-hover:gap-2 transition-all">
            <span>Upload new</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </Link>

        <Link
          to="/decks"
          className="group bg-white p-6 rounded-2xl border border-slate-200/80 hover:border-indigo-300 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
              <Layers className="w-5 h-5" />
            </div>
            <h4 className="text-base font-semibold text-slate-900 mb-1">Manage Decks</h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              Browse created decks, inspect individual questions and answers, or remove old sets.
            </p>
          </div>
          <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-violet-600 group-hover:gap-2 transition-all">
            <span>View decks</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </Link>
      </div>
    </div>
  );
};
