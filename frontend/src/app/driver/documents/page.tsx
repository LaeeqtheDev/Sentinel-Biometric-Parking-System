'use client';

import { useEffect, useState } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  Clock,
  AlertCircle,
  Image as ImageIcon,
  Car,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { apiGet, tokenStore } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Vehicle, cn } from '@/lib/utils';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const MEDIA_BASE = API_URL.replace(/\/api\/?$/, '');

function fileURL(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.startsWith('http') ? path : `${MEDIA_BASE}${path}`;
}

export default function DriverDocumentsPage() {
  const { user, refresh } = useAuth();
  const [licenseFile, setLicenseFile] = useState<File | null>(null);
  const [cnicFile, setCnicFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Vehicle doc upload
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleDocFile, setVehicleDocFile] = useState<File | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>('');
  const [vehicleUploading, setVehicleUploading] = useState(false);

  useEffect(() => {
    apiGet<Vehicle[]>('/vehicles/my/').then(setVehicles).catch(() => {});
  }, []);

  async function uploadPersonalDocs() {
    if (!licenseFile && !cnicFile) {
      setError('Please choose at least one file.');
      return;
    }
    setUploading(true); setError(''); setSuccess('');
    try {
      const fd = new FormData();
      if (licenseFile) fd.append('driving_license_doc', licenseFile);
      if (cnicFile) fd.append('cnic_doc', cnicFile);
      const token = tokenStore.getAccess();
      const res = await fetch(`${API_URL}/auth/me/documents/`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as any).detail || `Upload failed (${res.status})`);
      }
      setSuccess('Documents uploaded — pending admin review.');
      setLicenseFile(null); setCnicFile(null);
      if (refresh) await refresh();
    } catch (e: any) { setError(e.message); }
    finally { setUploading(false); }
  }

  async function uploadVehicleDoc() {
    if (!vehicleDocFile || !selectedVehicleId) {
      setError('Select a vehicle and choose a file.');
      return;
    }
    setVehicleUploading(true); setError(''); setSuccess('');
    try {
      const fd = new FormData();
      fd.append('registration_doc', vehicleDocFile);
      const token = tokenStore.getAccess();
      // PATCH the vehicle with the new doc
      const res = await fetch(`${API_URL}/vehicles/${selectedVehicleId}/`, {
        method: 'PATCH',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!res.ok) throw new Error(`Upload failed (${res.status})`);
      setSuccess('Vehicle registration document uploaded.');
      setVehicleDocFile(null);
      const updated = await apiGet<Vehicle[]>('/vehicles/my/');
      setVehicles(updated);
    } catch (e: any) { setError(e.message); }
    finally { setVehicleUploading(false); }
  }

  const licenseURL = fileURL(user?.driving_license_doc);
  const cnicURL = fileURL(user?.cnic_doc);
  const verified = user?.documents_verified;

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">· Compliance</p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50">Documents</h1>
        <p className="mt-2 text-sm text-bone-400">Upload your ID documents and vehicle registration for admin verification.</p>
      </div>

      {/* Verification status */}
      <div className={cn('rounded-lg border p-4', verified ? 'border-granted/40 bg-granted/5' : 'border-amber/40 bg-amber/5')}>
        <div className="flex items-start gap-3">
          {verified ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-granted" /> : <Clock className="mt-0.5 size-5 shrink-0 text-amber" />}
          <div>
            <p className={cn('text-sm font-medium', verified ? 'text-granted' : 'text-amber')}>
              {verified ? 'Documents verified' : 'Pending verification'}
            </p>
            <p className="text-xs text-bone-400">
              {verified ? 'Admin approved your documents.' : 'Admin will review shortly.'}
            </p>
          </div>
        </div>
      </div>

      {error && <div className="flex items-start gap-2 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied"><AlertCircle className="mt-0.5 size-4 shrink-0" />{error}</div>}
      {success && <div className="flex items-start gap-2 rounded-md border border-granted/30 bg-granted/10 px-3 py-2 text-sm text-granted"><CheckCircle2 className="mt-0.5 size-4 shrink-0" />{success}</div>}

      {/* Current personal docs */}
      <section className="space-y-2">
        <h3 className="font-mono text-[11px] uppercase tracking-widest text-bone-500">Personal documents</h3>
        <DocStatus label="Driving licence" href={licenseURL} />
        <DocStatus label="CNIC / National ID" href={cnicURL} />
      </section>

      {/* Upload personal docs */}
      <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Upload className="size-4 text-amber" />
          <h3 className="font-display text-base font-semibold text-bone-50">Upload personal documents</h3>
        </div>
        <FileInput label="Driving licence" accept="image/*,application/pdf" file={licenseFile} onChange={setLicenseFile} hint="Front side, clear & legible." />
        <FileInput label="CNIC / National ID" accept="image/*,application/pdf" file={cnicFile} onChange={setCnicFile} hint="Front side, ID number visible." />
        <Button onClick={uploadPersonalDocs} disabled={(!licenseFile && !cnicFile) || uploading} loading={uploading} size="lg" className="w-full">
          <Upload className="size-4" /> Submit for review
        </Button>
      </section>

      {/* Vehicle registration docs */}
      {vehicles.length > 0 && (
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Car className="size-4 text-amber" />
            <h3 className="font-display text-base font-semibold text-bone-50">Vehicle registration documents</h3>
          </div>
          <p className="text-xs text-bone-400">Upload the registration certificate for your vehicle. Speeds up admin approval.</p>

          {/* Show existing docs */}
          {vehicles.map((v) => (
            <div key={v.id} className="flex items-center justify-between rounded-md border border-ink-700 bg-ink-900/40 px-3 py-2">
              <div className="flex items-center gap-2">
                <Car className="size-4 text-bone-500" />
                <span className="font-mono text-sm text-bone-200">{v.plate_number}</span>
                <span className={cn('rounded-full px-1.5 py-0.5 font-mono text-[9px] uppercase', v.status === 'ACTIVE' ? 'bg-granted/10 text-granted' : v.status === 'BLOCKED' ? 'bg-denied/10 text-denied' : 'bg-amber/10 text-amber')}>{v.status.toLowerCase().replace('_', ' ')}</span>
              </div>
              {(v as any).registration_doc ? (
                <a href={fileURL((v as any).registration_doc) || '#'} target="_blank" rel="noopener noreferrer" className="font-mono text-[11px] text-amber hover:underline">View doc</a>
              ) : (
                <span className="font-mono text-[10px] text-bone-600">No doc</span>
              )}
            </div>
          ))}

          <div className="space-y-2">
            <label className="block font-mono text-[10px] uppercase tracking-wider text-bone-500">Select vehicle</label>
            <select
              value={selectedVehicleId}
              onChange={(e) => setSelectedVehicleId(e.target.value)}
              className="w-full rounded border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-bone-200 focus:border-amber focus:outline-none"
            >
              <option value="">Choose a vehicle…</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>{v.plate_number} ({v.status.toLowerCase()})</option>
              ))}
            </select>
          </div>
          <FileInput label="Registration document" accept="image/*,application/pdf" file={vehicleDocFile} onChange={setVehicleDocFile} hint="Vehicle registration certificate." />
          <Button onClick={uploadVehicleDoc} disabled={!vehicleDocFile || !selectedVehicleId || vehicleUploading} loading={vehicleUploading} className="w-full">
            <Upload className="size-4" /> Upload vehicle document
          </Button>
        </section>
      )}
    </div>
  );
}

function DocStatus({ label, href }: { label: string; href: string | null }) {
  return (
    <div className={cn('flex items-center justify-between rounded-md border p-3', href ? 'border-ink-700 bg-ink-800/40' : 'border-dashed border-ink-700 bg-ink-800/20')}>
      <div className="flex items-center gap-3">
        <div className={cn('grid size-10 place-items-center rounded-md', href ? 'bg-granted/10 text-granted' : 'bg-ink-700 text-bone-500')}>
          <FileText className="size-4" />
        </div>
        <div>
          <p className="text-sm font-medium text-bone-100">{label}</p>
          <p className="font-mono text-[10px] uppercase tracking-wider text-bone-500">{href ? 'On file' : 'Not uploaded'}</p>
        </div>
      </div>
      {href && <a href={href} target="_blank" rel="noopener noreferrer" className="font-mono text-[11px] uppercase tracking-wider text-amber hover:underline">View</a>}
    </div>
  );
}

function FileInput({ label, accept, file, onChange, hint }: { label: string; accept: string; file: File | null; onChange: (f: File | null) => void; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-bone-500">{label}</span>
      <div className={cn('relative flex cursor-pointer items-center gap-3 rounded-md border bg-ink-900/40 p-3 transition-colors hover:border-amber/40', file ? 'border-amber/40' : 'border-dashed border-ink-700')}>
        <input type="file" accept={accept} onChange={(e) => onChange(e.target.files?.[0] || null)} className="absolute inset-0 cursor-pointer opacity-0" />
        <ImageIcon className={cn('size-5', file ? 'text-amber' : 'text-bone-500')} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-bone-200">{file ? file.name : 'Click to choose a file'}</p>
          {hint && !file && <p className="text-[11px] text-bone-500">{hint}</p>}
        </div>
      </div>
    </label>
  );
}
