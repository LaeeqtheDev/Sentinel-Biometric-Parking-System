'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Home,
  Car,
  ScanFace,
  History,
  LogOut,
  ShieldCheck,
  ParkingCircle,
  FileText,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';

const PUBLIC_ROUTES = ['/driver/login', '/driver/scan','/driver/register']; // /driver/scan/[token] too

export default function DriverLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();

  const isPublic =
    PUBLIC_ROUTES.some(
      (r) => pathname === r || pathname.startsWith(r + '/'),
    ) || false;

  useEffect(() => {
    if (loading) return;
    if (!user && !isPublic) {
      router.replace('/driver/login');
    }
  }, [user, loading, router, isPublic]);

  if (isPublic) {
    return <div className="min-h-screen bg-ink-950">{children}</div>;
  }

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-950">
        <div className="size-10 animate-spin rounded-full border-2 border-amber/30 border-t-amber" />
      </div>
    );
  }

  const tabs = [
    { href: '/driver', label: 'Home', icon: Home, exact: true },
    { href: '/driver/vehicles', label: 'Vehicles', icon: Car },
    { href: '/driver/pickup', label: 'Pickup', icon: ParkingCircle },
    { href: '/driver/documents', label: 'Docs', icon: FileText },
    { href: '/driver/biometric', label: 'Biometric', icon: ScanFace },
  ];

  return (
    <div className="min-h-screen bg-ink-950 pb-20 sm:pb-0">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4">
          <Link href="/driver" className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-md bg-amber text-ink-950 glow-amber">
              <ShieldCheck className="size-4" strokeWidth={2.5} />
            </div>
            <div className="leading-tight">
              <p className="font-display text-sm font-semibold text-bone-50">
                Sentinel
              </p>
              <p className="font-mono text-[9px] uppercase tracking-widest text-bone-500">
                Driver
              </p>
            </div>
          </Link>
          <button
            onClick={logout}
            className="rounded-md p-2 text-bone-500 transition-colors hover:bg-ink-700 hover:text-denied"
            aria-label="Logout"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-6">{children}</main>

      {/* Bottom nav (mobile) / horizontal (desktop) */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-ink-700 bg-ink-950/95 backdrop-blur-md sm:static sm:mt-8 sm:border-0 sm:bg-transparent">
        <div className="mx-auto flex max-w-2xl items-center justify-around px-2 py-2 sm:justify-center sm:gap-2">
          {tabs.map(({ href, label, icon: Icon, exact }) => {
            const active = exact ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  'group flex flex-1 flex-col items-center gap-1 rounded-md py-2 transition-colors sm:flex-none sm:flex-row sm:gap-2 sm:px-4',
                  active
                    ? 'text-amber'
                    : 'text-bone-500 hover:text-bone-200',
                )}
              >
                <Icon className="size-5 sm:size-4" />
                <span className="font-mono text-[10px] uppercase tracking-wider sm:text-xs">
                  {label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
