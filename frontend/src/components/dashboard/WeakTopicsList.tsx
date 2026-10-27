import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, BookOpen, CheckCircle, RotateCcw } from 'lucide-react';
import type { TopicAccuracyItem } from '../../api/types';

interface WeakTopicsListProps {
  topics: TopicAccuracyItem[];
  error?: string | null;
  onRetry?: () => void;
}

export const WeakTopicsList: React.FC<WeakTopicsListProps> = ({
  topics,
  error,
  onRetry,
}) => {
  if (error) {
    return (
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-xs flex flex-col justify-center items-center text-center min-h-[320px] space-y-3">
        <AlertTriangle className="w-8 h-8 text-rose-600" />
        <h4 className="text-sm font-bold text-slate-800">Failed to load topics</h4>
        <p className="text-xs text-slate-500 max-w-xs">{error}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        )}
      </div>
    );
  }

  const weakTopics = topics.filter((t) => t.is_weak);

  return (
    <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-xs flex flex-col justify-between min-h-[320px]">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Weak Topics
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Accuracy &lt; 60% with $\ge 5$ reviews.
            </p>
          </div>
          <span
            className={`text-xs font-bold px-2.5 py-1 rounded-full ${
              weakTopics.length > 0
                ? 'bg-rose-50 text-rose-700 border border-rose-200/60'
                : 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
            }`}
          >
            {weakTopics.length} {weakTopics.length === 1 ? 'Topic' : 'Topics'}
          </span>
        </div>

        {weakTopics.length === 0 ? (
          <div className="py-8 px-4 text-center rounded-2xl bg-emerald-50/50 border border-emerald-100/80 my-auto">
            <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-emerald-900">
              No weak topics detected!
            </h4>
            <p className="text-xs text-emerald-700 mt-1 max-w-xs mx-auto">
              All reviewed topics are currently performing above the 60% accuracy threshold. Keep up the consistent reviews!
            </p>
          </div>
        ) : (
          <div className="space-y-2.5 max-h-[190px] overflow-y-auto pr-1">
            {weakTopics.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 rounded-2xl border border-rose-100 bg-rose-50/40"
              >
                <div>
                  <h4 className="text-xs font-bold text-slate-900 line-clamp-1">
                    {item.topic}
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {item.reviews_count} reviews in last 30d
                  </p>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <span className="text-xs font-black text-rose-600 bg-white px-2 py-0.5 rounded-md border border-rose-200">
                    {item.accuracy !== null ? `${item.accuracy.toFixed(1)}%` : 'N/A'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-slate-100">
        <Link
          to="/review"
          className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-xs transition-colors"
        >
          <BookOpen className="w-4 h-4" />
          <span>Start Reviewing</span>
        </Link>
      </div>
    </div>
  );
};
