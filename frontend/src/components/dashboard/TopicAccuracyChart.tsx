import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';
import { AlertCircle, RotateCcw } from 'lucide-react';
import type { TopicAccuracyItem } from '../../api/types';

interface TopicAccuracyChartProps {
  topics: TopicAccuracyItem[];
  error?: string | null;
  onRetry?: () => void;
}

export const TopicAccuracyChart: React.FC<TopicAccuracyChartProps> = ({
  topics,
  error,
  onRetry,
}) => {
  if (error) {
    return (
      <div className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card flex flex-col justify-center items-center text-center min-h-[380px] space-y-3">
        <AlertCircle className="w-8 h-8 text-rose-600 dark:text-rose-400" />
        <h4 className="text-sm font-bold text-txt-primary">Failed to load topic accuracy</h4>
        <p className="text-xs text-txt-muted max-w-xs">{error}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        )}
      </div>
    );
  }

  // Filter topics: topics with non-null accuracy go to chart, null topics to small list
  const reviewedTopics = topics.filter((t) => t.accuracy !== null && t.accuracy !== undefined);
  const unreviewedTopics = topics.filter((t) => t.accuracy === null || t.accuracy === undefined);

  // Compute aria label summary
  const weakCount = reviewedTopics.filter((t) => t.is_weak).length;
  const ariaLabel = `Topic accuracy: ${reviewedTopics.length} topics reviewed, ${weakCount} below 60 percent threshold.`;

  return (
    <div
      className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card flex flex-col justify-between min-h-[380px]"
      aria-label={ariaLabel}
    >
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-bold text-txt-primary tracking-tight">
              Topic Accuracy (Last 30 Days)
            </h3>
            <p className="text-xs text-txt-muted mt-0.5">
              Share of ratings ≥ 3 per topic. Topics below 60% are prioritized for revision.
            </p>
          </div>

          {/* Accessible Legend explaining colours, patterns and threshold line */}
          <div className="flex flex-wrap items-center gap-3 text-[11px] font-medium text-txt-secondary shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-brand inline-block" />
              <span>≥ 60% (Proficient)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="w-3 h-3 rounded-sm border border-rose-500 inline-block"
                style={{
                  background:
                    'repeating-linear-gradient(45deg, #f43f5e, #f43f5e 2px, #ffe4e6 2px, #ffe4e6 5px)',
                }}
              />
              <span>&lt; 60% (Weak / Striped)</span>
            </div>
            <div className="flex items-center gap-1.5 text-rose-500 font-semibold">
              <span className="w-4 h-0.5 border-t-2 border-dashed border-rose-500 inline-block" />
              <span>60% Target</span>
            </div>
          </div>
        </div>

        {/* Chart Container */}
        {reviewedTopics.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[260px] text-center text-txt-muted text-xs">
            <span>No topic accuracy data available yet. Review some flashcards to see analytics.</span>
          </div>
        ) : (
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={reviewedTopics}
                margin={{ top: 15, right: 15, left: -10, bottom: 25 }}
              >
                <defs>
                  {/* Striped diagonal pattern for weak topics (accessibility: not color alone) */}
                  <pattern
                    id="weak-topic-pattern"
                    width="6"
                    height="6"
                    patternUnits="userSpaceOnUse"
                    patternTransform="rotate(45)"
                  >
                    <rect width="3" height="6" fill="#f43f5e" />
                    <rect x="3" width="3" height="6" fill="#fda4af" />
                  </pattern>
                </defs>

                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-subtle)" />

                <XAxis
                  dataKey="topic"
                  stroke="var(--text-muted)"
                  fontSize={11}
                  tickLine={false}
                  interval={0}
                  tickFormatter={(val: string) =>
                    val.length > 9 ? `${val.slice(0, 8)}…` : val
                  }
                  label={{
                    value: 'Topic',
                    position: 'insideBottom',
                    offset: -16,
                    fill: 'var(--text-muted)',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                />

                <YAxis
                  domain={[0, 100]}
                  stroke="var(--text-muted)"
                  fontSize={11}
                  tickLine={false}
                  label={{
                    value: 'Accuracy (%)',
                    angle: -90,
                    position: 'insideLeft',
                    offset: 15,
                    fill: 'var(--text-muted)',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                />

                <Tooltip
                  cursor={{ fill: 'var(--bg-surface-muted)' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload as TopicAccuracyItem;
                      return (
                        <div className="bg-surface-elevated text-txt-primary border border-border-subtle rounded-xl px-3.5 py-2.5 text-xs shadow-elevated space-y-1">
                          <p className="font-bold text-txt-primary">{item.topic}</p>
                          <p className="text-txt-secondary">
                            Accuracy:{' '}
                            <span className="font-bold text-txt-primary">
                              {item.accuracy !== null ? `${item.accuracy.toFixed(1)}%` : 'N/A'}
                            </span>
                          </p>
                          <p className="text-txt-muted">Reviews: {item.reviews_count}</p>
                          {item.is_weak && (
                            <p className="text-rose-500 font-semibold pt-0.5">
                              ⚠ Priority Weak Topic (&lt;60%)
                            </p>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />

                {/* 60% Target Reference Line with custom styled label */}
                <ReferenceLine
                  y={60}
                  stroke="var(--color-danger)"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  label={{
                    value: '60% Target',
                    position: 'right',
                    fill: '#f43f5e',
                    fontSize: 10,
                    fontWeight: 700,
                  }}
                />

                <Bar dataKey="accuracy" radius={[6, 6, 0, 0]} maxBarSize={45}>
                  {reviewedTopics.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.is_weak ? 'url(#weak-topic-pattern)' : 'var(--brand-primary)'}
                      stroke={entry.is_weak ? '#e11d48' : 'var(--brand-primary-hover)'}
                      strokeWidth={1}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Small list for unreviewed topics with null accuracy */}
      {unreviewedTopics.length > 0 && (
        <div className="pt-3 border-t border-border-subtle flex flex-wrap items-center gap-1.5 text-xs text-txt-muted">
          <span className="font-semibold text-txt-secondary">No reviews yet:</span>
          {unreviewedTopics.map((item, idx) => (
            <span
              key={idx}
              className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-muted text-txt-secondary border border-border-subtle text-[11px]"
            >
              {item.topic}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
