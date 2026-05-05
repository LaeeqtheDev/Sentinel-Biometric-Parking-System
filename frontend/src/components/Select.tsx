'use client';

import { SelectHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, hint, id, children, ...rest }, ref) => {
    const selectId = id || rest.name;
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={selectId}
            className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-bone-400"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            'h-10 w-full rounded-md border border-ink-600 bg-ink-800/60 px-3 text-sm text-bone-50',
            'transition-colors focus:border-amber/60 focus:outline-none focus:ring-2 focus:ring-amber/20',
            'appearance-none bg-no-repeat',
            className,
          )}
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239a9aa3' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")",
            backgroundPosition: 'right 0.75rem center',
            backgroundSize: '0.75rem',
            paddingRight: '2.25rem',
          }}
          {...rest}
        >
          {children}
        </select>
        {hint && <p className="mt-1.5 text-xs text-bone-500">{hint}</p>}
      </div>
    );
  },
);
Select.displayName = 'Select';
