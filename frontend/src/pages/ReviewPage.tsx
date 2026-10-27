import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpen,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  ArrowRight,
  UploadCloud,
  HelpCircle,
  Eye,
} from 'lucide-react';
import { m, AnimatePresence } from 'motion/react';
import { apiGetReviewQueue, apiSubmitReview } from '../api/reviews';
import { ApiClientError } from '../api/types';
import type { QueueCardItem } from '../api/types';
import { useToast } from '../context/ToastContext';
import { Spinner } from '../components/common/Spinner';
import { Skeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { Button } from '../components/ui/Button';

function formatInterval(days: number): string {
  if (days <= 0) return '< 1 day';
  if (days === 1) return '1 day';
  return `${days} days`;
}

export const ReviewPage: React.FC = () => {
  const toast = useToast();

  const [queue, setQueue] = useState<QueueCardItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [totalDue, setTotalDue] = useState(0);
  const [remainingCount, setRemainingCount] = useState(0);

  const [isLoading, setIsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Card interaction state
  const [isAnswerRevealed, setIsAnswerRevealed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Idempotency: per-card request_id generated with crypto.randomUUID() and reused on retry
  const [currentRequestId, setCurrentRequestId] = useState<string>(() =>
    typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `req-${Date.now()}`
  );

  // Counter of cards completed during this session
  const [reviewedCount, setReviewedCount] = useState(0);
  const initialQueueLengthRef = useRef(0);

  const fetchQueue = useCallback(async () => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const data = await apiGetReviewQueue();
      setQueue(data.cards);
      setTotalDue(data.total_due);
      setRemainingCount(data.remaining_count);
      setCurrentIndex(0);
      setIsAnswerRevealed(false);
      initialQueueLengthRef.current = data.cards.length;
      setCurrentRequestId(
        typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `req-${Date.now()}`
      );
    } catch {
      setFetchError('Failed to load review queue. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const currentCard: QueueCardItem | undefined = queue[currentIndex];

  const handleReveal = useCallback(() => {
    setIsAnswerRevealed(true);
  }, []);

  const handleRate = useCallback(
    async (rating: 1 | 2 | 3 | 4) => {
      if (!currentCard || isSubmitting || !isAnswerRevealed) return;

      setIsSubmitting(true);
      setSubmitError(null);

      try {
        await apiSubmitReview({
          card_id: currentCard.card_id,
          rating,
          request_id: currentRequestId,
        });

        // Success: advance to next card from locally held queue (do not refetch queue after every card)
        setReviewedCount((prev) => prev + 1);
        setIsAnswerRevealed(false);
        setSubmitError(null);
        setCurrentIndex((prev) => prev + 1);

        // Generate brand new request_id for the next card
        setCurrentRequestId(
          typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `req-${Date.now()}`
        );
      } catch (err: unknown) {
        // If rating fails, keep the same card and the same request_id and show Retry
        if (err instanceof ApiClientError) {
          setSubmitError(err.message);
        } else {
          setSubmitError('Failed to submit rating. Please retry.');
        }
        toast.error('Network error during review submission. You can retry safely.');
      } finally {
        setIsSubmitting(false);
      }
    },
    [currentCard, currentRequestId, isAnswerRevealed, isSubmitting, toast]
  );

  // Keyboard Shortcuts:
  // Space: reveal answer
  // 1-4: submit rating (Again, Hard, Good, Easy)
  // Ignored while typing in inputs, while submitting, or before answer is revealed
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }

      if (isSubmitting) return;

      if (e.code === 'Space' && !isAnswerRevealed) {
        e.preventDefault();
        handleReveal();
        return;
      }

      if (isAnswerRevealed) {
        if (e.key === '1') {
          e.preventDefault();
          handleRate(1);
        } else if (e.key === '2') {
          e.preventDefault();
          handleRate(2);
        } else if (e.key === '3') {
          e.preventDefault();
          handleRate(3);
        } else if (e.key === '4') {
          e.preventDefault();
          handleRate(4);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleRate, handleReveal, isAnswerRevealed, isSubmitting]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6 animate-fade-in pb-12">
        <div className="flex justify-between items-center">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="bg-surface rounded-3xl p-8 border border-border-subtle shadow-card space-y-6">
          <Skeleton className="h-5 w-24 rounded-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-12 w-full rounded-2xl" />
        </div>
      </div>
    );
  }

  // Fetch Error
  if (fetchError) {
    return (
      <div className="max-w-md mx-auto bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 rounded-3xl p-8 text-center space-y-4 shadow-card">
        <AlertCircle className="w-10 h-10 text-rose-600 dark:text-rose-400 mx-auto" />
        <h2 className="text-lg font-bold text-rose-900 dark:text-rose-200">Unable to Load Queue</h2>
        <p className="text-sm text-rose-700 dark:text-rose-300">{fetchError}</p>
        <Button
          type="button"
          variant="danger"
          onClick={fetchQueue}
          leftIcon={<RotateCcw className="w-4 h-4" />}
        >
          Retry
        </Button>
      </div>
    );
  }

  // Empty State: nothing due today
  if (totalDue === 0 && reviewedCount === 0) {
    return (
      <EmptyState
        icon={BookOpen}
        title="Nothing due today"
        description="You are completely caught up! No cards are due for review right now. Upload more study materials to keep expanding your knowledge."
        actionText="Upload Notes"
        actionHref="/upload"
      />
    );
  }

  // Final State: Session Complete screen
  const isSessionComplete = currentIndex >= queue.length;

  if (isSessionComplete) {
    return (
      <div className="max-w-md mx-auto bg-surface rounded-3xl border border-border-subtle shadow-card p-8 text-center space-y-6 animate-fade-in pb-10">
        <div className="w-16 h-16 rounded-3xl bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto shadow-xs">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <div>
          <h2 className="text-2xl font-extrabold text-txt-primary tracking-tight">
            Session Complete!
          </h2>
          <p className="text-sm text-txt-secondary mt-1">
            Excellent focus! You reviewed{' '}
            <span className="font-bold text-txt-primary tabular-nums">{reviewedCount}</span>{' '}
            {reviewedCount === 1 ? 'card' : 'cards'} in this study session.
          </p>
        </div>

        {remainingCount > 0 && (
          <div className="p-4 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100/60 dark:border-indigo-900/60 text-xs text-brand font-medium">
            There are {remainingCount} more cards due beyond today's daily limit.
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <Link
            to="/dashboard"
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-brand hover:bg-brand-hover text-white font-semibold text-sm shadow-sm transition-colors"
          >
            <span>Dashboard</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/upload"
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-surface-elevated hover:bg-surface-muted text-txt-primary border border-border-subtle font-semibold text-sm transition-colors"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Notes</span>
          </Link>
        </div>
      </div>
    );
  }

  if (!currentCard) return null;

  const intervals = currentCard.predicted_intervals;

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Header Info & Progress */}
      <div className="flex items-center justify-between text-xs sm:text-sm font-semibold text-txt-secondary">
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950/50 text-brand border border-indigo-100/60 dark:border-indigo-900/60 tabular-nums">
            Card {currentIndex + 1} of {queue.length}
          </span>
          {remainingCount > 0 && (
            <span className="text-txt-muted font-normal text-xs">
              (+{remainingCount} beyond limit)
            </span>
          )}
        </div>

        <div className="text-txt-muted text-xs font-mono tabular-nums">
          Reviewed today: {reviewedCount}
        </div>
      </div>

      {/* Main Flashcard Container with 3D perspective feel */}
      <div className="perspective-1000">
        <m.div
          key={currentCard.card_id}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.2 }}
          className="bg-surface rounded-3xl border border-border-subtle shadow-card p-6 sm:p-10 flex flex-col justify-between min-h-[360px] relative transition-shadow duration-300"
        >
          <div>
            {/* Card Topic Badge */}
            <div className="flex items-center justify-between mb-6">
              <span className="px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase bg-indigo-50 dark:bg-indigo-950/50 text-brand border border-indigo-100/60 dark:border-indigo-900/60">
                {currentCard.topic}
              </span>
              <span className="text-xs text-txt-muted font-medium flex items-center gap-1">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>SM-2 Spaced Card</span>
              </span>
            </div>

            {/* Question Text */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">
                Question
              </span>
              <h2 className="text-lg sm:text-xl font-bold text-txt-primary leading-snug">
                {currentCard.question}
              </h2>
            </div>

            {/* Revealed Answer with smooth entrance */}
            <AnimatePresence>
              {isAnswerRevealed && (
                <m.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  className="mt-8 pt-6 border-t border-border-subtle space-y-2"
                >
                  <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                    Answer
                  </span>
                  <p className="text-base sm:text-lg text-txt-primary leading-relaxed font-medium bg-emerald-50/50 dark:bg-emerald-950/30 p-4 rounded-2xl border border-emerald-100 dark:border-emerald-900/50">
                    {currentCard.answer}
                  </p>
                </m.div>
              )}
            </AnimatePresence>
          </div>

          {/* Network Retry Callout */}
          {submitError && (
            <div className="mt-6 p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-900 dark:text-rose-200 text-xs flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                <span>{submitError}</span>
              </div>
              <span className="font-semibold text-rose-700 dark:text-rose-300">Click rating to retry</span>
            </div>
          )}

          {/* Action Controls */}
          <div className="mt-8 pt-6 border-t border-border-subtle">
            {!isAnswerRevealed ? (
              <Button
                type="button"
                variant="primary"
                size="lg"
                onClick={handleReveal}
                leftIcon={<Eye className="w-4 h-4" />}
                className="w-full"
              >
                <span>Show Answer</span>
                <span className="ml-2 text-xs font-normal opacity-80">(Space)</span>
              </Button>
            ) : (
              <div className="space-y-3">
                <div className="text-center text-xs font-medium text-txt-muted">
                  How well did you recall this card? (Use keys 1–4)
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {/* 1: Again */}
                  <m.button
                    type="button"
                    disabled={isSubmitting}
                    whileTap={isSubmitting ? undefined : { scale: 0.97 }}
                    onClick={() => handleRate(1)}
                    className="p-3 rounded-2xl border border-rose-200/80 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/40 hover:bg-rose-100/90 dark:hover:bg-rose-950/60 text-rose-900 dark:text-rose-200 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
                  >
                    <span className="text-rose-700 dark:text-rose-300 font-extrabold">[1] Again</span>
                    <span className="text-[11px] font-normal text-rose-600 dark:text-rose-400 mt-0.5 tabular-nums">
                      {formatInterval(intervals.again)}
                    </span>
                  </m.button>

                  {/* 2: Hard */}
                  <m.button
                    type="button"
                    disabled={isSubmitting}
                    whileTap={isSubmitting ? undefined : { scale: 0.97 }}
                    onClick={() => handleRate(2)}
                    className="p-3 rounded-2xl border border-amber-200/80 dark:border-amber-900/60 bg-amber-50/80 dark:bg-amber-950/40 hover:bg-amber-100/90 dark:hover:bg-amber-950/60 text-amber-900 dark:text-amber-200 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
                  >
                    <span className="text-amber-700 dark:text-amber-300 font-extrabold">[2] Hard</span>
                    <span className="text-[11px] font-normal text-amber-600 dark:text-amber-400 mt-0.5 tabular-nums">
                      {formatInterval(intervals.hard)}
                    </span>
                  </m.button>

                  {/* 3: Good */}
                  <m.button
                    type="button"
                    disabled={isSubmitting}
                    whileTap={isSubmitting ? undefined : { scale: 0.97 }}
                    onClick={() => handleRate(3)}
                    className="p-3 rounded-2xl border border-indigo-200/80 dark:border-indigo-900/60 bg-indigo-50/80 dark:bg-indigo-950/40 hover:bg-indigo-100/90 dark:hover:bg-indigo-950/60 text-indigo-900 dark:text-indigo-200 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
                  >
                    <span className="text-brand font-extrabold">[3] Good</span>
                    <span className="text-[11px] font-normal text-brand mt-0.5 tabular-nums">
                      {formatInterval(intervals.good)}
                    </span>
                  </m.button>

                  {/* 4: Easy */}
                  <m.button
                    type="button"
                    disabled={isSubmitting}
                    whileTap={isSubmitting ? undefined : { scale: 0.97 }}
                    onClick={() => handleRate(4)}
                    className="p-3 rounded-2xl border border-emerald-200/80 dark:border-emerald-900/60 bg-emerald-50/80 dark:bg-emerald-950/40 hover:bg-emerald-100/90 dark:hover:bg-emerald-950/60 text-emerald-900 dark:text-emerald-200 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
                  >
                    <span className="text-emerald-700 dark:text-emerald-300 font-extrabold">[4] Easy</span>
                    <span className="text-[11px] font-normal text-emerald-600 dark:text-emerald-400 mt-0.5 tabular-nums">
                      {formatInterval(intervals.easy)}
                    </span>
                  </m.button>
                </div>
              </div>
            )}
          </div>
        </m.div>
      </div>
    </div>
  );
};
