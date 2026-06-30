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
  AlertCircle,
  FileText,
  Plus,
  Fingerprint,
  TrendingUp,
} from 'lucide-react';
import { apiGet } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Vehicle, ParkingSession, fmtDateTime, fmtDuration, cn } from '@/lib/utils';

export default function DriverHomePage() {
  const { user } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<Vehicle[]>('/vehicles/my/').catch(() => []),
      apiGet<ParkingSession[]>('/parking/my/').catch(() => []),
    ])
      .then(([v, s]) => {
        setVehicles(v);
        setSessions(s);
      })
      .finally(() => setLoading(false));
  }, []);

  const parked = sessions.filter((s) => s.status === 'PARKED');
  const completed = sessions.filter((s) => s.status === 'EXITED').length;
  const trustScore = user?.trust_score ?? 60;
  const trustLevel = user?.trust_level ?? 'NORMAL';
  const docsVerified = !!user?.documents_verified;
  const hasBiometric = !!user?.has_biometric;
  const pendingVehicles = vehicles.filter((v) => v.status === 'UNDER_REVIEW').length;
  const blockedVehicles = vehicles.filter((v) => v.status === 'BLOCKED').length;

  // Compliance score: % of compliance steps completed
  const complianceSteps = [docsVerified, hasBiometric, pendingVehicles === 0];
  const compliancePct = Math.round(
    (complianceSteps.filter(Boolean).length / complianceSteps.length) * 100,
  );

  return (
    <div className="space-y-6">
      {/* Greeting */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Welcome back
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          Hello, {user?.first_name || user?.username}
        </h1>
        <p className="mt-1 text-sm text-bone-400">
          Your gate access dashboard.
        </p>
      </div>

      {/* Currently parked */}
      {parked.length > 0 && (
        <section className="rounded-lg border border-amber/40 bg-amber/5 p-5">
          <div className="mb-3 flex items-center gap-2">
            <ParkingCircle className="size-4 text-amber" />
            <h2 className="font-mono text-[11px] uppercase tracking-wider text-amber">
              · Currently parked
            </h2>
          </div>
          {parked.map((s) => (
            <div key={s.id} className="flex items-center justify-between">
              <div>
                <p className="font-mono text-lg font-semibold tracking-wider text-bone-50">
                  {s.vehicle_detail.plate_number}
                </p>
                <p className="text-xs text-bone-400">
                  Since {fmtDateTime(s.entry_time)} ·{' '}
                  {fmtDuration(s.duration_seconds)}
                </p>
              </div>
              <Link
                href="/driver/pickup"
                className="inline-flex items-center gap-1.5 rounded-md bg-amber px-3 py-2 font-mono text-xs uppercase tracking-wider text-ink-950 hover:bg-amber/80"
              >
                Pickup <ArrowRight className="size-3" />
              </Link>
            </div>
          ))}
        </section>
      )}

      {/* Trust + compliance row */}
      <div className="grid gap-3 sm:grid-cols-2">
        {/* Trust score card */}
        <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
              Trust score
            </span>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
                trustLevel === 'TRUSTED'
                  ? 'bg-granted/10 text-granted'
                  : trustLevel === 'SUSPICIOUS'
                  ? 'bg-denied/10 text-denied'
                  : 'bg-amber/10 text-amber',
              )}
            >
              {trustLevel}
            </span>
          </div>
          <p className="font-display text-3xl font-semibold tracking-tight text-bone-50">
            {trustScore}
            <span className="ml-1 text-base text-bone-500">/100</span>
          </p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-700">
            <div
              className={cn(
                'h-full rounded-full',
                trustLevel === 'TRUSTED'
                  ? 'bg-granted'
                  : trustLevel === 'SUSPICIOUS'
                  ? 'bg-denied'
                  : 'bg-amber',
              )}
              style={{ width: `${trustScore}%` }}
            />
          </div>
          <p className="mt-2 text-[11px] text-bone-500">
            {trustLevel === 'TRUSTED'
              ? '🚀 Auto-entry eligible during off-peak.'
              : trustLevel === 'SUSPICIOUS'
              ? '⚠ Strict verification required at every gate.'
              : 'Standard verification at gates.'}
          </p>
        </div>

        {/* Compliance card */}
        <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
              Compliance
            </span>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
                compliancePct === 100
                  ? 'bg-granted/10 text-granted'
                  : 'bg-amber/10 text-amber',
              )}
            >
              {compliancePct}%
            </span>
          </div>
          <ul className="mt-1 space-y-1.5">
            <ComplianceRow ok={docsVerified} label="Identity docs verified" href="/driver/documents" />
            <ComplianceRow ok={hasBiometric} label="Biometric enrolled" href="/driver/biometric" />
            <ComplianceRow
              ok={pendingVehicles === 0 && vehicles.length > 0}
              label={
                pendingVehicles > 0
                  ? `${pendingVehicles} vehicle${pendingVehicles > 1 ? 's' : ''} pending`
                  : vehicles.length === 0
                  ? 'No vehicles added'
                  : 'All vehicles approved'
              }
              href="/driver/vehicles"
            />
          </ul>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <StatBlock label="Vehicles" value={vehicles.length} icon={Car} />
        <StatBlock label="Trips" value={completed} icon={TrendingUp} />
        <StatBlock label="Parked now" value={parked.length} icon={ParkingCircle} accent />
      </div>

      {/* Block alerts */}
      {blockedVehicles > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">
              {blockedVehicles} vehicle{blockedVehicles > 1 ? 's' : ''} BLOCKED
            </p>
            <p className="text-[11px] text-denied/80">
              Contact admin to resolve. Blocked vehicles cannot enter the gate.
            </p>
          </div>
        </div>
      )}

      {/* Action grid */}
      <section>
        <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wider text-bone-500">
          · Quick actions
        </h2>
        <div className="grid grid-cols-2 gap-2.5">
          <ActionCard
            href="/driver/vehicles"
            icon={Car}
            title="My vehicles"
            sub={`${vehicles.length} on file`}
          />
          <ActionCard
            href="/driver/pickup"
            icon={ParkingCircle}
            title="Pickup"
            sub={parked.length > 0 ? 'Active session' : 'No parked car'}
            highlight={parked.length > 0}
          />
          <ActionCard
            href="/driver/documents"
            icon={FileText}
            title="Documents"
            sub={docsVerified ? '✓ Verified' : 'Pending'}
          />
          <ActionCard
            href="/driver/biometric"
            icon={Fingerprint}
            title="Biometric"
            sub={hasBiometric ? '✓ Enrolled' : 'Not set up'}
          />
        </div>
      </section>

      {/* Vehicles preview */}
      {vehicles.length > 0 && (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-mono text-[11px] uppercase tracking-wider text-bone-500">
              · My vehicles
            </h2>
            <Link
              href="/driver/vehicles"
              className="font-mono text-[11px] uppercase tracking-wider text-amber hover:underline"
            >
              View all →
            </Link>
          </div>
          <ul className="space-y-2">
            {vehicles.slice(0, 3).map((v) => (
              <li
                key={v.id}
                className="flex items-center gap-3 rounded-md border border-ink-700 bg-ink-800/40 p-3"
              >
                <div
                  className={cn(
                    'grid size-9 place-items-center rounded-md',
                    v.status === 'ACTIVE'
                      ? 'bg-granted/10 text-granted'
                      : v.status === 'BLOCKED'
                      ? 'bg-denied/10 text-denied'
                      : 'bg-amber/10 text-amber',
                  )}
                >
                  <Car className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-sm font-semibold tracking-wider text-bone-50">
                    {v.plate_number}
                  </p>
                  <p className="text-[11px] text-bone-500">
                    {v.make} {v.model} ·{' '}
                    <span
                      className={cn(
                        v.status === 'ACTIVE'
                          ? 'text-granted'
                          : v.status === 'BLOCKED'
                          ? 'text-denied'
                          : 'text-amber',
                      )}
                    >
                      {v.status.toLowerCase().replace('_', ' ')}
                    </span>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ComplianceRow({
  ok,
  label,
  href,
}: {
  ok: boolean;
  label: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center justify-between text-xs"
    >
      <span className="flex items-center gap-1.5">
        {ok ? (
          <CheckCircle2 className="size-3 text-granted" />
        ) : (
          <Clock className="size-3 text-amber" />
        )}
        <span className={ok ? 'text-bone-300' : 'text-amber'}>{label}</span>
      </span>
      <ArrowRight className="size-3 text-bone-600 group-hover:text-amber" />
    </Link>
  );
}

function StatBlock({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: any;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border p-3',
        accent
          ? 'border-amber/40 bg-amber/5'
          : 'border-ink-700 bg-ink-800/40',
      )}
    >
      <div className="flex items-center gap-1.5">
        <Icon className={cn('size-3', accent ? 'text-amber' : 'text-bone-500')} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
          {label}
        </span>
      </div>
      <p className="mt-1 font-display text-2xl font-semibold tracking-tight text-bone-50">
        {value}
      </p>
    </div>
  );
}

function ActionCard({
  href,
  icon: Icon,
  title,
  sub,
  highlight,
}: {
  href: string;
  icon: any;
  title: string;
  sub: string;
  highlight?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'group flex items-center gap-3 rounded-lg border p-3 transition-colors',
        highlight
          ? 'border-amber/40 bg-amber/5 hover:bg-amber/10'
          : 'border-ink-700 bg-ink-800/40 hover:border-ink-500',
      )}
    >
      <div
        className={cn(
          'grid size-10 place-items-center rounded-md',
          highlight ? 'bg-amber/10 text-amber' : 'bg-ink-700 text-bone-300',
        )}
      >
        <Icon className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-bone-100">{title}</p>
        <p className="text-[11px] text-bone-500">{sub}</p>
      </div>
      <ArrowRight className="size-4 shrink-0 text-bone-500 group-hover:text-amber" />
    </Link>
  );
}
