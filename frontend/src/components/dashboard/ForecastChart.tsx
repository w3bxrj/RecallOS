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
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-xs flex flex-col justify-center items-center text-center min-h-[380px] space-y-3">
        <AlertCircle className="w-8 h-8 text-rose-600" />
        <h4 className="text-sm font-bold text-slate-800">Failed to load forecast</h4>
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

  // Calculate summary metrics for aria label
  const totalScheduled = forecast.reduce((acc, curr) => acc + curr.due_count, 0);
  const maxDueItem = forecast.reduce(
    (max, curr) => (curr.due_count > max.due_count ? curr : max),
    forecast[0] || { date: '', due_count: 0 }
  );
  const ariaLabel = `Cards due per day (next 30 days): ${forecast.length} days forecasted with ${totalScheduled} total cards scheduled. Peak of ${maxDueItem.due_count} on ${formatIstDate(maxDueItem.date)}.`;

  return (
    <div
      className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-xs flex flex-col justify-between min-h-[380px]"
      aria-label={ariaLabel}
    >
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Cards due per day (next 30 days)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Projected daily review workload based on SM-2 interval scheduling.
            </p>
          </div>
          <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100/60 self-start sm:self-auto">
            {totalScheduled} Total Due
          </span>
        </div>

        {forecast.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[260px] text-center text-slate-400 text-xs">
            <span>No forecast available. Add decks or review cards to schedule dates.</span>
          </div>
        ) : (
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={forecast}
                margin={{ top: 15, right: 15, left: -10, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />

                <XAxis
                  dataKey="date"
                  stroke="#94a3b8"
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
                    fill: '#64748b',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                />

                <YAxis
                  allowDecimals={false}
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  label={{
                    value: 'Cards due',
                    angle: -90,
                    position: 'insideLeft',
                    offset: 15,
                    fill: '#64748b',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                />

                <Tooltip
                  cursor={{ fill: '#f8fafc' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload as ForecastItem;
                      const isFirstBar = forecast[0]?.date === item.date;
                      const dateTitle = isFirstBar
                        ? 'Today (incl. overdue)'
                        : formatIstDate(item.date);

                      return (
                        <div className="bg-slate-900 text-white rounded-xl px-3 py-2 text-xs shadow-lg space-y-1">
                          <p className="font-bold text-slate-100">{dateTitle}</p>
                          <p className="text-indigo-300">
                            Cards Due:{' '}
                            <span className="font-extrabold text-white">
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
                  fill="#6366f1"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={20}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span>Day 1 includes cards currently overdue</span>
        <span>Generated for IST timezone</span>
      </div>
    </div>
  );
};
