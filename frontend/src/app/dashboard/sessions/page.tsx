'use client';

import { useEffect, useState } from 'react';
import { QRCodeCanvas } from 'qrcode.react';
import {
  Car,
  Clock,
  ParkingCircle,
  QrCode,
  X,
  ArrowDownLeft,
  ArrowUpRight,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { apiGet, apiPost } from '@/lib/api';
import { ParkingSession, fmtDateTime, fmtDuration, cn } from '@/lib/utils';

type FilterState = 'all' | 'PARKED' | 'EXITED';

export default function AdminSessionsPage() {
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterState>('PARKED');
  const [error, setError] = useState('');

  // Pickup-QR modal
  const [qrInfo, setQrInfo] = useState<{
    deep_link: string;
    token: string;
    plate: string;
    expires_at: string;
  } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const params = filter === 'all' ? '' : `?status=${filter}`;
      const data = await apiGet<any>(`/parking/sessions/${params}`);
      setSessions(Array.isArray(data) ? data : data.results || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [filter]);

  async function generatePickupQR(session: ParkingSession) {
    try {
      const res = await apiPost<any>('/passkeys/pickup-tokens/', {
        vehicle_id: session.vehicle,
      });
      setQrInfo({
        deep_link: res.deep_link,
        token: res.token,
        plate: session.vehicle_detail.plate_number,
        expires_at: res.expires_at,
      });
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
            · Parking sessions
          </p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
            Sessions
          </h1>
          <p className="mt-2 text-sm text-bone-400">
            Currently parked vehicles and full entry/exit history.
          </p>
        </div>
        <Button onClick={load} variant="ghost" size="sm">
          <RefreshCw className="size-3.5" /> Refresh
        </Button>
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {(['PARKED', 'EXITED', 'all'] as FilterState[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'rounded-md border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors',
              filter === f
                ? 'border-amber bg-amber/10 text-amber'
                : 'border-ink-600 bg-ink-800/40 text-bone-500 hover:text-bone-300',
            )}
          >
            {f === 'all' ? 'All' : f === 'PARKED' ? 'Parked now' : 'History'}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
          Loading sessions…
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-12 text-center">
          <ParkingCircle className="mx-auto size-10 text-bone-500" />
          <p className="mt-3 text-bone-300">
            {filter === 'PARKED'
              ? 'No vehicles currently parked.'
              : 'No sessions yet.'}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-ink-700">
          <table className="w-full">
            <thead className="bg-ink-800/60 font-mono text-[10px] uppercase tracking-wider text-bone-500">
              <tr>
                <th className="p-3 text-left">Vehicle</th>
                <th className="p-3 text-left">Status</th>
                <th className="p-3 text-left">Entered</th>
                <th className="p-3 text-left">Exited</th>
                <th className="p-3 text-left">Duration</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr
                  key={s.id}
                  className="border-t border-ink-700 hover:bg-ink-800/30"
                >
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <Car className="size-4 text-bone-500" />
                      <div>
                        <p className="font-mono text-sm font-semibold tracking-wider text-bone-50">
                          {s.vehicle_detail.plate_number}
                        </p>
                        <p className="text-[11px] text-bone-500">
                          {s.vehicle_detail.make} {s.vehicle_detail.model}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="p-3">
                    {s.status === 'PARKED' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber">
                        <ParkingCircle className="size-3" /> Parked
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-ink-600 bg-ink-900 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                        Exited
                      </span>
                    )}
                  </td>
                  <td className="p-3 font-mono text-[11px] tabular-nums text-bone-300">
                    <ArrowDownLeft className="mr-1 inline size-3 text-granted" />
                    {fmtDateTime(s.entry_time)}
                  </td>
                  <td className="p-3 font-mono text-[11px] tabular-nums text-bone-300">
                    {s.exit_time ? (
                      <>
                        <ArrowUpRight className="mr-1 inline size-3 text-denied" />
                        {fmtDateTime(s.exit_time)}
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="p-3 font-mono text-[11px] text-bone-300">
                    {fmtDuration(s.duration_seconds) ||
                      (s.status === 'PARKED' ? 'ongoing…' : '—')}
                  </td>
                  <td className="p-3 text-right">
                    {s.status === 'PARKED' && (
                      <Button
                        onClick={() => generatePickupQR(s)}
                        variant="ghost"
                        size="sm"
                      >
                        <QrCode className="size-3.5" /> Pickup QR
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* QR Modal */}
      {qrInfo && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-lg border border-ink-700 bg-ink-900 p-6">
            <button
              onClick={() => setQrInfo(null)}
              className="absolute right-3 top-3 rounded-md p-1.5 text-bone-500 hover:bg-ink-800 hover:text-bone-200"
            >
              <X className="size-4" />
            </button>

            <div className="text-center">
              <p className="font-mono text-[10px] uppercase tracking-widest text-amber">
                · Pickup QR for
              </p>
              <p className="mt-1 font-mono text-xl font-semibold tracking-wider text-bone-50">
                {qrInfo.plate}
              </p>
            </div>

            <div className="mt-5 grid place-items-center rounded-lg bg-bone-50 p-6">
              <QRCodeCanvas
                value={qrInfo.deep_link}
                size={220}
                level="M"
                includeMargin={false}
              />
            </div>

            <div className="mt-4 space-y-2 text-center">
              <p className="text-sm text-bone-300">
                Driver scans this QR with their phone camera.
              </p>
              <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
                Expires{' '}
                {new Date(qrInfo.expires_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>

            <div className="mt-4 break-all rounded border border-ink-700 bg-ink-800/40 p-3 font-mono text-[10px] text-bone-400">
              {qrInfo.deep_link}
            </div>

            <Button
              onClick={() => setQrInfo(null)}
              variant="ghost"
              className="mt-4 w-full"
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
