'use client';

import { useEffect, useState } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  Clock,
  AlertCircle,
  Image as ImageIcon,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { apiGet, tokenStore } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { fmtDateTime, cn } from '@/lib/utils';

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

  async function upload() {
    if (!licenseFile && !cnicFile) {
      setError('Please choose at least one file to upload.');
      return;
    }
    setUploading(true);
    setError('');
    setSuccess('');
    try {
      const fd = new FormData();
      if (licenseFile) fd.append('driving_license_doc', licenseFile);
      if (cnicFile) fd.append('cnic_doc', cnicFile);

      // Use raw fetch since our api wrapper doesn't have FormData helper here
      const token = tokenStore.getAccess();
      const res = await fetch(`${API_URL}/auth/me/documents/`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          (data as any).detail || `Upload failed (${res.status})`,
        );
      }
      setSuccess('Documents uploaded — pending admin review.');
      setLicenseFile(null);
      setCnicFile(null);
      // Refresh `user` so document_verified state updates
      if (refresh) await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  const licenseURL = fileURL(user?.driving_license_doc);
  const cnicURL = fileURL(user?.cnic_doc);
  const verified = user?.documents_verified;

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Compliance
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          Documents
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          Upload your driving licence and CNIC. Admin reviews these before
          your vehicle gets ACTIVE status.
        </p>
      </div>

      {/* Status banner */}
      <div
        className={cn(
          'rounded-lg border p-4',
          verified
            ? 'border-granted/40 bg-granted/5'
            : 'border-amber/40 bg-amber/5',
        )}
      >
        <div className="flex items-start gap-3">
          {verified ? (
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-granted" />
          ) : (
            <Clock className="mt-0.5 size-5 shrink-0 text-amber" />
          )}
          <div>
            <p
              className={cn(
                'text-sm font-medium',
                verified ? 'text-granted' : 'text-amber',
              )}
            >
              {verified ? 'Documents verified' : 'Pending verification'}
            </p>
            <p className="text-xs text-bone-400">
              {verified
                ? 'An admin has reviewed and approved your documents.'
                : 'An admin will review your uploaded documents shortly.'}
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-start gap-2 rounded-md border border-granted/30 bg-granted/10 px-3 py-2 text-sm text-granted">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
          {success}
        </div>
      )}

      {/* Existing docs */}
      <section className="space-y-3">
        <h3 className="font-mono text-[11px] uppercase tracking-widest text-bone-500">
          Currently uploaded
        </h3>
        <DocStatus
          label="Driving licence"
          href={licenseURL}
        />
        <DocStatus label="CNIC / National ID" href={cnicURL} />
      </section>

      {/* Upload form */}
      <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Upload className="size-4 text-amber" />
          <h3 className="font-display text-base font-semibold text-bone-50">
            Upload / replace
          </h3>
        </div>

        <FileInput
          label="Driving licence"
          accept="image/*,application/pdf"
          file={licenseFile}
          onChange={setLicenseFile}
          hint="Front side, clear & legible. JPG / PNG / PDF."
        />
        <div className="mt-3" />
        <FileInput
          label="CNIC / National ID"
          accept="image/*,application/pdf"
          file={cnicFile}
          onChange={setCnicFile}
          hint="Front side, photo + ID number visible."
        />

        <Button
          onClick={upload}
          disabled={(!licenseFile && !cnicFile) || uploading}
          loading={uploading}
          size="lg"
          className="mt-5 w-full"
        >
          <Upload className="size-4" /> Submit for review
        </Button>
      </section>
    </div>
  );
}

function DocStatus({
  label,
  href,
}: {
  label: string;
  href: string | null;
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-md border p-3',
        href
          ? 'border-ink-700 bg-ink-800/40'
          : 'border-dashed border-ink-700 bg-ink-800/20',
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'grid size-10 place-items-center rounded-md',
            href ? 'bg-granted/10 text-granted' : 'bg-ink-700 text-bone-500',
          )}
        >
          <FileText className="size-4" />
        </div>
        <div>
          <p className="text-sm font-medium text-bone-100">{label}</p>
          <p className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
            {href ? 'On file' : 'Not uploaded'}
          </p>
        </div>
      </div>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-[11px] uppercase tracking-wider text-amber hover:underline"
        >
          View
        </a>
      )}
    </div>
  );
}

function FileInput({
  label,
  accept,
  file,
  onChange,
  hint,
}: {
  label: string;
  accept: string;
  file: File | null;
  onChange: (f: File | null) => void;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-bone-500">
        {label}
      </span>
      <div
        className={cn(
          'relative flex cursor-pointer items-center gap-3 rounded-md border bg-ink-900/40 p-3 transition-colors hover:border-amber/40',
          file ? 'border-amber/40' : 'border-dashed border-ink-700',
        )}
      >
        <input
          type="file"
          accept={accept}
          onChange={(e) => onChange(e.target.files?.[0] || null)}
          className="absolute inset-0 cursor-pointer opacity-0"
        />
        <ImageIcon
          className={cn(
            'size-5',
            file ? 'text-amber' : 'text-bone-500',
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-bone-200">
            {file ? file.name : 'Click to choose a file'}
          </p>
          {hint && !file && (
            <p className="text-[11px] text-bone-500">{hint}</p>
          )}
        </div>
      </div>
    </label>
  );
}
