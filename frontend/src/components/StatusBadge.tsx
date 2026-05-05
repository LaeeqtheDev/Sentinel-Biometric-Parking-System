import { cn } from '@/lib/utils';

interface Props {
  status: 'GRANTED' | 'DENIED' | 'PENDING' | string;
  className?: string;
}

export function StatusBadge({ status, className }: Props) {
  const map: Record<string, string> = {
    GRANTED: 'bg-granted/10 text-granted border-granted/30',
    DENIED: 'bg-denied/10 text-denied border-denied/30',
    PENDING: 'bg-pending/10 text-pending border-pending/30',
  };
  const dotMap: Record<string, string> = {
    GRANTED: 'bg-granted shadow-[0_0_8px_rgba(52,211,153,0.6)]',
    DENIED: 'bg-denied shadow-[0_0_8px_rgba(248,113,113,0.6)]',
    PENDING: 'bg-pending',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider',
        map[status] || map.PENDING,
        className,
      )}
    >
      <span
        className={cn(
          'inline-block size-1.5 rounded-full',
          dotMap[status] || dotMap.PENDING,
        )}
      />
      {status}
    </span>
  );
}
