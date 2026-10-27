import React, { forwardRef, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { m, AnimatePresence } from 'motion/react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  isPassword?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      isPassword = false,
      type = 'text',
      id,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const [showPassword, setShowPassword] = useState(false);
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);
    const inputType = isPassword ? (showPassword ? 'text' : 'password') : type;

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-semibold text-txt-secondary tracking-wide uppercase"
          >
            {label}
          </label>
        )}

        <div className="relative rounded-xl shadow-xs">
          {leftIcon && (
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-txt-muted">
              {leftIcon}
            </div>
          )}

          <input
            ref={ref}
            id={inputId}
            type={inputType}
            disabled={disabled}
            className={`block w-full rounded-xl border bg-surface text-txt-primary placeholder:text-txt-muted text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-50 disabled:bg-surface-muted ${
              leftIcon ? 'pl-10' : 'pl-3.5'
            } ${rightIcon || isPassword ? 'pr-10' : 'pr-3.5'} py-2.5 ${
              error
                ? 'border-rose-400 focus-visible:ring-rose-500'
                : 'border-border-subtle hover:border-border-strong focus-visible:ring-brand'
            } ${className}`}
            {...props}
          />

          {isPassword && (
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-txt-muted hover:text-txt-primary transition-colors focus:outline-hidden"
              tabIndex={-1}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          )}

          {!isPassword && rightIcon && (
            <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-txt-muted">
              {rightIcon}
            </div>
          )}
        </div>

        <AnimatePresence mode="wait">
          {error && (
            <m.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="text-xs text-rose-500 font-medium"
            >
              {error}
            </m.p>
          )}
        </AnimatePresence>

        {!error && helperText && (
          <p className="text-xs text-txt-muted">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
