import React from 'react';
import { Loader2, Server } from 'lucide-react';
import { useWakeupBanner } from '../../hooks/useWakeupBanner';

export const WakeupBanner: React.FC = () => {
  const isWaking = useWakeupBanner();

  if (!isWaking) return null;

  return (
    <div className="bg-amber-500 text-white px-4 py-2.5 shadow-md flex items-center justify-center gap-2.5 text-xs sm:text-sm font-medium z-50 sticky top-0 animate-fade-in">
      <Server className="w-4 h-4 shrink-0" />
      <span>Server is waking up, this can take up to a minute...</span>
      <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0 opacity-80" />
    </div>
  );
};
