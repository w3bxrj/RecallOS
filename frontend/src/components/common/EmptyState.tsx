import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Button } from '../ui/Button';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  actionHref?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  actionText,
  onAction,
  actionHref,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 md:p-12 text-center rounded-3xl border border-dashed border-border-subtle bg-surface/60 max-w-lg mx-auto shadow-xs">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100/80 dark:bg-indigo-950/40 dark:border-indigo-900/50 flex items-center justify-center mb-4 text-indigo-600 dark:text-indigo-400 shadow-xs">
          <Icon className="w-7 h-7" />
        </div>
      )}
      <h3 className="text-lg font-bold text-txt-primary mb-1 tracking-tight">{title}</h3>
      <p className="text-sm text-txt-secondary mb-6 max-w-xs">{description}</p>
      {actionText && (
        actionHref ? (
          <a
            href={actionHref}
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-semibold text-white bg-brand hover:bg-brand-hover rounded-xl shadow-xs transition-colors duration-150"
          >
            {actionText}
          </a>
        ) : (
          <Button onClick={onAction} variant="primary" size="md">
            {actionText}
          </Button>
        )
      )}
    </div>
  );
};

