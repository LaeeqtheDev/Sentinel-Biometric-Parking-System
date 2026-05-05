'use client';

import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, error, id, ...rest }, ref) => {
    const inputId = id || rest.name;
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-bone-400"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'h-10 w-full rounded-md border border-ink-600 bg-ink-800/60 px-3 text-sm text-bone-50 placeholder:text-bone-500',
            'transition-colors focus:border-amber/60 focus:outline-none focus:ring-2 focus:ring-amber/20',
            error && 'border-denied/60 focus:border-denied focus:ring-denied/20',
            className,
          )}
          {...rest}
        />
        {error ? (
          <p className="mt-1.5 text-xs text-denied">{error}</p>
        ) : hint ? (
          <p className="mt-1.5 text-xs text-bone-500">{hint}</p>
        ) : null}
      </div>
    );
  },
);
Input.displayName = 'Input';
