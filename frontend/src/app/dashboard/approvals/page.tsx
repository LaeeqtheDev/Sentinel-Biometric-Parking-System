'use client';

import { useEffect, useState } from 'react';
import {
  Car,
  CheckCircle2,
  XCircle,
  FileText,
  Clock,
  RefreshCw,
  ShieldCheck,
  ExternalLink,
  AlertCircle,
} from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { apiGet, apiPost } from '@/lib/api';
import { Vehicle, fmtDateTime, cn } from '@/lib/utils';

const MEDIA_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(
  /\/api\/?$/,
  '',
);

function fileURL(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.startsWith('http') ? path : `${MEDIA_BASE}${path}`;
}

export default function ApprovalsPage() {
  const [pending, setPending] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const v = await apiGet<Vehicle[]>('/vehicles/pending-approvals/');
      setPending(v);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function approve(id: number) {
    try {
      await apiPost(`/vehicles/${id}/approve/`, {});
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function block(id: number) {
    const reason = prompt('Reason for blocking?', 'Suspicious');
    if (reason === null) return;
    try {
      await apiPost(`/vehicles/${id}/block/`, { reason });
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <>
      <Topbar
        title="Pending approvals"
        subtitle="Vehicles awaiting review. Approve, block, or open documents."
      />
      <main className="flex-1 space-y-6 p-6 lg:p-8">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[11px] uppercase tracking-wider text-bone-500">
            {pending.length} vehicle{pending.length !== 1 ? 's' : ''} pending
          </p>
          <Button onClick={load} variant="ghost" size="sm">
            <RefreshCw className="size-3.5" /> Refresh
          </Button>
        </div>

        {error && (
          <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-8 text-center text-bone-500">
            Loading…
          </div>
        ) : pending.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-12 text-center">
            <CheckCircle2 className="mx-auto size-10 text-granted" />
            <p className="mt-3 font-medium text-bone-200">All caught up!</p>
            <p className="mt-1 text-sm text-bone-500">
              No vehicles waiting for approval.
            </p>
          </div>
        ) : (
          <ul className="grid gap-4 lg:grid-cols-2">
            {pending.map((v) => {
              const driverDoc = v.assignments?.[0]?.user_detail;
              const regDoc = fileURL(v.registration_doc);
              const licDoc = fileURL(driverDoc?.driving_license_doc);
              const cnicDoc = fileURL(driverDoc?.cnic_doc);
              return (
                <li
                  key={v.id}
                  className="rounded-lg border border-amber/30 bg-amber/5 p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="grid size-12 place-items-center rounded-md border border-amber/40 bg-amber/10 text-amber">
                        <Car className="size-5" />
                      </div>
                      <div>
                        <p className="font-mono text-base font-semibold tracking-wider text-bone-50">
                          {v.plate_number}
                        </p>
                        <p className="text-xs text-bone-400">
                          {v.make || '—'} {v.model} · {v.color || 'unknown'}
                        </p>
                        <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                          Submitted {fmtDateTime(v.created_at)}
                        </p>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber">
                      <Clock className="size-3" /> Review
                    </span>
                  </div>

                  {/* Linked drivers */}
                  <div className="mt-4 border-t border-ink-700 pt-3">
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-bone-500">
                      Linked users ({v.assignments?.length || 0})
                    </p>
                    {v.assignments && v.assignments.length > 0 ? (
                      <ul className="space-y-1.5">
                        {v.assignments.map((a) => (
                          <li
                            key={a.id}
                            className="flex items-center gap-2 text-sm text-bone-200"
                          >
                            <ShieldCheck className="size-3 text-bone-500" />
                            {a.user_detail?.first_name}{' '}
                            {a.user_detail?.last_name}
                            <span className="text-bone-500">
                              @{a.user_detail?.username}
                            </span>
                            <span className="ml-auto rounded-full bg-ink-700 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-bone-300">
                              {a.relationship}
                            </span>
                            {a.user_detail?.documents_verified && (
                              <span className="rounded-full bg-granted/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-granted">
                                ✓ verified
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-bone-500">No linked users</p>
                    )}
                  </div>

                  {/* Documents */}
                  <div className="mt-4 border-t border-ink-700 pt-3">
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-bone-500">
                      Compliance documents
                    </p>
                    <div className="grid grid-cols-3 gap-2">
                      <DocCard label="Vehicle reg" href={regDoc} />
                      <DocCard label="Driver licence" href={licDoc} />
                      <DocCard label="CNIC / ID" href={cnicDoc} />
                    </div>
                    {!regDoc && !licDoc && !cnicDoc && (
                      <div className="mt-2 flex items-start gap-2 rounded-md border border-amber/30 bg-amber/10 px-2.5 py-1.5 text-xs text-amber">
                        <AlertCircle className="mt-0.5 size-3 shrink-0" />
                        No compliance documents uploaded yet.
                      </div>
                    )}
                  </div>

                  <div className="mt-4 flex gap-2">
                    <Button
                      onClick={() => block(v.id)}
                      variant="ghost"
                      className="flex-1 border-denied/30 text-denied hover:bg-denied/10"
                      size="sm"
                    >
                      <XCircle className="size-3.5" /> Block
                    </Button>
                    <Button
                      onClick={() => approve(v.id)}
                      variant="primary"
                      className="flex-1"
                      size="sm"
                    >
                      <CheckCircle2 className="size-3.5" /> Approve
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </>
  );
}

function DocCard({
  label,
  href,
}: {
  label: string;
  href: string | null;
}) {
  return (
    <a
      href={href || undefined}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'flex flex-col items-start gap-1 rounded-md border p-2 transition-colors',
        href
          ? 'border-ink-600 bg-ink-900/40 text-bone-200 hover:border-amber/40 hover:bg-amber/5'
          : 'cursor-not-allowed border-dashed border-ink-700 bg-ink-900/20 text-bone-600',
      )}
      onClick={(e) => {
        if (!href) e.preventDefault();
      }}
    >
      <FileText className="size-3.5" />
      <span className="text-[11px]">{label}</span>
      <span className="font-mono text-[9px] uppercase tracking-wider">
        {href ? (
          <span className="inline-flex items-center gap-0.5">
            View <ExternalLink className="size-2.5" />
          </span>
        ) : (
          'missing'
        )}
      </span>
    </a>
  );
}
