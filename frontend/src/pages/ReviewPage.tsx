import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpen,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Sparkles,
  ArrowRight,
  UploadCloud,
  HelpCircle,
  Eye,
} from 'lucide-react';
import { apiGetReviewQueue, apiSubmitReview } from '../api/reviews';
import { ApiClientError } from '../api/types';
import type { QueueCardItem } from '../api/types';
import { useToast } from '../context/ToastContext';
import { Spinner } from '../components/common/Spinner';
import { Skeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';

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
      <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
        <div className="flex justify-between items-center">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="bg-white rounded-3xl p-8 border border-slate-200 space-y-6">
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
      <div className="max-w-md mx-auto bg-rose-50 border border-rose-200 rounded-3xl p-8 text-center space-y-4">
        <AlertCircle className="w-10 h-10 text-rose-600 mx-auto" />
        <h2 className="text-lg font-bold text-rose-900">Unable to Load Queue</h2>
        <p className="text-sm text-rose-700">{fetchError}</p>
        <button
          onClick={fetchQueue}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-sm shadow-sm transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Retry</span>
        </button>
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
      <div className="max-w-md mx-auto bg-white rounded-3xl border border-slate-200/90 shadow-md p-8 text-center space-y-6 animate-fade-in">
        <div className="w-16 h-16 rounded-3xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            Session Complete!
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Excellent focus! You reviewed <span className="font-bold text-slate-800">{reviewedCount}</span> {reviewedCount === 1 ? 'card' : 'cards'} in this study session.
          </p>
        </div>

        {remainingCount > 0 && (
          <div className="p-4 rounded-2xl bg-indigo-50 border border-indigo-100 text-xs text-indigo-900 font-medium">
            There are {remainingCount} more cards due beyond today's daily limit.
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <Link
            to="/dashboard"
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm shadow-sm transition-colors"
          >
            <span>Dashboard</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/upload"
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition-colors"
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
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      {/* Header Info & Progress */}
      <div className="flex items-center justify-between text-xs sm:text-sm font-semibold text-slate-600">
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
            Card {currentIndex + 1} of {queue.length}
          </span>
          {remainingCount > 0 && (
            <span className="text-slate-400 font-normal">
              (+{remainingCount} beyond limit)
            </span>
          )}
        </div>

        <div className="text-slate-400 text-xs font-mono">
          Reviewed today: {reviewedCount}
        </div>
      </div>

      {/* Main Flashcard Container */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-md p-6 sm:p-10 flex flex-col justify-between min-h-[360px] relative transition-all duration-300">
        <div>
          {/* Card Topic Badge */}
          <div className="flex items-center justify-between mb-6">
            <span className="px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase bg-indigo-50 text-indigo-700 border border-indigo-100">
              {currentCard.topic}
            </span>
            <span className="text-xs text-slate-400 font-medium flex items-center gap-1">
              <HelpCircle className="w-3.5 h-3.5" />
              <span>SM-2 Spaced Card</span>
            </span>
          </div>

          {/* Question Text */}
          <div className="space-y-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Question
            </span>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 leading-snug">
              {currentCard.question}
            </h2>
          </div>

          {/* Revealed Answer (Back face shows ONLY the answer, no distractors) */}
          {isAnswerRevealed && (
            <div className="mt-8 pt-6 border-t border-slate-100 animate-slide-up space-y-2">
              <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider">
                Answer
              </span>
              <p className="text-base sm:text-lg text-slate-800 leading-relaxed font-medium bg-emerald-50/50 p-4 rounded-2xl border border-emerald-100">
                {currentCard.answer}
              </p>
            </div>
          )}
        </div>

        {/* Network Retry Callout */}
        {submitError && (
          <div className="mt-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{submitError}</span>
            </div>
            <span className="font-semibold text-rose-700">Click a rating to retry</span>
          </div>
        )}

        {/* Action Controls */}
        <div className="mt-8 pt-6 border-t border-slate-100">
          {!isAnswerRevealed ? (
            <button
              onClick={handleReveal}
              className="w-full py-3.5 px-6 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm shadow-md shadow-indigo-100 flex items-center justify-center gap-2 transition-all duration-150"
            >
              <Eye className="w-4 h-4" />
              <span>Show Answer</span>
              <span className="ml-2 text-xs font-normal opacity-75">(Space)</span>
            </button>
          ) : (
            <div className="space-y-3">
              <div className="text-center text-xs font-medium text-slate-400">
                How well did you recall this card? (Use keys 1–4)
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {/* 1: Again */}
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => handleRate(1)}
                  className="p-3 rounded-2xl border border-rose-200 bg-rose-50/80 hover:bg-rose-100/90 text-rose-900 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-all disabled:opacity-50"
                >
                  <span className="text-rose-700 font-extrabold">[1] Again</span>
                  <span className="text-[11px] font-normal text-rose-600 mt-0.5">
                    {formatInterval(intervals.again)}
                  </span>
                </button>

                {/* 2: Hard */}
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => handleRate(2)}
                  className="p-3 rounded-2xl border border-amber-200 bg-amber-50/80 hover:bg-amber-100/90 text-amber-900 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-all disabled:opacity-50"
                >
                  <span className="text-amber-700 font-extrabold">[2] Hard</span>
                  <span className="text-[11px] font-normal text-amber-600 mt-0.5">
                    {formatInterval(intervals.hard)}
                  </span>
                </button>

                {/* 3: Good */}
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => handleRate(3)}
                  className="p-3 rounded-2xl border border-blue-200 bg-blue-50/80 hover:bg-blue-100/90 text-blue-900 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-all disabled:opacity-50"
                >
                  <span className="text-blue-700 font-extrabold">[3] Good</span>
                  <span className="text-[11px] font-normal text-blue-600 mt-0.5">
                    {formatInterval(intervals.good)}
                  </span>
                </button>

                {/* 4: Easy */}
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => handleRate(4)}
                  className="p-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 hover:bg-emerald-100/90 text-emerald-900 font-bold text-xs sm:text-sm text-center flex flex-col items-center justify-center transition-all disabled:opacity-50"
                >
                  <span className="text-emerald-700 font-extrabold">[4] Easy</span>
                  <span className="text-[11px] font-normal text-emerald-600 mt-0.5">
                    {formatInterval(intervals.easy)}
                  </span>
                </button>
              </div>

              {isSubmitting && (
                <div className="flex items-center justify-center gap-2 text-xs text-indigo-600 font-medium pt-1">
                  <Spinner size="sm" />
                  <span>Recording rating...</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
