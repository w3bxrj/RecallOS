import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts';
import type { DailyReviewCount } from '../../api/types';
import { formatIstDate } from '../../utils/dateUtils';

interface RecentReviewsChartProps {
  data: DailyReviewCount[];
}

export const RecentReviewsChart: React.FC<RecentReviewsChartProps> = ({ data }) => {
  const totalReviews = data.reduce((acc, curr) => acc + curr.count, 0);

  // The last entry (index 6) in the 7-day array is today IST
  const todayIdx = data.length > 0 ? data.length - 1 : -1;
  const todayDate = todayIdx >= 0 ? data[todayIdx].date : '';

  const ariaLabel = `Reviews in the last 7 days: ${totalReviews} total reviews completed, with ${
    todayIdx >= 0 ? data[todayIdx].count : 0
  } reviews completed today.`;

  return (
    <div
      className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card flex flex-col justify-between min-h-[320px]"
      aria-label={ariaLabel}
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-bold text-txt-primary tracking-tight">
              Reviews in the last 7 days
            </h3>
            <p className="text-xs text-txt-muted mt-0.5">
              Daily study consistency leading up to today.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-txt-primary bg-surface-muted border border-border-subtle px-2.5 py-1 rounded-lg tabular-nums">
            <span>{totalReviews} Total</span>
          </div>
        </div>

        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 15, right: 10, left: -20, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-subtle)" />

              <XAxis
                dataKey="date"
                stroke="var(--text-muted)"
                fontSize={11}
                tickLine={false}
                tickFormatter={(val: string, idx: number) =>
                  idx === todayIdx ? 'Today' : formatIstDate(val)
                }
                label={{
                  value: 'Date',
                  position: 'insideBottom',
                  offset: -12,
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
                  value: 'Reviews',
                  angle: -90,
                  position: 'insideLeft',
                  offset: 25,
                  fill: 'var(--text-muted)',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />

              <Tooltip
                cursor={{ fill: 'var(--bg-surface-muted)' }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload as DailyReviewCount;
                    const isToday = item.date === todayDate;
                    const dateLabel = isToday
                      ? `Today (${formatIstDate(item.date)})`
                      : formatIstDate(item.date);

                    return (
                      <div className="bg-surface-elevated text-txt-primary border border-border-subtle rounded-xl px-3.5 py-2.5 text-xs shadow-elevated space-y-1">
                        <p className="font-bold text-txt-primary">{dateLabel}</p>
                        <p className="text-txt-secondary">
                          Reviews Completed:{' '}
                          <span className="font-bold text-brand tabular-nums">
                            {item.count}
                          </span>
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />

              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={32}>
                {data.map((entry, index) => {
                  const isToday = index === todayIdx;
                  return (
                    <Cell
                      key={`review-cell-${index}`}
                      fill={isToday ? 'var(--brand-primary)' : 'var(--border-strong)'}
                    />
                  );
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="pt-3 border-t border-border-subtle text-[11px] text-txt-muted flex items-center justify-between">
        <span>7-day active window</span>
        <span className="text-txt-secondary">
          Today: <strong className="text-brand font-bold tabular-nums">{todayIdx >= 0 ? data[todayIdx].count : 0}</strong> reviews
        </span>
      </div>
    </div>
  );
};
