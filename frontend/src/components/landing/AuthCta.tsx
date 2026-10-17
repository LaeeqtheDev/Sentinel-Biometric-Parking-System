'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';

/** Nav / hero buttons that adapt to whether someone is already signed in. */
export function AuthCta({ variant = 'nav' }: { variant?: 'nav' | 'hero' }) {
  const { user, loading } = useAuth();
  const home = user?.role === 'ADMIN' ? '/dashboard' : '/driver';

  if (variant === 'nav') {
    if (!loading && user) {
      return (
        <Link
          href={home}
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-amber px-3.5 text-sm font-medium text-ink-950 transition-colors hover:bg-amber-glow"
        >
          Open {user.role === 'ADMIN' ? 'console' : 'my garage'}
          <ArrowRight className="size-3.5" />
        </Link>
      );
    }
    return (
      <div className="flex items-center gap-1 sm:gap-2">
        <Link
          href="/driver/login"
          className="hidden h-9 items-center rounded-md px-3 text-sm text-bone-200 transition-colors hover:bg-ink-700 sm:inline-flex"
        >
          Driver sign in
        </Link>
        <Link
          href="/login"
          className="inline-flex h-9 items-center rounded-md border border-ink-600 bg-ink-800 px-3.5 text-sm text-bone-50 transition-colors hover:border-ink-500 hover:bg-ink-700"
        >
          Operator console
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <Link
        href={!loading && user ? home : '/driver/register'}
        className={cn(
          'glow-amber inline-flex h-12 items-center justify-center gap-2 rounded-md bg-amber px-6 font-medium text-ink-950 transition-colors hover:bg-amber-glow',
        )}
      >
        {!loading && user ? 'Go to your dashboard' : 'Register as a driver'}
        <ArrowRight className="size-4" />
      </Link>
      <a
        href="#how-it-works"
        className="inline-flex h-12 items-center justify-center rounded-md border border-ink-600 px-6 text-bone-50 transition-colors hover:border-ink-500 hover:bg-ink-800"
      >
        See how the gate decides
      </a>
    </div>
  );
}
