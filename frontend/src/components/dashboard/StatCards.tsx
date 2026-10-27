import React from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Flame, Layers, Calendar, Brain, ArrowRight } from 'lucide-react';
import type { StatsOverviewResponse } from '../../api/types';

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
      : (days_to_exam !== null && days_to_exam < 0);

  const isExamToday =
    exam_date && todayStr
      ? exam_date === todayStr
      : (days_to_exam === 0);

  // Compute Days to Exam label/subtext
  const renderExamDays = () => {
    if (!exam_date) {
      return (
        <div className="flex flex-col">
          <span className="text-base font-bold text-indigo-600">No exam set</span>
          <Link
            to="/settings"
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1 mt-1"
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
          <span className="text-base font-bold text-slate-500">Exam passed</span>
          <span className="text-xs text-slate-400 mt-1">Exam date has passed</span>
        </div>
      );
    }

    if (isExamToday) {
      return (
        <div className="flex flex-col">
          <span className="text-2xl font-black text-rose-600">Today</span>
          <span className="text-xs font-semibold text-rose-500 mt-1">Exam is today!</span>
        </div>
      );
    }

    return (
      <div className="flex flex-col">
        <span className="text-2xl font-black text-slate-900 tracking-tight">
          {days_to_exam} {days_to_exam === 1 ? 'day' : 'days'}
        </span>
        <span className="text-xs text-slate-500 mt-1">Until target exam</span>
      </div>
    );
  };

  // Compute Retention on Exam label/subtext
  const renderRetention = () => {
    if (expected_retention_on_exam !== null && expected_retention_on_exam !== undefined) {
      return (
        <div className="flex flex-col">
          <span className="text-2xl font-black text-emerald-600 tracking-tight">
            {expected_retention_on_exam.toFixed(1)}%
          </span>
          <span className="text-[11px] text-slate-500 leading-snug mt-1">
            Estimated retention on exam day if you stopped revising now
          </span>
        </div>
      );
    }

    // Separate null cases per user requirement
    let messageContent: React.ReactNode;
    if (!exam_date) {
      messageContent = (
        <Link
          to="/settings"
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
        >
          <span>Set your exam date in Settings</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      );
    } else if (isExamPassed) {
      messageContent = <span className="text-xs text-slate-500">Exam date has passed</span>;
    } else {
      messageContent = (
        <Link
          to="/review"
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
        >
          <span>Review some cards first</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      );
    }

    return (
      <div className="flex flex-col">
        <span className="text-base font-bold text-slate-400">N/A</span>
        <div className="mt-1">{messageContent}</div>
        <span className="text-[11px] text-slate-400 leading-tight mt-1.5">
          Estimated retention on exam day if you stopped revising now
        </span>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {/* 1. Due Today Card */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between min-h-[145px]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Due Today
          </span>
          <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <BookOpen className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 tracking-tight">
              {queue_size_today}
            </span>
            <span className="text-xs font-medium text-slate-500">
              in queue
            </span>
          </div>
          {extraDue > 0 && (
            <div className="mt-1">
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200/60">
                +{extraDue} more due beyond today's limit
              </span>
            </div>
          )}
        </div>
        <div className="text-[11px] text-slate-400 font-medium">
          Daily limit: {daily_limit}
        </div>
      </div>

      {/* 2. Streak Days Card */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between min-h-[145px]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Review Streak
          </span>
          <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <Flame className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          <span className="text-3xl font-black text-slate-900 tracking-tight">
            {streak_days}
          </span>
          <span className="text-xs font-medium text-slate-500 ml-1.5">
            {streak_days === 1 ? 'day' : 'days'}
          </span>
        </div>
        <div className="text-[11px] text-slate-400 font-medium">
          {streak_days > 0 ? 'Consecutive review days' : 'Start your streak today!'}
        </div>
      </div>

      {/* 3. Total Cards Card */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between min-h-[145px]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Cards
          </span>
          <div className="w-8 h-8 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center">
            <Layers className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          <span className="text-3xl font-black text-slate-900 tracking-tight">
            {total_cards}
          </span>
          <span className="text-xs font-medium text-slate-500 ml-1.5">
            cards
          </span>
        </div>
        <div className="text-[11px] text-slate-400 font-medium">
          Across all your decks
        </div>
      </div>

      {/* 4. Days to Exam Card */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between min-h-[145px]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Target Exam
          </span>
          <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Calendar className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          {renderExamDays()}
        </div>
        <div className="text-[11px] text-slate-400 font-medium">
          Adaptive prioritization
        </div>
      </div>

      {/* 5. Expected Retention on Exam Card */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between min-h-[145px]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Predicted Recall
          </span>
          <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Brain className="w-4 h-4" />
          </div>
        </div>
        <div className="my-1">
          {renderRetention()}
        </div>
      </div>
    </div>
  );
};
