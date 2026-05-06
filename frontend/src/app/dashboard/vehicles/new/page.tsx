'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Car, Save, Plus, X, Users } from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiGet, apiPost } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Assignment {
  user: number;
  username: string;
  relationship: 'OWNER' | 'DRIVER' | 'BOTH';
}

export default function NewVehiclePage() {
  const router = useRouter();
  const [users, setUsers] = useState<any[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    plate_number: '',
    vehicle_type: 'CAR',
    make: '',
    model: '',
    color: '',
    is_active: true,
  });

  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [pendingUserId, setPendingUserId] = useState('');
  const [pendingRel, setPendingRel] = useState<'OWNER' | 'DRIVER' | 'BOTH'>('DRIVER');

  useEffect(() => {
    apiGet<any>('/auth/users/')
      .then((u) => setUsers(Array.isArray(u) ? u : u.results || []))
      .catch((e) => setError(e.message));
  }, []);

  function addAssignment() {
    if (!pendingUserId) return;
    const id = parseInt(pendingUserId);
    if (assignments.some((a) => a.user === id)) return;
    const u = users.find((x) => x.id === id);
    if (!u) return;
    setAssignments([
      ...assignments,
      { user: id, username: u.username, relationship: pendingRel },
    ]);
    setPendingUserId('');
    setPendingRel('DRIVER');
  }

  function removeAssignment(userId: number) {
    setAssignments(assignments.filter((a) => a.user !== userId));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await apiPost('/vehicles/', {
        ...form,
        assignments: assignments.map((a) => ({
          user: a.user,
          relationship: a.relationship,
        })),
      });
      router.push('/dashboard/vehicles');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  const availableUsers = users.filter(
    (u) => !assignments.some((a) => a.user === u.id),
  );

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Register vehicle
        </p>
        <h1 className="mt-2 flex items-center gap-3 font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
          <Car className="size-7 text-amber" /> New vehicle
        </h1>
      </div>

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
        {/* Vehicle details */}
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <h2 className="mb-4 font-display text-base font-semibold text-bone-50">
            Vehicle details
          </h2>
          <div className="space-y-4">
            <Input
              label="Plate number"
              value={form.plate_number}
              onChange={(e) =>
                setForm({ ...form, plate_number: e.target.value.toUpperCase() })
              }
              required
              placeholder="LEA-1234"
              className="font-mono tracking-widest"
            />
            <Select
              label="Vehicle type"
              value={form.vehicle_type}
              onChange={(e) =>
                setForm({ ...form, vehicle_type: e.target.value })
              }
            >
              <option value="CAR">Car</option>
              <option value="BIKE">Motorcycle</option>
              <option value="SUV">SUV</option>
              <option value="TRUCK">Truck</option>
              <option value="OTHER">Other</option>
            </Select>
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Make"
                value={form.make}
                onChange={(e) => setForm({ ...form, make: e.target.value })}
                placeholder="Toyota"
              />
              <Input
                label="Model"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
                placeholder="Corolla"
              />
            </div>
            <Input
              label="Color"
              value={form.color}
              onChange={(e) => setForm({ ...form, color: e.target.value })}
              placeholder="White"
            />
            <label className="flex cursor-pointer items-center gap-2 text-sm text-bone-300">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) =>
                  setForm({ ...form, is_active: e.target.checked })
                }
                className="size-4 rounded border-ink-600 bg-ink-900 text-amber focus:ring-amber"
              />
              Active (allowed to enter)
            </label>
          </div>
        </section>

        {/* Assignments */}
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <div className="mb-4 flex items-center gap-2">
            <Users className="size-4 text-amber" />
            <h2 className="font-display text-base font-semibold text-bone-50">
              Drivers & owners
            </h2>
          </div>
          <p className="mb-4 text-xs text-bone-400">
            Multiple users can be linked to a vehicle. A user can be an
            OWNER, a DRIVER, or BOTH.
          </p>

          {/* Existing list */}
          {assignments.length > 0 && (
            <ul className="mb-4 space-y-2">
              {assignments.map((a) => (
                <li
                  key={a.user}
                  className="flex items-center justify-between rounded-md border border-ink-700 bg-ink-900/40 px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-bone-200">@{a.username}</span>
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
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
                  <button
                    type="button"
                    onClick={() => removeAssignment(a.user)}
                    className="rounded p-1 text-bone-500 hover:bg-denied/10 hover:text-denied"
                  >
                    <X className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Add row */}
          <div className="grid gap-3 sm:grid-cols-[1fr_120px_auto]">
            <Select
              label="User"
              value={pendingUserId}
              onChange={(e) => setPendingUserId(e.target.value)}
            >
              <option value="">Select user…</option>
              {availableUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.first_name} {u.last_name} (@{u.username})
                </option>
              ))}
            </Select>
            <Select
              label="As"
              value={pendingRel}
              onChange={(e) => setPendingRel(e.target.value as any)}
            >
              <option value="DRIVER">Driver</option>
              <option value="OWNER">Owner</option>
              <option value="BOTH">Both</option>
            </Select>
            <Button
              type="button"
              onClick={addAssignment}
              disabled={!pendingUserId}
              variant="ghost"
              className="self-end"
            >
              <Plus className="size-4" />
            </Button>
          </div>
        </section>

        <div className="lg:col-span-2 flex justify-end gap-3">
          <Button
            type="button"
            variant="ghost"
            onClick={() => router.push('/dashboard/vehicles')}
          >
            Cancel
          </Button>
          <Button type="submit" loading={submitting} size="lg">
            <Save className="size-4" /> Create vehicle
          </Button>
        </div>
      </form>
    </div>
  );
}
