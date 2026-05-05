'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Car } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiGet, apiPost } from '@/lib/api';
import { PaginatedResponse } from '@/lib/utils';

interface Driver {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
}

export default function NewVehiclePage() {
  const router = useRouter();
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [form, setForm] = useState({
    owner: '',
    plate_number: '',
    vehicle_type: 'CAR',
    make: '',
    model: '',
    color: '',
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    apiGet<PaginatedResponse<Driver>>('/auth/users/?role=DRIVER')
      .then((res) => setDrivers(res.results))
      .catch((e) => setError(e.message));
  }, []);

  function update<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await apiPost('/vehicles/', {
        ...form,
        owner: Number(form.owner),
      });
      router.push('/dashboard/vehicles');
    } catch (e: any) {
      const data = e.data;
      if (data && typeof data === 'object') {
        const first = Object.entries(data)[0];
        if (first) {
          setError(`${first[0]}: ${(first[1] as any)?.[0] ?? first[1]}`);
        } else {
          setError(e.message);
        }
      } else {
        setError(e.message || 'Failed to create vehicle');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Topbar
        title="Register Vehicle"
        subtitle="Link a license plate to a registered driver."
      />

      <main className="flex-1 p-6 lg:p-8">
        <Link
          href="/dashboard/vehicles"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-bone-500 transition-colors hover:text-bone-300"
        >
          <ArrowLeft className="size-3.5" /> Back to vehicles
        </Link>

        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
              <div className="mb-3 grid size-10 place-items-center rounded-md bg-amber/10 text-amber">
                <Car className="size-5" />
              </div>
              <h2 className="font-display text-lg font-semibold text-bone-50">
                New vehicle
              </h2>
              <p className="mt-2 text-sm text-bone-400">
                The plate number will be normalised (uppercase, no spaces) and
                must be unique across the system.
              </p>
              <ul className="mt-5 space-y-2 text-xs text-bone-500">
                <li>· Driver must already be registered as a user</li>
                <li>· Plate is the lookup key during entry</li>
                <li>· Inactive vehicles are denied access</li>
              </ul>
            </div>
          </div>

          <form
            onSubmit={submit}
            className="space-y-5 rounded-lg border border-ink-600 bg-ink-800/40 p-6 lg:col-span-2"
          >
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <Select
                label="Owner (Driver) *"
                value={form.owner}
                onChange={(e) => update('owner', e.target.value)}
                required
              >
                <option value="">Select driver…</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.first_name || d.username} {d.last_name} (@{d.username})
                  </option>
                ))}
              </Select>

              <Input
                label="Plate Number *"
                value={form.plate_number}
                onChange={(e) =>
                  update('plate_number', e.target.value.toUpperCase())
                }
                placeholder="LEA-1234"
                required
              />

              <Select
                label="Vehicle Type *"
                value={form.vehicle_type}
                onChange={(e) => update('vehicle_type', e.target.value)}
              >
                <option value="CAR">Car</option>
                <option value="BIKE">Motorcycle</option>
                <option value="SUV">SUV</option>
                <option value="TRUCK">Truck</option>
                <option value="OTHER">Other</option>
              </Select>

              <Input
                label="Color"
                value={form.color}
                onChange={(e) => update('color', e.target.value)}
                placeholder="e.g. Silver"
              />

              <Input
                label="Make"
                value={form.make}
                onChange={(e) => update('make', e.target.value)}
                placeholder="Toyota"
              />

              <Input
                label="Model"
                value={form.model}
                onChange={(e) => update('model', e.target.value)}
                placeholder="Corolla"
              />
            </div>

            <label className="flex cursor-pointer items-center gap-2 text-sm text-bone-300">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => update('is_active', e.target.checked)}
                className="size-4 accent-amber"
              />
              Active (vehicle can request entry)
            </label>

            {error && (
              <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
                {error}
              </div>
            )}

            <div className="flex justify-end gap-3 border-t border-ink-700 pt-5">
              <Link href="/dashboard/vehicles">
                <Button type="button" variant="ghost">
                  Cancel
                </Button>
              </Link>
              <Button type="submit" loading={submitting}>
                Register vehicle
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}
