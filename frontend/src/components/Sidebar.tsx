'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Car,
  Users,
  ScrollText,
  ScanLine,
  Video,
  ParkingCircle,
  ClipboardCheck,
  Settings,
  Shield,
  LogOut,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';

const navItems = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard, exact: true },
  { href: '/dashboard/live-camera', label: 'Live Camera', icon: Video },
  { href: '/dashboard/entry', label: 'Manual Gate', icon: ScanLine },
  { href: '/dashboard/sessions', label: 'Sessions', icon: ParkingCircle },
  { href: '/dashboard/vehicles', label: 'Vehicles', icon: Car },
  { href: '/dashboard/approvals', label: 'Approvals', icon: ClipboardCheck },
  { href: '/dashboard/users', label: 'Users', icon: Users },
  { href: '/dashboard/logs', label: 'Access Logs', icon: ScrollText },
  { href: '/dashboard/risk-events', label: 'Risk Events', icon: Shield },
  { href: '/dashboard/policy', label: 'Policy', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="hidden h-screen w-60 shrink-0 flex-col border-r border-ink-700 bg-ink-900/60 lg:flex">
      {/* Logo / brand */}
      <div className="flex h-16 items-center gap-2.5 border-b border-ink-700 px-5">
        <div className="grid size-8 place-items-center rounded-md bg-amber text-ink-950 glow-amber">
          <ShieldCheck className="size-4" strokeWidth={2.5} />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="font-display text-base font-semibold tracking-tight text-bone-50">
            Sentinel
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
            Parking · v0.2
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-0.5 px-3 py-5">
        <p className="px-3 pb-2 font-mono text-[10px] uppercase tracking-widest text-bone-500">
          Navigation
        </p>
        {navItems.map(({ href, label, icon: Icon, exact }) => {
          const active = exact
            ? pathname === href
            : pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-ink-700/60 text-bone-50'
                  : 'text-bone-400 hover:bg-ink-700/40 hover:text-bone-200',
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-amber shadow-[0_0_8px_rgba(251,191,36,0.6)]" />
              )}
              <Icon
                className={cn(
                  'size-4 transition-colors',
                  active ? 'text-amber' : 'text-bone-500 group-hover:text-bone-300',
                )}
              />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User card */}
      <div className="border-t border-ink-700 p-3">
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          <div className="grid size-9 place-items-center rounded-full bg-ink-700 font-mono text-xs font-semibold uppercase text-bone-200">
            {(user?.first_name?.[0] || user?.username?.[0] || '?').toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-bone-100">
              {user?.first_name || user?.username || 'User'}
            </p>
            <p className="truncate font-mono text-[10px] uppercase tracking-wider text-bone-500">
              {user?.role || '—'}
            </p>
          </div>
          <button
            onClick={logout}
            className="rounded-md p-2 text-bone-500 transition-colors hover:bg-ink-700 hover:text-denied"
            title="Logout"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
