import React, { forwardRef } from 'react';
import { m, type HTMLMotionProps } from 'motion/react';

export interface CardProps extends HTMLMotionProps<'div'> {
  variant?: 'default' | 'elevated' | 'muted' | 'interactive';
  hoverLift?: boolean;
}

const variantStyles = {
  default: 'bg-surface border-border-subtle shadow-card',
  elevated: 'bg-surface-elevated border-border-subtle shadow-elevated',
  muted: 'bg-surface-muted border-border-subtle',
  interactive: 'bg-surface border-border-subtle shadow-card hover:border-brand/40 hover:shadow-card-hover cursor-pointer',
};

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      variant = 'default',
      hoverLift = false,
      className = '',
      children,
      ...motionProps
    },
    ref
  ) => {
    return (
      <m.div
        ref={ref}
        whileHover={hoverLift ? { y: -2, transition: { duration: 0.18, ease: 'easeOut' } } : undefined}
        className={`rounded-2xl border transition-colors ${variantStyles[variant]} ${className}`}
        {...motionProps}
      >
        {children}
      </m.div>
    );
  }
);

Card.displayName = 'Card';
