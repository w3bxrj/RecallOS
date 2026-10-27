import React from 'react';
import { Skeleton } from '../common/Skeleton';

export const AnalyticsSkeleton: React.FC = () => {
  return (
    <div className="space-y-8 animate-fade-in" aria-busy="true" aria-label="Loading analytics data">
      {/* 5 Stat Cards Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="bg-surface rounded-2xl p-5 border border-border-subtle shadow-card space-y-3 min-h-[130px]">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-8 w-8 rounded-xl" />
            </div>
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-3 w-32" />
          </div>
        ))}
      </div>

      {/* Charts Grid Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card space-y-4 min-h-[380px]">
          <div className="flex justify-between items-center">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-[280px] w-full rounded-2xl" />
        </div>

        <div className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card space-y-4 min-h-[380px]">
          <div className="flex justify-between items-center">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-20" />
          </div>
          <Skeleton className="h-[280px] w-full rounded-2xl" />
        </div>
      </div>

      {/* Bottom Row Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-surface rounded-3xl p-6 border border-border-subtle shadow-card space-y-4 min-h-[320px]">
          <Skeleton className="h-5 w-44" />
          <Skeleton className="h-[220px] w-full rounded-2xl" />
        </div>
        <div className="bg-surface rounded-3xl p-6 border border-border-subtle shadow-card space-y-4 min-h-[320px]">
          <Skeleton className="h-5 w-32" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        </div>
      </div>

    </div>
  );
};
