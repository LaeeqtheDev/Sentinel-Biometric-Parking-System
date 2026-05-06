'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Car,
  Users,
  Plus,
  Trash2,
  ArrowLeft,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Select } from '@/components/Select';
import { apiGet, apiPost, apiDelete } from '@/lib/api';
import { Vehicle, UserVehicleAssignment, cn } from '@/lib/utils';

export default function AssignmentsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const vehicleId = params.id;

  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<UserVehicleAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  // form state
  const [newUserId, setNewUserId] = useState('');
  const [newRel, setNewRel] = useState<'OWNER' | 'DRIVER' | 'BOTH'>('DRIVER');

  async function load() {
    setLoading(true);
    try {
      const [v, a, u] = await Promise.all([
        apiGet<Vehicle>(`/vehicles/${vehicleId}/`),
        apiGet<UserVehicleAssignment[]>(`/vehicles/${vehicleId}/assignments/`),
        apiGet<any>(`/auth/users/`),
      ]);
      setVehicle(v);
      setAssignments(a);
      setUsers(Array.isArray(u) ? u : u.results || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [vehicleId]);

  async function add() {
    if (!newUserId) return;
    setAdding(true);
    setError('');
    try {
      await apiPost(`/vehicles/${vehicleId}/assignments/`, {
        user: parseInt(newUserId),
        relationship: newRel,
      });
      setNewUserId('');
      setNewRel('DRIVER');
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function remove(aid: number) {
    if (!confirm('Remove this assignment?')) return;
    try {
      await apiDelete(`/vehicles/${vehicleId}/assignments/${aid}/`);
      setAssignments((a) => a.filter((x) => x.id !== aid));
    } catch (e: any) {
      setError(e.message);
    }
  }

  // users not yet assigned
  const availableUsers = users.filter(
    (u) => !assignments.some((a) => a.user === u.id),
  );

  return (
    <div className="space-y-6">
      <button
        onClick={() => router.back()}
        className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-bone-500 hover:text-bone-300"
      >
        <ArrowLeft className="size-3" /> Back
      </button>

      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Vehicle assignments
        </p>
        <h1 className="mt-2 flex items-center gap-3 font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
          <Car className="size-7 text-amber" />
          {vehicle?.plate_number || '…'}
        </h1>
        {vehicle && (
          <p className="mt-1 text-sm text-bone-400">
            {vehicle.make} {vehicle.model} · {vehicle.vehicle_type}
          </p>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}

      {/* Current assignments */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <Users className="size-4 text-amber" />
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-bone-500">
            Current users ({assignments.length})
          </h2>
        </div>

        {loading ? (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
            Loading…
          </div>
        ) : assignments.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-6 text-center text-sm text-bone-500">
            No users assigned to this vehicle yet.
          </div>
        ) : (
          <ul className="space-y-2">
            {assignments.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-800/40 p-4"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'grid size-10 place-items-center rounded-md border',
                      a.relationship === 'OWNER'
                        ? 'border-amber/40 bg-amber/10 text-amber'
                        : a.relationship === 'BOTH'
                        ? 'border-granted/40 bg-granted/10 text-granted'
                        : 'border-ink-600 bg-ink-900 text-bone-400',
                    )}
                  >
                    {a.relationship === 'OWNER' ? (
                      <ShieldCheck className="size-4" />
                    ) : (
                      <Users className="size-4" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-bone-100">
                      {a.user_detail?.first_name}{' '}
                      {a.user_detail?.last_name}{' '}
                      <span className="text-bone-500">
                        @{a.user_detail?.username}
                      </span>
                    </p>
                    <span
                      className={cn(
                        'inline-block mt-0.5 rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
                        a.relationship === 'OWNER'
                          ? 'bg-amber/10 text-amber'
                          : a.relationship === 'BOTH'
                          ? 'bg-granted/10 text-granted'
                          : 'bg-ink-700 text-bone-400',
                      )}
                    >
                      {a.relationship}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => remove(a.id)}
                  className="rounded-md p-2 text-bone-500 hover:bg-denied/10 hover:text-denied"
                  title="Remove"
                >
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Add new */}
      <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Plus className="size-4 text-amber" />
          <h2 className="font-display text-base font-semibold text-bone-50">
            Add user
          </h2>
        </div>

        {availableUsers.length === 0 ? (
          <p className="text-sm text-bone-500">
            All users are already assigned. Create a new user first.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-[1fr_180px_auto]">
            <Select
              label="User"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
            >
              <option value="">Select user…</option>
              {availableUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.first_name} {u.last_name} (@{u.username})
                </option>
              ))}
            </Select>
            <Select
              label="Relationship"
              value={newRel}
              onChange={(e) => setNewRel(e.target.value as any)}
            >
              <option value="DRIVER">Driver</option>
              <option value="OWNER">Owner</option>
              <option value="BOTH">Owner & Driver</option>
            </Select>
            <Button
              onClick={add}
              loading={adding}
              disabled={!newUserId}
              className="self-end"
            >
              <Plus className="size-4" /> Add
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
