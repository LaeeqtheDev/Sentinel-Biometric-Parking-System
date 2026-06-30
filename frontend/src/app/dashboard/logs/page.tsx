'use client';

import { useEffect, useState } from 'react';
import { Search, ScrollText, Image as ImageIcon } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Input } from '@/components/Input';
import { StatusBadge } from '@/components/StatusBadge';
import { apiGet } from '@/lib/api';
import { AccessLog, PaginatedResponse, fmtDateTime, cn } from '@/lib/utils';

const MEDIA_URL =
  process.env.NEXT_PUBLIC_MEDIA_URL || 'http://localhost:8000';

export default function LogsPage() {
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'ALL' | 'GRANTED' | 'DENIED'>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<AccessLog | null>(null);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('plate', search);
      if (filter !== 'ALL') params.set('status', filter);
      const res = await apiGet<PaginatedResponse<AccessLog>>(
        `/access/logs/?${params.toString()}`,
      );
      setLogs(res.results);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, filter]);

  return (
    <>
      <Topbar
        title="Access Logs"
        subtitle="Every entry attempt — filterable and exportable."
      />

      <main className="flex-1 p-6 lg:p-8">
        {/* Filters */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative max-w-xs flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-bone-500" />
            <Input
              placeholder="Filter by plate…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex rounded-md border border-ink-600 bg-ink-800/40 p-0.5">
            {(['ALL', 'GRANTED', 'DENIED'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  'rounded px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors',
                  filter === f
                    ? f === 'GRANTED'
                      ? 'bg-granted text-ink-950'
                      : f === 'DENIED'
                        ? 'bg-denied text-ink-950'
                        : 'bg-amber text-ink-950'
                    : 'text-bone-400 hover:text-bone-200',
                )}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-denied/30 bg-denied/10 px-4 py-3 text-sm text-denied">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          {/* Table */}
          <div
            className={cn(
              'overflow-hidden rounded-lg border border-ink-600 bg-ink-800/40',
              selected ? 'lg:col-span-3' : 'lg:col-span-5',
            )}
          >
            <table className="w-full">
              <thead>
                <tr className="border-b border-ink-700 bg-ink-900/40 text-left">
                  <Th>Timestamp</Th>
                  <Th>Plate</Th>
                  <Th>Gate</Th>
                  <Th>User</Th>
                  <Th>Plate ✓</Th>
                  <Th>Bio ✓</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-sm text-bone-500">
                      Loading…
                    </td>
                  </tr>
                )}
                {!loading && logs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-16 text-center">
                      <div className="flex flex-col items-center gap-3 text-bone-500">
                        <ScrollText className="size-8 opacity-50" />
                        <p className="text-sm">No log entries match.</p>
                      </div>
                    </td>
                  </tr>
                )}
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelected(log)}
                    className={cn(
                      'cursor-pointer border-b border-ink-700 transition-colors last:border-0 hover:bg-ink-700/20',
                      selected?.id === log.id && 'bg-amber/5',
                    )}
                  >
                    <Td>
                      <span className="font-mono text-[11px] tabular-nums text-bone-300">
                        {fmtDateTime(log.timestamp)}
                      </span>
                    </Td>
                    <Td>
                      <span className="rounded border border-ink-600 bg-ink-900 px-2 py-0.5 font-mono text-xs font-semibold tracking-wider text-bone-100">
                        {log.plate_detected}
                      </span>
                    </Td>
                    <Td>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
                        {(log as any).gate || '—'}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-sm text-bone-300">
                        {log.user_detail?.username || '—'}
                      </span>
                    </Td>
                    <Td>
                      <CheckIndicator on={log.plate_match} />
                    </Td>
                    <Td>
                      <CheckIndicator on={log.biometric_match} />
                    </Td>
                    <Td>
                      <StatusBadge status={log.status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Detail panel */}
          {selected && (
            <aside className="space-y-4 lg:col-span-2">
              <div className="overflow-hidden rounded-lg border border-ink-600 bg-ink-800/40">
                {selected.snapshot ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={
                      selected.snapshot.startsWith('http')
                        ? selected.snapshot
                        : `${MEDIA_URL}${selected.snapshot}`
                    }
                    alt="Snapshot"
                    className="aspect-video w-full object-cover"
                    onError={(e) => {
                      // Hide broken image and show fallback
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="grid aspect-video place-items-center bg-ink-900/60 text-bone-500">
                    <div className="flex flex-col items-center gap-2">
                      <ImageIcon className="size-8 opacity-50" />
                      <span className="text-xs">No snapshot</span>
                    </div>
                  </div>
                )}

                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
                      Log #{selected.id}
                    </p>
                    <StatusBadge status={selected.status} />
                  </div>
                  <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50">
                    {selected.plate_detected}
                  </h2>
                  <p className="mt-2 text-sm text-bone-400">{selected.reason}</p>

                  <dl className="mt-5 space-y-2.5 border-t border-ink-700 pt-4">
                    <KV
                      k="Timestamp"
                      v={
                        <span className="font-mono text-xs">
                          {fmtDateTime(selected.timestamp)}
                        </span>
                      }
                    />
                    <KV
                      k="Plate match"
                      v={selected.plate_match ? 'Yes' : 'No'}
                    />
                    <KV
                      k="Biometric match"
                      v={selected.biometric_match ? 'Yes' : 'No'}
                    />
                    {selected.biometric_distance !== null && (
                      <KV
                        k="Bio distance"
                        v={
                          <span className="font-mono">
                            {selected.biometric_distance.toFixed(4)}
                          </span>
                        }
                      />
                    )}
                    {selected.user_detail && (
                      <KV
                        k="User"
                        v={`${selected.user_detail.first_name || ''} ${
                          selected.user_detail.last_name || ''
                        } (@${selected.user_detail.username})`}
                      />
                    )}
                    {selected.vehicle_detail && (
                      <KV
                        k="Vehicle"
                        v={`${selected.vehicle_detail.make || ''} ${
                          selected.vehicle_detail.model || ''
                        }`}
                      />
                    )}
                  </dl>
                </div>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="w-full rounded-md border border-ink-700 py-2 text-xs uppercase tracking-wider text-bone-500 transition-colors hover:border-ink-600 hover:text-bone-300"
              >
                Close detail
              </button>
            </aside>
          )}
        </div>
      </main>
    </>
  );
}

function CheckIndicator({ on }: { on: boolean }) {
  return (
    <span
      className={cn(
        'inline-block size-2 rounded-full',
        on
          ? 'bg-granted shadow-[0_0_6px_rgba(52,211,153,0.7)]'
          : 'bg-denied/50',
      )}
    />
  );
}

function Th({ children, className = '' }: any) {
  return (
    <th className={`px-5 py-3 font-mono text-[10px] font-medium uppercase tracking-widest text-bone-500 ${className}`}>
      {children}
    </th>
  );
}
function Td({ children, className = '' }: any) {
  return <td className={`px-5 py-4 ${className}`}>{children}</td>;
}
function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <dt className="text-xs uppercase tracking-wider text-bone-500">{k}</dt>
      <dd className="text-bone-200">{v}</dd>
    </div>
  );
}
