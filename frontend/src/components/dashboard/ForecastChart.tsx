import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { AlertCircle, RotateCcw } from 'lucide-react';
import type { ForecastItem } from '../../api/types';
import { formatIstDate } from '../../utils/dateUtils';

interface ForecastChartProps {
  forecast: ForecastItem[];
  error?: string | null;
  onRetry?: () => void;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  forecast,
  error,
  onRetry,
}) => {
  if (error) {
    return (
      <div className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card flex flex-col justify-center items-center text-center min-h-[380px] space-y-3">
        <AlertCircle className="w-8 h-8 text-rose-600 dark:text-rose-400" />
        <h4 className="text-sm font-bold text-txt-primary">Failed to load forecast</h4>
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

  // Calculate summary metrics for aria label
  const totalScheduled = forecast.reduce((acc, curr) => acc + curr.due_count, 0);
  const maxDueItem = forecast.reduce(
    (max, curr) => (curr.due_count > max.due_count ? curr : max),
    forecast[0] || { date: '', due_count: 0 }
  );
  const ariaLabel = `Cards due per day (next 30 days): ${forecast.length} days forecasted with ${totalScheduled} total cards scheduled. Peak of ${maxDueItem.due_count} on ${formatIstDate(maxDueItem.date)}.`;

  return (
    <div
      className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card flex flex-col justify-between min-h-[380px]"
      aria-label={ariaLabel}
    >
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
          <div>
            <h3 className="text-base font-bold text-txt-primary tracking-tight">
              Cards due per day (next 30 days)
            </h3>
            <p className="text-xs text-txt-muted mt-0.5">
              Projected daily review workload based on SM-2 interval scheduling.
            </p>
          </div>
          <span className="text-xs font-semibold text-brand bg-brand/10 dark:bg-brand/20 px-2.5 py-1 rounded-lg border border-brand/20 self-start sm:self-auto tabular-nums">
            {totalScheduled} Total Due
          </span>
        </div>

        {forecast.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[260px] text-center text-txt-muted text-xs">
            <span>No forecast available. Add decks or review cards to schedule dates.</span>
          </div>
        ) : (
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={forecast}
                margin={{ top: 15, right: 15, left: -10, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-subtle)" />

                <XAxis
                  dataKey="date"
                  stroke="var(--text-muted)"
                  fontSize={10}
                  tickLine={false}
                  interval={4} // Step interval so 30 labels do not overlap on mobile
                  tickFormatter={(val: string, idx: number) =>
                    idx === 0 ? 'Today' : formatIstDate(val)
                  }
                  label={{
                    value: 'Date',
                    position: 'insideBottom',
                    offset: -16,
                    fill: 'var(--text-muted)',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                />

                <YAxis
                  allowDecimals={false}
                  stroke="var(--text-muted)"
                  fontSize={11}
                  tickLine={false}
                  label={{
                    value: 'Cards Due',
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
                      const item = payload[0].payload as ForecastItem;
                      return (
                        <div className="bg-surface-elevated text-txt-primary border border-border-subtle rounded-xl px-3.5 py-2.5 text-xs shadow-elevated space-y-1">
                          <p className="font-bold text-txt-primary">{formatIstDate(item.date)}</p>
                          <p className="text-txt-secondary">
                            Cards Due:{' '}
                            <span className="font-bold text-brand tabular-nums">
                              {item.due_count}
                            </span>
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />

                <Bar
                  dataKey="due_count"
                  fill="var(--brand-primary)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-border-subtle text-[11px] text-txt-muted flex items-center justify-between">
        <span>Horizon: 30 days ahead</span>
        <span className="font-medium text-txt-secondary">
          Peak:{' '}
          <span className="text-txt-primary font-bold tabular-nums">{maxDueItem.due_count}</span> on{' '}
          {maxDueItem.date ? formatIstDate(maxDueItem.date) : 'N/A'}
        </span>
      </div>
    </div>
  );
};
