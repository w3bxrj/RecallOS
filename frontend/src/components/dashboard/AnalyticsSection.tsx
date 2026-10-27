import React from 'react';
import { EmptyState } from '../common/EmptyState';
import { Layers, BookOpen } from 'lucide-react';
import { StatCards } from './StatCards';
import { TopicAccuracyChart } from './TopicAccuracyChart';
import { ForecastChart } from './ForecastChart';
import { RecentReviewsChart } from './RecentReviewsChart';
import { WeakTopicsList } from './WeakTopicsList';
import type {
  StatsOverviewResponse,
  TopicAccuracyItem,
  ForecastResponse,
} from '../../api/types';

export interface AnalyticsSectionProps {
  overview: StatsOverviewResponse | null;
  overviewError: string | null;
  onRetryOverview: () => void;

  topics: TopicAccuracyItem[] | null;
  topicsError: string | null;
  onRetryTopics: () => void;

  forecast: ForecastResponse | null;
  forecastError: string | null;
  onRetryForecast: () => void;
}

export const AnalyticsSection: React.FC<AnalyticsSectionProps> = ({
  overview,
  overviewError,
  onRetryOverview,
  topics,
  topicsError,
  onRetryTopics,
  forecast,
  forecastError,
  onRetryForecast,
}) => {
  // Check empty state situations
  const isNoCards = overview && overview.total_cards === 0;

  // Check if cards exist but zero reviews have occurred yet
  const hasNoReviews =
    overview &&
    overview.total_cards > 0 &&
    overview.streak_days === 0 &&
    overview.reviews_last_7_days.every((r) => r.count === 0);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* 1. Five Stat Cards (Overview) */}
      {overview && <StatCards overview={overview} />}

      {overviewError && (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 text-center text-xs text-rose-800 flex items-center justify-between">
          <span>Failed to load overview metrics: {overviewError}</span>
          <button
            onClick={onRetryOverview}
            className="font-bold underline hover:text-rose-950 ml-2"
          >
            Retry
          </button>
        </div>
      )}

      {/* If no cards created yet, show upload CTA */}
      {isNoCards ? (
        <EmptyState
          icon={Layers}
          title="No flashcards found"
          description="Upload notes to get started with automated spaced repetition flashcards and view detailed learning analytics."
          actionText="Upload notes to get started"
          actionHref="/upload"
        />
      ) : hasNoReviews ? (
        /* If cards exist but 0 reviews yet, show friendly analytics prompt */
        <EmptyState
          icon={BookOpen}
          title="No review analytics yet"
          description="You have created flashcards! Complete your first review session to unlock learning retention predictions, topic accuracy benchmarks, and forecast charts."
          actionText="Review some cards to see your analytics"
          actionHref="/review"
        />
      ) : (
        <>
          {/* 2. Topic Accuracy and Forecast Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TopicAccuracyChart
              topics={topics || []}
              error={topicsError}
              onRetry={onRetryTopics}
            />

            <ForecastChart
              forecast={forecast?.forecast || []}
              error={forecastError}
              onRetry={onRetryForecast}
            />
          </div>

          {/* 3. Recent 7-Day Reviews and Weak Topics Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              {overview?.reviews_last_7_days ? (
                <RecentReviewsChart data={overview.reviews_last_7_days} />
              ) : (
                <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-xs h-[320px] flex items-center justify-center text-xs text-slate-400">
                  Reviews history loading...
                </div>
              )}
            </div>

            <div>
              <WeakTopicsList
                topics={topics || []}
                error={topicsError}
                onRetry={onRetryTopics}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default AnalyticsSection;
