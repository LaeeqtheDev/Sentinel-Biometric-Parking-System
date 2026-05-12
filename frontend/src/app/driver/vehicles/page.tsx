'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Car, Plus, Trash2, Clock, CheckCircle2,
  XCircle, Upload, FileText, Users,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiGet, apiPost, apiDelete, tokenStore } from '@/lib/api';
import { Vehicle, cn } from '@/lib/utils';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function DriverVehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState({
    plate_number: '', make: '', model: '', color: '', vehicle_type: 'CAR',
  });
  const [regDoc, setRegDoc] = useState<File | null>(null);

  // Assign extra driver to a vehicle
  const [assigningFor, setAssigningFor] = useState<Vehicle | null>(null);
  const [assignUsername, setAssignUsername] = useState('');
  const [assigning, setAssigning] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const v = await apiGet<Vehicle[]>('/vehicles/my/');
      setVehicles(v);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function add() {
    if (!form.plate_number.trim()) return;
    setAdding(true); setError(''); setSuccess('');
    try {
      const token = tokenStore.getAccess();
      let res: Response;
      if (regDoc) {
        const fd = new FormData();
        Object.entries(form).forEach(([k, v]) => fd.append(k, v));
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
          body: JSON.stringify(form),
        });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Add failed');
      setSuccess(data.message || 'Vehicle added — pending approval.');
      setForm({ plate_number: '', make: '', model: '', color: '', vehicle_type: 'CAR' });
      setRegDoc(null);
      setShowForm(false);
      load();
    } catch (e: any) { setError(e.message); }
    finally { setAdding(false); }
  }

  async function remove(id: number) {
    if (!confirm('Remove this vehicle from your account?')) return;
    try {
      await apiDelete(`/vehicles/my/${id}/`);
      load();
    } catch (e: any) { setError(e.message); }
  }

  async function assignDriver() {
    if (!assigningFor || !assignUsername.trim()) return;
    setAssigning(true);
    try {
      // Look up user then create assignment via admin endpoint
      // We use walk-up endpoint with existing vehicle + driver_id lookup by username
      const users = await apiGet<any[]>(`/auth/users/?search=${assignUsername.trim()}`);
      const match = users.find((u: any) => u.username === assignUsername.trim());
      if (!match) throw new Error(`User "${assignUsername}" not found.`);
      await apiPost(`/vehicles/${assigningFor.id}/assignments/`, {
        user_id: match.id,
        relationship: 'DRIVER',
      });
      setSuccess(`@${assignUsername} added as driver.`);
      setAssigningFor(null);
      setAssignUsername('');
      load();
    } catch (e: any) { setError(e.message); }
    finally { setAssigning(false); }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">· My garage</p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50">
          My vehicles
        </h1>
      </div>

      {vehicles.some((v) => v.status === 'UNDER_REVIEW') && (
        <div className="rounded-lg border border-amber/30 bg-amber/5 p-4 text-sm text-bone-300">
          <p className="font-medium text-amber">⏳ Pending review</p>
          <p className="mt-1 text-xs text-bone-400">
            Your vehicle is in the admin queue.{' '}
            <a href="/driver/documents" className="text-amber hover:underline">
              Upload your documents
            </a>{' '}
            to speed up approval.
          </p>
        </div>
      )}

      {error && <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">{error}</div>}
      {success && <div className="rounded-md border border-granted/30 bg-granted/10 px-3 py-2 text-sm text-granted">{success}</div>}

      {loading ? (
        <div className="p-6 text-center text-bone-500">Loading…</div>
      ) : vehicles.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-ink-700 p-8 text-center">
          <Car className="mx-auto size-10 text-bone-500" />
          <p className="mt-3 text-bone-300">No vehicles yet</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {vehicles.map((v) => (
            <li key={v.id} className="rounded-lg border border-ink-700 bg-ink-800/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    'grid size-10 place-items-center rounded-md',
                    v.status === 'ACTIVE' ? 'bg-granted/10 text-granted'
                    : v.status === 'BLOCKED' ? 'bg-denied/10 text-denied'
                    : 'bg-amber/10 text-amber',
                  )}>
                    <Car className="size-4" />
                  </div>
                  <div>
                    <p className="font-mono text-sm font-semibold tracking-wider text-bone-50">
                      {v.plate_number}
                    </p>
                    <p className="text-[11px] text-bone-500">
                      {v.make} {v.model} ·{' '}
                      <span className={cn(
                        v.status === 'ACTIVE' ? 'text-granted'
                        : v.status === 'BLOCKED' ? 'text-denied' : 'text-amber',
                      )}>
                        {v.status.toLowerCase().replace('_', ' ')}
                      </span>
                    </p>
                    {/* Linked users */}
                    {v.assignments && v.assignments.length > 0 && (
                      <p className="mt-1 font-mono text-[10px] text-bone-500">
                        {v.assignments.length} linked user{v.assignments.length > 1 ? 's' : ''}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => { setAssigningFor(v); setAssignUsername(''); }}
                    className="rounded-md p-1.5 text-bone-500 hover:bg-ink-700 hover:text-amber"
                    title="Add driver"
                  >
                    <Users className="size-4" />
                  </button>
                  <button
                    onClick={() => remove(v.id)}
                    className="rounded-md p-1.5 text-bone-500 hover:bg-denied/10 hover:text-denied"
                    title="Remove"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Add vehicle form */}
      {showForm ? (
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5 space-y-3">
          <h3 className="font-display text-base font-semibold text-bone-50">Add a vehicle</h3>
          <Input
            label="Plate number *"
            value={form.plate_number}
            onChange={(e) => setForm({ ...form, plate_number: e.target.value.toUpperCase() })}
            placeholder="AAP-1478"
            className="font-mono tracking-widest"
          />
          <Select
            label="Type"
            value={form.vehicle_type}
            onChange={(e) => setForm({ ...form, vehicle_type: e.target.value })}
          >
            <option value="CAR">Car</option>
            <option value="BIKE">Motorcycle</option>
            <option value="SUV">SUV</option>
            <option value="TRUCK">Truck</option>
            <option value="OTHER">Other</option>
          </Select>
          <div className="grid grid-cols-3 gap-2">
            <Input label="Make" value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} placeholder="Toyota" />
            <Input label="Model" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="Corolla" />
            <Input label="Color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} placeholder="White" />
          </div>

          {/* Document upload */}
          <div>
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-bone-500">
              Vehicle registration document (speeds up approval)
            </label>
            <label className={cn(
              'relative flex cursor-pointer items-center gap-3 rounded-md border bg-ink-900/40 p-3 transition-colors hover:border-amber/40',
              regDoc ? 'border-amber/40' : 'border-dashed border-ink-700',
            )}>
              <input
                type="file"
                accept="image/*,application/pdf"
                onChange={(e) => setRegDoc(e.target.files?.[0] || null)}
                className="absolute inset-0 cursor-pointer opacity-0"
              />
              <FileText className={cn('size-4', regDoc ? 'text-amber' : 'text-bone-500')} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-bone-200">
                  {regDoc ? regDoc.name : 'Attach registration document (JPG/PNG/PDF)'}
                </p>
                <p className="text-[11px] text-bone-500">
                  Optional — helps admin verify faster
                </p>
              </div>
              {regDoc && (
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); setRegDoc(null); }}
                  className="shrink-0 text-bone-500 hover:text-denied"
                >
                  <XCircle className="size-4" />
                </button>
              )}
            </label>
          </div>

          <div className="flex gap-2 pt-1">
            <Button onClick={() => setShowForm(false)} variant="ghost" className="flex-1">Cancel</Button>
            <Button onClick={add} loading={adding} disabled={!form.plate_number.trim()} className="flex-1">
              <Plus className="size-4" /> Add
            </Button>
          </div>
        </section>
      ) : (
        <Button onClick={() => setShowForm(true)} className="w-full" size="lg">
          <Plus className="size-4" /> Add a vehicle
        </Button>
      )}

      {/* Assign driver modal */}
      {assigningFor && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-lg border border-ink-700 bg-ink-900 p-6">
            <h3 className="font-display text-base font-semibold text-bone-50">
              Add driver to {assigningFor.plate_number}
            </h3>
            <p className="mt-1 text-xs text-bone-400">
              Enter the username of the person you want to share this vehicle with.
            </p>
            <div className="mt-4 space-y-3">
              <Input
                label="Username"
                value={assignUsername}
                onChange={(e) => setAssignUsername(e.target.value)}
                placeholder="their_username"
                autoFocus
              />
            </div>
            <div className="mt-4 flex gap-2">
              <Button onClick={() => setAssigningFor(null)} variant="ghost" className="flex-1">Cancel</Button>
              <Button onClick={assignDriver} loading={assigning} disabled={!assignUsername.trim()} className="flex-1">
                <Users className="size-4" /> Add driver
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
