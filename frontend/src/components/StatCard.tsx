import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  accent?: boolean;
}

export function StatCard({ label, value, hint, icon: Icon, accent }: Props) {
  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-lg border bg-ink-800/40 p-5 transition-colors',
        accent
          ? 'border-amber/30 hover:border-amber/50'
          : 'border-ink-600 hover:border-ink-500',
      )}
    >
      {accent && (
        <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-amber/10 blur-3xl" />
      )}
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-medium uppercase tracking-[0.15em] text-bone-400">
          {label}
        </span>
        {Icon && (
          <Icon
            className={cn(
              'size-4 transition-colors',
              accent ? 'text-amber' : 'text-bone-500 group-hover:text-bone-400',
            )}
          />
        )}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span
          className={cn(
            'font-display text-3xl font-semibold tracking-tight',
            accent ? 'text-amber-glow' : 'text-bone-50',
          )}
        >
          {value}
        </span>
      </div>
      {hint && <p className="mt-1 text-xs text-bone-500">{hint}</p>}
    </div>
  );
}
