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
      className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-xs flex flex-col justify-between min-h-[320px]"
      aria-label={ariaLabel}
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Reviews in the last 7 days
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Daily study consistency leading up to today.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg">
            <span>{totalReviews} Total</span>
          </div>
        </div>

        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 15, right: 10, left: -20, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />

              <XAxis
                dataKey="date"
                stroke="#94a3b8"
                fontSize={11}
                tickLine={false}
                tickFormatter={(val: string, idx: number) =>
                  idx === todayIdx ? 'Today' : formatIstDate(val)
                }
                label={{
                  value: 'Date',
                  position: 'insideBottom',
                  offset: -12,
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
                  value: 'Reviews',
                  angle: -90,
                  position: 'insideLeft',
                  offset: 25,
                  fill: '#64748b',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />

              <Tooltip
                cursor={{ fill: '#f8fafc' }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload as DailyReviewCount;
                    const isToday = item.date === todayDate;
                    const dateLabel = isToday
                      ? `Today (${formatIstDate(item.date)})`
                      : formatIstDate(item.date);

                    return (
                      <div className="bg-slate-900 text-white rounded-xl px-3 py-2 text-xs shadow-lg space-y-1">
                        <p className="font-bold text-slate-100">{dateLabel}</p>
                        <p className="text-indigo-300">
                          Reviews:{' '}
                          <span className="font-extrabold text-white">
                            {item.count}
                          </span>
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />

              <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={32}>
                {data.map((entry, index) => {
                  const isToday = index === todayIdx;
                  return (
                    <Cell
                      key={`review-bar-${index}`}
                      fill={isToday ? '#4f46e5' : '#cbd5e1'}
                      stroke={isToday ? '#4338ca' : '#94a3b8'}
                      strokeWidth={isToday ? 1.5 : 1}
                    />
                  );
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-indigo-600 inline-block" />
          <span className="font-medium text-slate-700">Today's reviews highlighted</span>
        </div>
        <span className="text-slate-400">Past 6 days in slate</span>
      </div>
    </div>
  );
};
