'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  Car,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  Clock,
  Calendar,
  ParkingCircle,
  AlertCircle,
} from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { StatCard } from '@/components/StatCard';
import { StatusBadge } from '@/components/StatusBadge';
import { apiGet } from '@/lib/api';
import { Stats, fmtDateTime } from '@/lib/utils';

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiGet<Stats>('/access/stats/')
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <Topbar
        title="Overview"
        subtitle="Real-time parking surveillance metrics."
      />

      <main className="flex-1 space-y-8 p-6 lg:p-8">
        {error && (
          <div className="rounded-md border border-denied/30 bg-denied/10 px-4 py-3 text-sm text-denied">
            {error}
          </div>
        )}

        {/* Alert banner: show if there are recent denials */}
        {stats && stats.totals.today_denied > 0 && (
          <div className="flex items-start gap-3 rounded-md border border-denied/30 bg-denied/5 px-4 py-3">
            <AlertCircle className="mt-0.5 size-5 shrink-0 text-denied" />
            <div className="flex-1">
              <p className="text-sm font-medium text-denied">
                {stats.totals.today_denied} denied access{' '}
                {stats.totals.today_denied === 1 ? 'attempt' : 'attempts'}{' '}
                today
              </p>
              <p className="text-xs text-bone-400">
                Review them in{' '}
                <Link href="/dashboard/logs" className="underline">
                  Access Logs
                </Link>{' '}
                — multiple denials may indicate an unauthorized entry attempt.
              </p>
            </div>
          </div>
        )}

        {/* ----- Stat row ----- */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard
            label="Today · Total"
            value={stats?.totals.today ?? '—'}
            hint="Access attempts in the last 24h"
            icon={Activity}
            accent
          />
          <StatCard
            label="Today · Granted"
            value={stats?.totals.today_granted ?? '—'}
            hint="Successful entries today"
            icon={CheckCircle2}
          />
          <StatCard
            label="Today · Denied"
            value={stats?.totals.today_denied ?? '—'}
            hint="Failed verification today"
            icon={XCircle}
          />
          <StatCard
            label="Currently Parked"
            value={stats?.active_sessions ?? '—'}
            hint="Vehicles inside the lot"
            icon={ParkingCircle}
          />
          <StatCard
            label="Registered Vehicles"
            value={stats?.registered_vehicles ?? '—'}
            hint="Currently active in the system"
            icon={Car}
          />
        </section>

        {/* ----- Two-column: weekly chart + recent logs ----- */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          {/* Weekly bars */}
          <div className="lg:col-span-2 rounded-lg border border-ink-600 bg-ink-800/40 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="font-display text-lg font-semibold text-bone-50">
                  Last 7 days
                </h2>
                <p className="text-xs text-bone-500">
                  Granted vs denied attempts per day
                </p>
              </div>
              <Calendar className="size-4 text-bone-500" />
            </div>
            <WeeklyChart data={stats?.last_7_days ?? []} />
            <div className="mt-4 flex items-center gap-4 border-t border-ink-700 pt-3 text-xs text-bone-400">
              <div className="flex items-center gap-1.5">
                <span className="size-2 rounded-sm bg-granted" />
                Granted
              </div>
              <div className="flex items-center gap-1.5">
                <span className="size-2 rounded-sm bg-denied" />
                Denied
              </div>
            </div>
          </div>

          {/* Recent logs */}
          <div className="lg:col-span-3 rounded-lg border border-ink-600 bg-ink-800/40 p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="font-display text-lg font-semibold text-bone-50">
                  Recent activity
                </h2>
                <p className="text-xs text-bone-500">
                  Latest 5 access attempts
                </p>
              </div>
              <Link
                href="/dashboard/logs"
                className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-wider text-amber transition-colors hover:text-amber-glow"
              >
                View all <ArrowUpRight className="size-3" />
              </Link>
            </div>

            <div className="space-y-2">
              {stats?.recent_logs.length === 0 && (
                <p className="py-8 text-center text-sm text-bone-500">
                  No activity yet. Try the{' '}
                  <Link
                    href="/dashboard/entry"
                    className="text-amber hover:underline"
                  >
                    Live Entry
                  </Link>{' '}
                  page to simulate access.
                </p>
              )}

              {stats?.recent_logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between gap-4 rounded-md border border-ink-700 bg-ink-900/40 p-3 transition-colors hover:border-ink-600"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <Clock className="size-3.5 shrink-0 text-bone-500" />
                    <span className="font-mono text-xs tabular-nums text-bone-400">
                      {fmtDateTime(log.timestamp)}
                    </span>
                    <span className="rounded border border-ink-600 bg-ink-800/60 px-2 py-0.5 font-mono text-xs font-semibold tracking-wider text-bone-100">
                      {log.plate_detected}
                    </span>
                    <span className="hidden truncate text-xs text-bone-500 sm:inline">
                      {log.reason}
                    </span>
                  </div>
                  <StatusBadge status={log.status} />
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ----- All-time totals ----- */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="All time · Attempts"
            value={stats?.totals.all_time ?? '—'}
            icon={Activity}
          />
          <StatCard
            label="All time · Granted"
            value={stats?.totals.granted ?? '—'}
            icon={CheckCircle2}
          />
          <StatCard
            label="All time · Denied"
            value={stats?.totals.denied ?? '—'}
            icon={XCircle}
          />
        </section>
      </main>
    </>
  );
}

/* -------------------- inline mini bar chart -------------------- */
function WeeklyChart({
  data,
}: {
  data: { day: string; granted: number; denied: number }[];
}) {
  const days: { day: string; granted: number; denied: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const found = data.find((r) => r.day === key);
    days.push({
      day: d.toLocaleDateString('en-US', { weekday: 'short' }),
      granted: found?.granted ?? 0,
      denied: found?.denied ?? 0,
    });
  }

  const max = Math.max(...days.map((d) => d.granted + d.denied), 1);

  return (
    <div className="flex h-44 items-end justify-between gap-2">
      {days.map((d, i) => {
        const total = d.granted + d.denied;
        // Minimum 8% height so bars are always visible
        const totalH = Math.max((total / max) * 100, 8);
        const grantedH = total > 0 ? (d.granted / total) * 100 : 0;
        const isToday = i === 6;
        return (
          <div key={i} className="flex flex-1 flex-col items-center gap-2">
            {/* Count label on top */}
            <span className={`font-mono text-[10px] ${total > 0 ? 'text-bone-300' : 'text-bone-700'}`}>
              {total > 0 ? total : '·'}
            </span>
            <div
              className={`relative flex w-full flex-col-reverse overflow-hidden rounded-sm transition-all ${isToday ? 'ring-1 ring-amber/40' : ''}`}
              style={{ height: `${totalH}%` }}
            >
              {total === 0 ? (
                <div className="h-full w-full bg-ink-700/30" />
              ) : (
                <>
                  <div className="bg-granted/70" style={{ height: `${grantedH}%` }} />
                  <div className="bg-denied/70" style={{ height: `${100 - grantedH}%` }} />
                </>
              )}
            </div>
            <span className={`font-mono text-[10px] uppercase tracking-wider ${isToday ? 'text-amber' : 'text-bone-500'}`}>
              {d.day}
            </span>
          </div>
        );
      })}
    </div>
  );
}
