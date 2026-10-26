import React from 'react';
import { AlertOctagon } from 'lucide-react';

interface ConfigErrorScreenProps {
  message?: string;
}

export const ConfigErrorScreen: React.FC<ConfigErrorScreenProps> = ({ message }) => {
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6 text-white">
      <div className="max-w-lg w-full bg-slate-800/80 backdrop-blur-md rounded-2xl border border-rose-500/30 p-8 shadow-2xl">
        <div className="w-14 h-14 rounded-2xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center mb-6 text-rose-400">
          <AlertOctagon className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white mb-3">
          Configuration Error
        </h1>
        <p className="text-slate-300 text-sm leading-relaxed mb-6">
          {message || 'The application is missing required environment variables in production. Please check your deployment settings.'}
        </p>
        <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-700/60 font-mono text-xs text-rose-300 space-y-1">
          <div>Required: VITE_API_URL (must start with https://)</div>
          <div>Required: VITE_WS_URL (must start with wss://)</div>
        </div>
      </div>
    </div>
  );
};
