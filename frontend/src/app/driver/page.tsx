'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Car,
  Clock,
  ScanFace,
  ArrowRight,
  ParkingCircle,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';
import { apiGet } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Vehicle, ParkingSession, fmtDateTime, cn } from '@/lib/utils';

export default function DriverHomePage() {
  const { user } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      apiGet<Vehicle[]>('/vehicles/my/'),
      apiGet<ParkingSession[]>('/parking/my/'),
    ])
      .then(([v, s]) => {
        setVehicles(v);
        setSessions(s);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const activeSessions = sessions.filter((s) => s.status === 'PARKED');
  const hasPasskey = user?.has_biometric || false; // we'll re-fetch for passkeys list elsewhere

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Welcome back
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          {user?.first_name || user?.username} 👋
        </h1>
        <p className="mt-1 text-sm text-bone-400">
          Your vehicles, your sessions, all in one place.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}

      {/* Active session card – the most important thing for a driver */}
      {activeSessions.length > 0 && (
        <Link
          href="/driver/pickup"
          className="block rounded-lg border border-amber/40 bg-gradient-to-br from-amber/10 to-transparent p-5 transition-colors hover:border-amber/60"
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber">
                <span className="size-1.5 rounded-full bg-amber animate-pulse-soft" />
                Currently parked
              </div>
              <h2 className="mt-3 font-display text-2xl font-semibold tracking-tight text-bone-50">
                {activeSessions[0].vehicle_detail.plate_number}
              </h2>
              <p className="mt-1 text-sm text-bone-400">
                Parked since {fmtDateTime(activeSessions[0].entry_time)}
              </p>
            </div>
            <ParkingCircle className="size-8 text-amber" strokeWidth={1.5} />
          </div>
          <div className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-amber">
            Pick up car <ArrowRight className="size-3" />
          </div>
        </Link>
      )}

      {/* Action grid */}
      <section className="grid grid-cols-2 gap-3">
        <ActionCard
          href="/driver/pickup"
          icon={Car}
          label="Pickup"
          hint="Verify & exit"
        />
        <ActionCard
          href="/driver/biometric"
          icon={ShieldCheck}
          label="Passkey"
          hint={hasPasskey ? 'Enrolled' : 'Set up'}
          highlight={!hasPasskey}
        />
        <ActionCard
          href="/driver/sessions"
          icon={Clock}
          label="History"
          hint={`${sessions.length} sessions`}
        />
        <div className="rounded-lg border border-ink-600 bg-ink-800/40 p-4">
          <Car className="size-5 text-bone-500" />
          <p className="mt-3 text-xs uppercase tracking-wider text-bone-500">
            My vehicles
          </p>
          <p className="font-display text-2xl font-semibold text-bone-50">
            {loading ? '…' : vehicles.length}
          </p>
        </div>
      </section>

      {/* My vehicles list */}
      <section>
        <h3 className="mb-3 font-mono text-[11px] uppercase tracking-widest text-bone-500">
          My vehicles
        </h3>
        {loading ? (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
            Loading…
          </div>
        ) : vehicles.length === 0 ? (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
            No vehicles linked to your account yet. Ask an admin to register
            you.
          </div>
        ) : (
          <ul className="space-y-2">
            {vehicles.map((v) => {
              const session = activeSessions.find(
                (s) => s.vehicle === v.id,
              );
              return (
                <li
                  key={v.id}
                  className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-800/40 p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="grid size-10 place-items-center rounded-md border border-ink-600 bg-ink-900">
                      <Car className="size-5 text-bone-400" />
                    </div>
                    <div>
                      <p className="font-mono text-base font-semibold tracking-wider text-bone-50">
                        {v.plate_number}
                      </p>
                      <p className="text-xs text-bone-500">
                        {v.make} {v.model}{' '}
                        <span className="text-bone-600">·</span>{' '}
                        {v.vehicle_type}
                      </p>
                    </div>
                  </div>
                  {session ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber">
                      <ParkingCircle className="size-3" /> Parked
                    </span>
                  ) : (
                    <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
                      Out
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function ActionCard({
  href,
  icon: Icon,
  label,
  hint,
  highlight,
}: {
  href: string;
  icon: any;
  label: string;
  hint: string;
  highlight?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'group block rounded-lg border bg-ink-800/40 p-4 transition-colors',
        highlight
          ? 'border-amber/40 hover:border-amber/60'
          : 'border-ink-600 hover:border-ink-500',
      )}
    >
      <Icon
        className={cn(
          'size-5',
          highlight
            ? 'text-amber'
            : 'text-bone-500 group-hover:text-bone-300',
        )}
      />
      <p className="mt-3 text-xs uppercase tracking-wider text-bone-500">
        {hint}
      </p>
      <p className="font-display text-lg font-semibold text-bone-50">
        {label}
      </p>
    </Link>
  );
}
