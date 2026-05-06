'use client';

import { useEffect, useState } from 'react';
import { Clock, Car, ArrowDownLeft, ArrowUpRight, ParkingCircle } from 'lucide-react';
import { apiGet } from '@/lib/api';
import { ParkingSession, fmtDateTime, fmtDuration, cn } from '@/lib/utils';

export default function DriverSessionsPage() {
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiGet<ParkingSession[]>('/parking/my/')
      .then(setSessions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Parking history
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          Your sessions
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          Every entry and exit, logged with timestamps.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
          Loading…
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-8 text-center">
          <Clock className="mx-auto size-10 text-bone-500" />
          <p className="mt-3 text-bone-300">No sessions yet</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {sessions.map((s) => (
            <li
              key={s.id}
              className={cn(
                'rounded-lg border p-4',
                s.status === 'PARKED'
                  ? 'border-amber/40 bg-amber/5'
                  : 'border-ink-700 bg-ink-800/40',
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'grid size-10 place-items-center rounded-md border',
                      s.status === 'PARKED'
                        ? 'border-amber/40 bg-amber/10 text-amber'
                        : 'border-ink-600 bg-ink-900 text-bone-400',
                    )}
                  >
                    <Car className="size-4" />
                  </div>
                  <div>
                    <p className="font-mono text-base font-semibold tracking-wider text-bone-50">
                      {s.vehicle_detail.plate_number}
                    </p>
                    <p className="text-xs text-bone-500">
                      {s.vehicle_detail.make} {s.vehicle_detail.model}
                    </p>
                  </div>
                </div>
                {s.status === 'PARKED' ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber">
                    <ParkingCircle className="size-3" /> Parked
                  </span>
                ) : (
                  <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
                    Exited
                  </span>
                )}
              </div>

              <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-ink-700 pt-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <ArrowDownLeft className="size-3 text-granted" />
                  <span className="text-bone-500">In</span>
                  <span className="font-mono tabular-nums text-bone-300">
                    {fmtDateTime(s.entry_time)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <ArrowUpRight className="size-3 text-denied" />
                  <span className="text-bone-500">Out</span>
                  <span className="font-mono tabular-nums text-bone-300">
                    {s.exit_time ? fmtDateTime(s.exit_time) : '—'}
                  </span>
                </div>
                {s.duration_seconds != null && (
                  <div className="col-span-2 flex items-center gap-1.5">
                    <Clock className="size-3 text-bone-500" />
                    <span className="text-bone-500">Duration</span>
                    <span className="font-mono text-bone-300">
                      {fmtDuration(s.duration_seconds)}
                    </span>
                  </div>
                )}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
