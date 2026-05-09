'use client';

import { useEffect, useState } from 'react';
import {
  Car,
  Plus,
  Trash2,
  Clock,
  CheckCircle2,
  AlertCircle,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiGet, apiPost, apiDelete, tokenStore } from '@/lib/api';
import { Vehicle, cn } from '@/lib/utils';

export default function DriverVehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState({
    plate_number: '',
    make: '',
    model: '',
    color: '',
    vehicle_type: 'CAR',
  });
  const [regDoc, setRegDoc] = useState<File | null>(null);

  async function load() {
    setLoading(true);
    try {
      const v = await apiGet<Vehicle[]>('/vehicles/my/');
      setVehicles(v);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add() {
    if (!form.plate_number.trim()) return;
    setAdding(true);
    setError('');
    setSuccess('');
    try {
      // Use FormData if a doc is attached so we can multipart-upload
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      const token = tokenStore.getAccess();
      let res: Response;
      if (regDoc) {
        const fd = new FormData();
        fd.append('plate_number', form.plate_number.trim());
        fd.append('make', form.make);
        fd.append('model', form.model);
        fd.append('color', form.color);
        fd.append('vehicle_type', form.vehicle_type);
        fd.append('registration_doc', regDoc);
        res = await fetch(`${API_URL}/vehicles/my/add/`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: fd,
        });
      } else {
        res = await fetch(`${API_URL}/vehicles/my/add/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            plate_number: form.plate_number.trim(),
            make: form.make,
            model: form.model,
            color: form.color,
            vehicle_type: form.vehicle_type,
          }),
        });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Add failed');
      setSuccess(data.message || 'Vehicle added.');
      setForm({
        plate_number: '',
        make: '',
        model: '',
        color: '',
        vehicle_type: 'CAR',
      });
      setRegDoc(null);
      setShowForm(false);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: number) {
    if (!confirm('Remove this vehicle from your account?')) return;
    try {
      await apiDelete(`/vehicles/my/${id}/`);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · My garage
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          My vehicles
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          Add, view, or remove vehicles linked to your account. New vehicles
          start as <strong>under review</strong> until an admin approves them.
        </p>
      </div>

      {/* Explanation banner — what under-review actually means */}
      {vehicles.some((v) => v.status === 'UNDER_REVIEW') && (
        <div className="rounded-lg border border-amber/30 bg-amber/5 p-4 text-sm text-bone-300">
          <p className="font-medium text-amber">⏳ Pending review</p>
          <p className="mt-1 text-xs text-bone-400">
            Your vehicle is in the parking system administrator's queue. They
            verify your driver licence + vehicle registration, then mark it
            ACTIVE. To speed this up:{' '}
            <a
              href="/driver/documents"
              className="text-amber hover:underline"
            >
              upload your documents
            </a>
            .
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-granted/30 bg-granted/10 px-3 py-2 text-sm text-granted">
          {success}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
          Loading…
        </div>
      ) : vehicles.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-8 text-center">
          <Car className="mx-auto size-10 text-bone-500" />
          <p className="mt-3 text-bone-300">No vehicles yet</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {vehicles.map((v) => (
            <li
              key={v.id}
              className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-800/40 p-4"
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    'grid size-10 place-items-center rounded-md border',
                    v.status === 'ACTIVE'
                      ? 'border-granted/40 bg-granted/10 text-granted'
                      : v.status === 'BLOCKED'
                      ? 'border-denied/40 bg-denied/10 text-denied'
                      : 'border-amber/40 bg-amber/10 text-amber',
                  )}
                >
                  <Car className="size-4" />
                </div>
                <div>
                  <p className="font-mono text-base font-semibold tracking-wider text-bone-50">
                    {v.plate_number}
                  </p>
                  <p className="text-xs text-bone-500">
                    {v.make} {v.model} · {v.vehicle_type}
                  </p>
                  <StatusBadge status={v.status} />
                </div>
              </div>
              <button
                onClick={() => remove(v.id)}
                className="rounded-md p-2 text-bone-500 hover:bg-denied/10 hover:text-denied"
                title="Remove"
              >
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {showForm ? (
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <h3 className="mb-4 font-display text-base font-semibold text-bone-50">
            Add a vehicle
          </h3>
          <div className="space-y-3">
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
              label="Type"
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
            <div className="grid grid-cols-2 gap-2.5">
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
            <div>
              <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-bone-500">
                Vehicle registration document (optional)
              </label>
              <div
                className={cn(
                  'relative flex cursor-pointer items-center gap-3 rounded-md border bg-ink-900/40 p-3 transition-colors hover:border-amber/40',
                  regDoc ? 'border-amber/40' : 'border-dashed border-ink-700',
                )}
              >
                <input
                  type="file"
                  accept="image/*,application/pdf"
                  onChange={(e) => setRegDoc(e.target.files?.[0] || null)}
                  className="absolute inset-0 cursor-pointer opacity-0"
                />
                <Plus
                  className={cn(
                    'size-4',
                    regDoc ? 'text-amber' : 'text-bone-500',
                  )}
                />
                <span className="truncate text-sm text-bone-200">
                  {regDoc ? regDoc.name : 'Attach a copy (speeds up approval)'}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <Button
              onClick={() => setShowForm(false)}
              variant="ghost"
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={add}
              loading={adding}
              disabled={!form.plate_number.trim()}
              className="flex-1"
            >
              <Plus className="size-4" /> Add
            </Button>
          </div>
        </section>
      ) : (
        <Button onClick={() => setShowForm(true)} className="w-full" size="lg">
          <Plus className="size-4" /> Add a vehicle
        </Button>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    ACTIVE: { icon: CheckCircle2, color: 'granted', label: 'Active' },
    BLOCKED: { icon: XCircle, color: 'denied', label: 'Blocked' },
    UNDER_REVIEW: { icon: Clock, color: 'amber', label: 'Under review' },
  } as const;
  const c = config[status as keyof typeof config] || config.UNDER_REVIEW;
  const Icon = c.icon;
  return (
    <span
      className={cn(
        'mt-1 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider',
        c.color === 'granted' && 'bg-granted/10 text-granted',
        c.color === 'denied' && 'bg-denied/10 text-denied',
        c.color === 'amber' && 'bg-amber/10 text-amber',
      )}
    >
      <Icon className="size-2.5" /> {c.label}
    </span>
  );
}
