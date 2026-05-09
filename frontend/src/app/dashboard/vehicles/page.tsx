'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Search, Car, Trash2, Users } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { apiGet, apiDelete } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Vehicle, PaginatedResponse, fmtDateTime } from '@/lib/utils';

export default function VehiclesPage() {
  const { user } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load(q: string = '') {
    setLoading(true);
    try {
      const res = await apiGet<PaginatedResponse<Vehicle>>(
        `/vehicles/?search=${encodeURIComponent(q)}`,
      );
      setVehicles(res.results);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (user?.role === 'ADMIN') load();
  }, [user]);

  useEffect(() => {
    if (user?.role !== 'ADMIN') return;
    const t = setTimeout(() => load(search), 300);
    return () => clearTimeout(t);
  }, [search, user]);

  async function remove(id: number) {
    if (!confirm('Delete this vehicle? This cannot be undone.')) return;
    try {
      await apiDelete(`/vehicles/${id}/`);
      setVehicles((v) => v.filter((x) => x.id !== id));
    } catch (e: any) {
      alert(e.message);
    }
  }

  return (
    <>
      <Topbar
        title="Vehicles"
        subtitle="Registered vehicles authorised for parking access."
      />

      <main className="flex-1 p-6 lg:p-8">
        {/* Toolbar */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-xs flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-bone-500" />
            <Input
              placeholder="Search by plate number…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Link href="/dashboard/vehicles/new">
            <Button>
              <Plus className="size-4" />
              Register vehicle
            </Button>
          </Link>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-denied/30 bg-denied/10 px-4 py-3 text-sm text-denied">
            {error}
          </div>
        )}

        {/* Table */}
        <div className="overflow-hidden rounded-lg border border-ink-600 bg-ink-800/40">
          <table className="w-full">
            <thead>
              <tr className="border-b border-ink-700 bg-ink-900/40 text-left">
                <Th>Plate</Th>
                <Th>Type</Th>
                <Th>Drivers / Owners</Th>
                <Th>Make / Model</Th>
                <Th>Status</Th>
                <Th>Registered</Th>
                <Th className="text-right pr-5">Actions</Th>
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
              {!loading && vehicles.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-16 text-center">
                    <div className="flex flex-col items-center gap-3 text-bone-500">
                      <Car className="size-8 opacity-50" />
                      <p className="text-sm">No vehicles yet.</p>
                      <Link href="/dashboard/vehicles/new">
                        <Button variant="secondary" size="sm">
                          Register the first vehicle
                        </Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              )}
              {vehicles.map((v) => (
                <tr
                  key={v.id}
                  className="border-b border-ink-700 transition-colors last:border-0 hover:bg-ink-700/20"
                >
                  <Td>
                    <span className="rounded border border-ink-600 bg-ink-900 px-2 py-0.5 font-mono text-xs font-semibold tracking-wider text-bone-100">
                      {v.plate_number}
                    </span>
                  </Td>
                  <Td>
                    <span className="font-mono text-[11px] uppercase tracking-wider text-bone-400">
                      {v.vehicle_type}
                    </span>
                  </Td>
                  <Td>
                    {v.assignments && v.assignments.length > 0 ? (
                      <div className="space-y-0.5">
                        {v.assignments.slice(0, 2).map((a) => (
                          <div key={a.id} className="text-sm text-bone-200">
                            @{a.user_detail?.username}
                            <span
                              className={`ml-1.5 rounded px-1 py-0.5 font-mono text-[9px] uppercase tracking-wider ${
                                a.relationship === 'OWNER'
                                  ? 'bg-amber/10 text-amber'
                                  : a.relationship === 'BOTH'
                                  ? 'bg-granted/10 text-granted'
                                  : 'bg-ink-700 text-bone-400'
                              }`}
                            >
                              {a.relationship}
                            </span>
                          </div>
                        ))}
                        {v.assignments.length > 2 && (
                          <p className="text-[11px] text-bone-500">
                            +{v.assignments.length - 2} more
                          </p>
                        )}
                      </div>
                    ) : (
                      <span className="text-[11px] text-bone-500">
                        Unassigned
                      </span>
                    )}
                  </Td>
                  <Td>
                    <span className="text-sm text-bone-200">
                      {v.make || '—'} {v.model}
                      {v.color && (
                        <span className="block text-[11px] text-bone-500">
                          {v.color}
                        </span>
                      )}
                    </span>
                  </Td>
                  <Td>
                    {v.is_active ? (
                      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-granted">
                        <span className="size-1.5 rounded-full bg-granted animate-pulse-soft" />
                        Active
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
                        Inactive
                      </span>
                    )}
                  </Td>
                  <Td>
                    <span className="font-mono text-[11px] tabular-nums text-bone-400">
                      {fmtDateTime(v.created_at)}
                    </span>
                  </Td>
                  <Td className="pr-5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Link
                        href={`/dashboard/vehicles/${v.id}/assignments`}
                        className="rounded-md p-1.5 text-bone-500 transition-colors hover:bg-amber/10 hover:text-amber"
                        title="Manage drivers/owners"
                      >
                        <Users className="size-4" />
                      </Link>
                      <button
                        onClick={() => remove(v.id)}
                        className="rounded-md p-1.5 text-bone-500 transition-colors hover:bg-denied/10 hover:text-denied"
                        title="Delete"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}

function Th({ children, className = '' }: any) {
  return (
    <th
      className={`px-5 py-3 font-mono text-[10px] font-medium uppercase tracking-widest text-bone-500 ${className}`}
    >
      {children}
    </th>
  );
}

function Td({ children, className = '' }: any) {
  return <td className={`px-5 py-4 ${className}`}>{children}</td>;
}
