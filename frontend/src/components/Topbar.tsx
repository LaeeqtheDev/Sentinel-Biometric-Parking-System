'use client';

import { useEffect, useState } from 'react';

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const [now, setNow] = useState<string>('');

  useEffect(() => {
    const tick = () =>
      setNow(
        new Date().toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }),
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-ink-700 bg-ink-950/80 px-6 backdrop-blur-md">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight text-bone-50">
          {title}
        </h1>
        {subtitle && (
          <p className="text-xs text-bone-500">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 rounded-full border border-ink-600 bg-ink-800/60 px-3 py-1 sm:flex">
          <span className="size-1.5 rounded-full bg-granted animate-pulse-soft" />
          <span className="font-mono text-[11px] uppercase tracking-wider text-bone-400">
            System Online
          </span>
        </div>
        <div className="rounded-md border border-ink-600 bg-ink-800/60 px-3 py-1 font-mono text-xs tabular-nums text-bone-300">
          {now}
        </div>
      </div>
    </header>
  );
}
