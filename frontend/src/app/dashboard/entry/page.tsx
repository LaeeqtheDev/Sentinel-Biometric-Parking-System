'use client';

import { useState } from 'react';
import {
  Camera,
  ScanFace,
  CheckCircle2,
  XCircle,
  RefreshCw,
  CircleAlert,
  Loader2,
} from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { ImageUploader } from '@/components/ImageUploader';
import { WebcamCapture } from '@/components/WebcamCapture';
import { StatusBadge } from '@/components/StatusBadge';
import { apiPost } from '@/lib/api';
import { cn } from '@/lib/utils';

type Step = 1 | 2 | 3;

interface VerifyResponse {
  decision: 'GRANTED' | 'DENIED';
  reason: string;
  plate: {
    number: string;
    registered: boolean;
    ocr_confidence?: string;
    raw_text?: string;
    found_plate?: boolean;
    vehicle?: any;
  };
  biometric: {
    matched: boolean;
    distance: number | null;
    found_face: boolean;
    reason?: string;
  };
  log_id: number;
  timestamp: string;
}

export default function LiveEntryPage() {
  const [step, setStep] = useState<Step>(1);
  const [plateImage, setPlateImage] = useState<string | null>(null);
  const [faceImage, setFaceImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState('');

  function reset() {
    setStep(1);
    setPlateImage(null);
    setFaceImage(null);
    setResult(null);
    setError('');
  }

  async function runVerification() {
    if (!plateImage || !faceImage) return;
    setSubmitting(true);
    setError('');
    try {
      const data = await apiPost<VerifyResponse>('/access/verify-entry/', {
        plate_image_base64: plateImage,
        face_image_base64: faceImage,
      });
      setResult(data);
      setStep(3);
    } catch (e: any) {
      setError(e.message || 'Verification failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Topbar
        title="Live Entry"
        subtitle="End-to-end vehicle verification simulation."
      />

      <main className="flex-1 space-y-8 p-6 lg:p-8">
        {/* Step indicator */}
        <StepIndicator current={step} />

        {error && (
          <div className="rounded-md border border-denied/30 bg-denied/10 px-4 py-3 text-sm text-denied">
            {error}
          </div>
        )}

        {/* ===================== STEP 1 — Plate ===================== */}
        {step === 1 && (
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">
                · Step 1 of 3
              </p>
              <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-bone-50">
                Capture vehicle plate
              </h2>
              <p className="mt-3 max-w-md text-bone-400">
                Upload a photo of the vehicle's license plate. The system will
                detect the plate region, run OCR, and look it up in the
                registered vehicles database.
              </p>

              <div className="mt-6 space-y-3 rounded-lg border border-ink-700 bg-ink-800/40 p-4">
                <Hint>
                  Use a clear photo with the plate roughly centred. JPG or PNG.
                </Hint>
                <Hint>
                  For demo purposes, you can use any car image — but only
                  registered plate numbers will be granted access.
                </Hint>
              </div>
            </div>

            <div>
              <ImageUploader
                onSelect={(_, dataUrl) => setPlateImage(dataUrl)}
                onClear={() => setPlateImage(null)}
                preview={plateImage}
                label="Drop plate image here"
              />
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  variant="primary"
                  size="lg"
                  disabled={!plateImage}
                  onClick={() => setStep(2)}
                >
                  Continue → Biometric
                </Button>
              </div>
            </div>
          </section>
        )}

        {/* ===================== STEP 2 — Face ===================== */}
        {step === 2 && (
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">
                · Step 2 of 3
              </p>
              <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-bone-50">
                Biometric capture
              </h2>
              <p className="mt-3 max-w-md text-bone-400">
                Position your face inside the frame. The system extracts a
                128-dimensional face encoding and compares it to the registered
                owner's enrolled biometric.
              </p>

              <div className="mt-6 rounded-lg border border-ink-700 bg-ink-800/40 p-4">
                <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
                  Plate captured
                </p>
                <div className="mt-2 flex items-center gap-3">
                  {plateImage && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={plateImage}
                      alt="Plate"
                      className="size-14 rounded-md border border-ink-600 object-cover"
                    />
                  )}
                  <span className="text-sm text-bone-300">
                    Ready for biometric step.
                  </span>
                </div>
              </div>
            </div>

            <div>
              <WebcamCapture
                onCapture={setFaceImage}
                aspect="4:3"
                showOverlay
                label="Capture face"
                preview={faceImage}
              />

              <div className="mt-4 flex justify-between gap-2">
                <Button variant="ghost" size="lg" onClick={() => setStep(1)}>
                  ← Back
                </Button>
                <Button
                  variant="primary"
                  size="lg"
                  disabled={!faceImage || submitting}
                  loading={submitting}
                  onClick={runVerification}
                >
                  {submitting ? 'Verifying…' : 'Verify & Open Gate'}
                </Button>
              </div>
            </div>
          </section>
        )}

        {/* ===================== STEP 3 — Result ===================== */}
        {step === 3 && result && (
          <ResultPanel result={result} onReset={reset} />
        )}
      </main>
    </>
  );
}

/* -------------------- Step indicator -------------------- */
function StepIndicator({ current }: { current: Step }) {
  const steps: { num: Step; label: string; icon: any }[] = [
    { num: 1, label: 'Plate', icon: Camera },
    { num: 2, label: 'Biometric', icon: ScanFace },
    { num: 3, label: 'Decision', icon: CheckCircle2 },
  ];
  return (
    <div className="flex items-center gap-3">
      {steps.map((s, i) => {
        const Icon = s.icon;
        const active = current === s.num;
        const done = current > s.num;
        return (
          <div key={s.num} className="flex items-center gap-3">
            <div
              className={cn(
                'flex items-center gap-2 rounded-full border px-3 py-1.5 transition-all',
                active && 'border-amber bg-amber/10 glow-amber',
                done && 'border-granted/40 bg-granted/10',
                !active && !done && 'border-ink-600 bg-ink-800/40',
              )}
            >
              <Icon
                className={cn(
                  'size-3.5',
                  active && 'text-amber',
                  done && 'text-granted',
                  !active && !done && 'text-bone-500',
                )}
              />
              <span
                className={cn(
                  'font-mono text-[11px] uppercase tracking-wider',
                  active && 'text-amber-glow',
                  done && 'text-granted',
                  !active && !done && 'text-bone-500',
                )}
              >
                {String(s.num).padStart(2, '0')} · {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={cn(
                  'h-px w-8 transition-colors',
                  current > s.num ? 'bg-granted/40' : 'bg-ink-600',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function Hint({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-xs text-bone-400">
      <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-bone-500" />
      <span>{children}</span>
    </div>
  );
}

/* -------------------- Result panel with animated gate -------------------- */
function ResultPanel({
  result,
  onReset,
}: {
  result: VerifyResponse;
  onReset: () => void;
}) {
  const granted = result.decision === 'GRANTED';

  return (
    <section className="animate-fade-up grid grid-cols-1 gap-6 lg:grid-cols-5">
      {/* Big verdict card */}
      <div
        className={cn(
          'relative overflow-hidden rounded-lg border p-8 lg:col-span-3',
          granted
            ? 'border-granted/40 bg-granted/5'
            : 'border-denied/40 bg-denied/5',
        )}
      >
        <div
          className={cn(
            'absolute -right-20 -top-20 h-64 w-64 rounded-full blur-3xl',
            granted ? 'bg-granted/20' : 'bg-denied/20',
          )}
        />

        <div className="relative">
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-bone-400">
            · Final Decision
          </p>

          <div className="mt-4 flex items-center gap-4">
            {granted ? (
              <CheckCircle2 className="size-12 text-granted" strokeWidth={1.5} />
            ) : (
              <XCircle className="size-12 text-denied" strokeWidth={1.5} />
            )}
            <h2
              className={cn(
                'font-display text-5xl font-semibold tracking-tight',
                granted ? 'text-granted' : 'text-denied',
              )}
            >
              {result.decision}
            </h2>
          </div>
          <p className="mt-3 max-w-lg text-bone-300">{result.reason}</p>

          {/* Animated gate */}
          <div className="mt-8">
            <BarrierGate open={granted} />
          </div>

          <div className="mt-6 flex gap-2">
            <Button onClick={onReset} variant="primary" size="lg">
              <RefreshCw className="size-4" /> Run another entry
            </Button>
          </div>
        </div>
      </div>

      {/* Detail breakdown */}
      <div className="space-y-4 lg:col-span-2">
        <DetailCard
          title="License plate"
          icon={Camera}
          status={result.plate.registered ? 'GRANTED' : 'DENIED'}
        >
          <KV
            k="Detected"
            v={
              <span className="font-mono text-base font-semibold tracking-wider text-bone-50">
                {result.plate.number || '—'}
              </span>
            }
          />
          <KV
            k="Registered"
            v={result.plate.registered ? 'Yes' : 'No'}
          />
          {result.plate.ocr_confidence && (
            <KV k="OCR confidence" v={result.plate.ocr_confidence} />
          )}
          {result.plate.raw_text && (
            <KV
              k="Raw OCR"
              v={
                <span className="font-mono text-xs text-bone-400">
                  "{result.plate.raw_text}"
                </span>
              }
            />
          )}
        </DetailCard>

        <DetailCard
          title="Biometric"
          icon={ScanFace}
          status={result.biometric.matched ? 'GRANTED' : 'DENIED'}
        >
          <KV
            k="Match"
            v={result.biometric.matched ? 'Confirmed' : 'Not confirmed'}
          />
          <KV
            k="Face detected"
            v={result.biometric.found_face ? 'Yes' : 'No face found'}
          />
          {result.biometric.distance !== null && (
            <KV
              k="Distance"
              v={
                <span className="font-mono">
                  {result.biometric.distance.toFixed(4)}{' '}
                  <span className="text-bone-500">
                    (cutoff 0.6)
                  </span>
                </span>
              }
            />
          )}
          {result.biometric.reason && (
            <KV k="Note" v={result.biometric.reason} />
          )}
        </DetailCard>

        <DetailCard title="Log entry" icon={CheckCircle2} muted>
          <KV
            k="Log ID"
            v={
              <span className="font-mono">#{result.log_id}</span>
            }
          />
          <KV
            k="Timestamp"
            v={
              <span className="font-mono text-xs">
                {new Date(result.timestamp).toLocaleString()}
              </span>
            }
          />
        </DetailCard>
      </div>
    </section>
  );
}

function DetailCard({
  title,
  icon: Icon,
  status,
  muted,
  children,
}: {
  title: string;
  icon: any;
  status?: 'GRANTED' | 'DENIED';
  muted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border p-4',
        muted
          ? 'border-ink-700 bg-ink-800/40'
          : status === 'GRANTED'
            ? 'border-granted/30 bg-ink-800/40'
            : status === 'DENIED'
              ? 'border-denied/30 bg-ink-800/40'
              : 'border-ink-600 bg-ink-800/40',
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="size-4 text-bone-400" />
          <h3 className="font-display text-sm font-semibold uppercase tracking-wider text-bone-200">
            {title}
          </h3>
        </div>
        {status && <StatusBadge status={status} />}
      </div>
      <dl className="space-y-1.5">{children}</dl>
    </div>
  );
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <dt className="text-xs uppercase tracking-wider text-bone-500">{k}</dt>
      <dd className="text-bone-200">{v}</dd>
    </div>
  );
}

/* -------------------- Animated SVG barrier gate -------------------- */
function BarrierGate({ open }: { open: boolean }) {
  return (
    <div className="relative h-32 w-full overflow-hidden rounded-md border border-ink-700 bg-gradient-to-b from-ink-900 to-ink-950">
      <div className="absolute inset-0 border-grid opacity-30" />
      {/* Ground */}
      <div className="absolute inset-x-0 bottom-0 h-px bg-amber/30" />
      <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-amber/5 to-transparent" />

      {/* Pole */}
      <div className="absolute left-12 bottom-0 h-24 w-2 rounded-t bg-bone-400" />
      {/* Pivot */}
      <div className="absolute left-[3rem] bottom-[5.5rem] z-10 size-4 -translate-x-1/2 rounded-full bg-amber glow-amber" />

      {/* Arm */}
      <div
        className={cn(
          'absolute bottom-[5.5rem] left-[3.25rem] h-2 w-56 origin-left rounded-sm',
          'bg-[repeating-linear-gradient(90deg,#fbbf24_0,#fbbf24_24px,#1b1b25_24px,#1b1b25_48px)]',
          open && 'animate-gate-open',
        )}
      />

      {/* Status */}
      <div className="absolute right-4 bottom-4">
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-widest',
            open
              ? 'border-granted/40 bg-granted/10 text-granted'
              : 'border-denied/40 bg-denied/10 text-denied',
          )}
        >
          <span
            className={cn(
              'size-1.5 rounded-full',
              open ? 'bg-granted animate-pulse-soft' : 'bg-denied',
            )}
          />
          Gate {open ? 'Open' : 'Closed'}
        </span>
      </div>
    </div>
  );
}
