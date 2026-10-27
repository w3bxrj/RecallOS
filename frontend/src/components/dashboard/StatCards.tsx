import React from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Flame, Layers, Calendar, Brain, ArrowRight } from 'lucide-react';
import { m } from 'motion/react';
import type { StatsOverviewResponse } from '../../api/types';
import { useCountUp } from '../../hooks/useCountUp';

interface StatCardsProps {
  overview: StatsOverviewResponse;
}

export const StatCards: React.FC<StatCardsProps> = ({ overview }) => {
  const {
    due_today,
    queue_size_today,
    daily_limit,
    total_cards,
    streak_days,
    expected_retention_on_exam,
    exam_date,
    days_to_exam,
  } = overview;

  // Animated numbers
  const animatedQueue = useCountUp(queue_size_today);
  const animatedStreak = useCountUp(streak_days);
  const animatedTotal = useCountUp(total_cards);

  // Extra cards due beyond daily limit
  const extraDue = due_today > queue_size_today ? due_today - queue_size_today : 0;

  // Today's date string in IST from the 7-day review sequence (last item is today)
  const todayStr =
    overview.reviews_last_7_days && overview.reviews_last_7_days.length > 0
      ? overview.reviews_last_7_days[overview.reviews_last_7_days.length - 1].date
      : undefined;

  const isExamPassed =
    exam_date && todayStr
      ? exam_date < todayStr
      : days_to_exam !== null && days_to_exam < 0;

  const isExamToday =
    exam_date && todayStr
      ? exam_date === todayStr
      : days_to_exam === 0;

  // Compute Days to Exam label/subtext
  const renderExamDays = () => {
    if (!exam_date) {
      return (
        <div className="flex flex-col">
          <span className="text-sm font-bold text-brand">No exam set</span>
          <Link
            to="/settings"
            className="text-xs text-brand hover:underline font-semibold inline-flex items-center gap-1 mt-1"
          >
            <span>Set in Settings</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      );
    }

    if (isExamPassed) {
      return (
        <div className="flex flex-col">
          <span className="text-sm font-bold text-txt-muted">Exam passed</span>
          <span className="text-xs text-txt-muted mt-1">Date has passed</span>
        </div>
      );
    }

    if (isExamToday) {
      return (
        <div className="flex flex-col">
          <span className="text-2xl font-black text-rose-600 dark:text-rose-400">Today</span>
          <span className="text-xs font-semibold text-rose-500 mt-1">Exam is today!</span>
        </div>
      );
    }

    return (
      <div className="flex flex-col">
        <span className="text-2xl font-black text-txt-primary tracking-tight tabular-nums">
          {days_to_exam} {days_to_exam === 1 ? 'day' : 'days'}
        </span>
        <span className="text-xs text-txt-muted mt-1">Until target exam</span>
      </div>
    );
  };

  // Compute Retention on Exam label/subtext
  const renderRetention = () => {
    if (expected_retention_on_exam !== null && expected_retention_on_exam !== undefined) {
      return (
        <div className="flex flex-col">
          <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400 tracking-tight tabular-nums">
            {expected_retention_on_exam.toFixed(1)}%
          </span>
          <span className="text-[11px] text-txt-muted leading-snug mt-1">
            Estimated retention on exam day if revision stopped now
          </span>
        </div>
      );
    }

    let messageContent: React.ReactNode;
    if (!exam_date) {
      messageContent = (
        <Link
          to="/settings"
          className="text-xs text-brand hover:underline font-semibold inline-flex items-center gap-1"
        >
          <span>Set date in Settings</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      );
    } else if (isExamPassed) {
      messageContent = <span className="text-xs text-txt-muted">Exam date passed</span>;
    } else {
      messageContent = (
        <Link
          to="/review"
          className="text-xs text-brand hover:underline font-semibold inline-flex items-center gap-1"
        >
          <span>Review cards first</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      );
    }

    return (
      <div className="flex flex-col">
        <span className="text-base font-bold text-txt-muted">N/A</span>
        <div className="mt-1">{messageContent}</div>
        <span className="text-[11px] text-txt-muted leading-tight mt-1.5">
          Estimated retention on exam day if revision stopped now
        </span>
      </div>
    );
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 12 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { duration: 0.25, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] },
    }),
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {/* 1. Due Today Card */}
      <m.div
        custom={0}
        initial="hidden"
        animate="visible"
        variants={cardVariants}
        className="bg-surface rounded-2xl p-5 border border-border-subtle shadow-card hover:shadow-card-hover transition-all flex flex-col justify-between min-h-[145px]"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">
            Due Today
          </span>
          <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-100/60 dark:bg-indigo-950/50 dark:border-indigo-900/50 text-brand flex items-center justify-center">
            <BookOpen className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-txt-primary tracking-tight tabular-nums">
              {animatedQueue}
            </span>
            <span className="text-xs font-medium text-txt-muted">in queue</span>
          </div>
          {extraDue > 0 && (
            <div className="mt-1">
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200/60 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800/60">
                +{extraDue} more due beyond today's limit
              </span>
            </div>
          )}
        </div>
        <div className="text-[11px] text-txt-muted font-medium">
          Daily limit: {daily_limit}
        </div>
      </m.div>

      {/* 2. Streak Days Card */}
      <m.div
        custom={1}
        initial="hidden"
        animate="visible"
        variants={cardVariants}
        className="bg-surface rounded-2xl p-5 border border-border-subtle shadow-card hover:shadow-card-hover transition-all flex flex-col justify-between min-h-[145px]"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">
            Review Streak
          </span>
          <div
            className={`w-8 h-8 rounded-xl flex items-center justify-center transition-transform ${
              streak_days > 0
                ? 'bg-amber-50 border border-amber-200 dark:bg-amber-950/50 dark:border-amber-800/60 text-amber-500 shadow-xs'
                : 'bg-surface-muted text-txt-muted'
            }`}
          >
            <Flame className={`w-4 h-4 ${streak_days > 0 ? 'fill-amber-400 text-amber-500 animate-pulse' : ''}`} />
          </div>
        </div>
        <div className="my-1">
          <span className="text-3xl font-black text-txt-primary tracking-tight tabular-nums">
            {animatedStreak}
          </span>
          <span className="text-xs font-medium text-txt-muted ml-1.5">
            {streak_days === 1 ? 'day' : 'days'}
          </span>
        </div>
        <div className="text-[11px] text-txt-muted font-medium">
          {streak_days > 0 ? 'Consecutive review days' : 'Start your streak today!'}
        </div>
      </m.div>

      {/* 3. Total Cards Card */}
      <m.div
        custom={2}
        initial="hidden"
        animate="visible"
        variants={cardVariants}
        className="bg-surface rounded-2xl p-5 border border-border-subtle shadow-card hover:shadow-card-hover transition-all flex flex-col justify-between min-h-[145px]"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">
            Total Cards
          </span>
          <div className="w-8 h-8 rounded-xl bg-violet-50 border border-violet-100/60 dark:bg-violet-950/50 dark:border-violet-900/50 text-violet-600 dark:text-violet-400 flex items-center justify-center">
            <Layers className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          <span className="text-3xl font-black text-txt-primary tracking-tight tabular-nums">
            {animatedTotal}
          </span>
          <span className="text-xs font-medium text-txt-muted ml-1.5">cards</span>
        </div>
        <div className="text-[11px] text-txt-muted font-medium">Across all your decks</div>
      </m.div>

      {/* 4. Days to Exam Card */}
      <m.div
        custom={3}
        initial="hidden"
        animate="visible"
        variants={cardVariants}
        className="bg-surface rounded-2xl p-5 border border-border-subtle shadow-card hover:shadow-card-hover transition-all flex flex-col justify-between min-h-[145px]"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">
            Target Exam
          </span>
          <div className="w-8 h-8 rounded-xl bg-emerald-50 border border-emerald-100/60 dark:bg-emerald-950/50 dark:border-emerald-900/50 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <Calendar className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">{renderExamDays()}</div>
        <div className="text-[11px] text-txt-muted font-medium">Adaptive prioritization</div>
      </m.div>

      {/* 5. Expected Retention on Exam Card */}
      <m.div
        custom={4}
        initial="hidden"
        animate="visible"
        variants={cardVariants}
        className="bg-surface rounded-2xl p-5 border border-border-subtle shadow-card hover:shadow-card-hover transition-all flex flex-col justify-between min-h-[145px]"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-txt-muted uppercase tracking-wider">
            Predicted Recall
          </span>
          <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-100/60 dark:bg-indigo-950/50 dark:border-indigo-900/50 text-brand flex items-center justify-center">
            <Brain className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">{renderRetention()}</div>
      </m.div>
    </div>
  );
};
