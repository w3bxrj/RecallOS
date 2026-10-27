import React, { forwardRef } from 'react';
import { m, type HTMLMotionProps } from 'motion/react';
import { Spinner } from '../common/Spinner';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  children?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-brand text-white hover:bg-brand-hover shadow-sm shadow-indigo-500/20 active:brightness-95 border-transparent',
  secondary:
    'bg-surface-elevated text-txt-primary hover:bg-surface-muted border-border-subtle shadow-xs active:bg-surface-muted',
  ghost:
    'bg-transparent text-txt-secondary hover:text-txt-primary hover:bg-surface-muted border-transparent active:bg-surface-muted',
  danger:
    'bg-rose-600 text-white hover:bg-rose-700 shadow-sm shadow-rose-500/20 active:brightness-95 border-transparent',
  outline:
    'bg-transparent text-txt-primary border-border-strong hover:bg-surface-muted active:bg-surface-muted',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs rounded-lg gap-1.5 font-medium',
  md: 'px-4 py-2 text-sm rounded-xl gap-2 font-semibold',
  lg: 'px-6 py-2.5 text-base rounded-xl gap-2.5 font-semibold',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      className = '',
      type = 'button',
      ...motionProps
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <m.button
        ref={ref}
        type={type}
        disabled={isDisabled}
        whileTap={isDisabled ? undefined : { scale: 0.98 }}
        className={`inline-flex items-center justify-center border transition-colors select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-50 disabled:pointer-events-none cursor-pointer ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
        {...motionProps}
      >
        {isLoading ? (
          <>
            <Spinner size="sm" className="shrink-0 text-current" />
            <span>{children}</span>
          </>
        ) : (
          <>
            {leftIcon && <span className="shrink-0">{leftIcon}</span>}
            {children}
            {rightIcon && <span className="shrink-0">{rightIcon}</span>}
          </>
        )}
      </m.button>
    );
  }
);

Button.displayName = 'Button';
