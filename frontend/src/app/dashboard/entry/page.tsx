'use client';

import { useEffect, useState } from 'react';
import {
  Car,
  ScanFace,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RefreshCw,
  ArrowDownLeft,
  ArrowUpRight,
} from 'lucide-react';
import { WebcamCapture } from '@/components/WebcamCapture';
import { Button } from '@/components/Button';
import { apiPost } from '@/lib/api';
import { cn, fmtDateTime } from '@/lib/utils';

type Step = 'mode' | 'plate' | 'face' | 'result';
type Mode = 'ENTRY' | 'EXIT';

interface DecisionResult {
  decision: 'GRANTED' | 'DENIED';
  event_type: 'ENTRY' | 'EXIT';
  reason: string;
  plate?: { number: string; registered: boolean; ocr_confidence?: string };
  biometric?: { matched: boolean; reason?: string };
  webauthn?: { matched: boolean };
  session_found?: boolean;
  log_id: number;
  timestamp: string;
}

export default function EntryPage() {
  const [step, setStep] = useState<Step>('mode');
  const [mode, setMode] = useState<Mode>('ENTRY');
  const [plateImage, setPlateImage] = useState<string | null>(null);
  const [manualPlate, setManualPlate] = useState<string>('');
  const [faceImage, setFaceImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [error, setError] = useState('');

  function reset() {
    setStep('mode');
    setPlateImage(null);
    setManualPlate('');
    setFaceImage(null);
    setResult(null);
    setError('');
  }

  async function submit() {
    if (!plateImage && !manualPlate.trim()) {
      setError('Capture the license plate or type it manually.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const endpoint =
        mode === 'EXIT' ? '/access/verify-exit/' : '/access/verify-entry/';
      const payload: any = {
        face_image_base64: faceImage || undefined,
        via: manualPlate.trim() ? 'manual_plate_entry' : 'manual',
      };
      if (manualPlate.trim()) {
        payload.plate_number = manualPlate.trim();
      }
      if (plateImage) {
        payload.plate_image_base64 = plateImage;
      }
      const res = await apiPost<DecisionResult>(endpoint, payload);
      setResult(res);
      setStep('result');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Manual gate
        </p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
          Verify access
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          Manual ENTRY/EXIT verification: capture plate, then verify driver
          biometric.
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider">
        <StepDot active={step === 'mode'} done={step !== 'mode'} label="Mode" />
        <span className="text-bone-700">—</span>
        <StepDot
          active={step === 'plate'}
          done={['face', 'result'].includes(step)}
          label="Plate"
        />
        <span className="text-bone-700">—</span>
        <StepDot
          active={step === 'face'}
          done={step === 'result'}
          label="Biometric"
        />
        <span className="text-bone-700">—</span>
        <StepDot active={step === 'result'} done={false} label="Result" />
      </div>

      {error && (
        <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
          {error}
        </div>
      )}

      {/* Step: Mode */}
      {step === 'mode' && (
        <div className="grid gap-4 sm:grid-cols-2">
          <ModeCard
            mode="ENTRY"
            selected={mode === 'ENTRY'}
            onSelect={() => setMode('ENTRY')}
          />
          <ModeCard
            mode="EXIT"
            selected={mode === 'EXIT'}
            onSelect={() => setMode('EXIT')}
          />
          <Button
            onClick={() => setStep('plate')}
            size="lg"
            className="sm:col-span-2"
          >
            Continue with {mode} <ArrowRight className="size-4" />
          </Button>
        </div>
      )}

      {/* Step: Plate */}
      {step === 'plate' && (
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <div className="mb-4 flex items-center gap-2">
            <Car className="size-4 text-amber" />
            <h2 className="font-display text-base font-semibold text-bone-50">
              1 · Capture license plate
            </h2>
          </div>
          <WebcamCapture
            value={plateImage}
            onCapture={setPlateImage}
            placeholder="Position the plate inside the frame, then capture."
            facing="environment"
            showOverlay
            minSharpness={30}
          />
          <div className="mt-4 rounded-md border border-ink-700 bg-ink-900/40 p-3">
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-bone-500">
              Plate text (manual override)
            </label>
            <input
              type="text"
              value={manualPlate}
              onChange={(e) => setManualPlate(e.target.value.toUpperCase())}
              placeholder="e.g. AAP-1478 — leave blank to use OCR"
              className="w-full rounded border border-ink-700 bg-ink-950 px-3 py-2 font-mono text-sm tracking-wider text-bone-100 placeholder:text-bone-600 focus:border-amber focus:outline-none"
            />
            <p className="mt-1.5 text-[11px] text-bone-500">
              If OCR can't read the plate (handwritten, unusual font, dirty),
              type it here. Your text takes priority over OCR.
            </p>
          </div>
          <div className="mt-4 flex gap-3">
            <Button onClick={() => setStep('mode')} variant="ghost">
              ← Back
            </Button>
            <Button
              onClick={() => setStep('face')}
              disabled={!plateImage && !manualPlate.trim()}
              className="ml-auto"
            >
              Next <ArrowRight className="size-4" />
            </Button>
          </div>
        </section>
      )}

      {/* Step: Face */}
      {step === 'face' && (
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <div className="mb-4 flex items-center gap-2">
            <ScanFace className="size-4 text-amber" />
            <h2 className="font-display text-base font-semibold text-bone-50">
              2 · Driver biometric (face)
            </h2>
          </div>
          <p className="mb-4 text-xs text-bone-400">
            Face will be matched against the user enrolled for this vehicle.
            Optional — if skipped, the driver must use a passkey via the
            mobile pickup flow instead.
          </p>
          <WebcamCapture
            value={faceImage}
            onCapture={setFaceImage}
            placeholder="Look at the camera and capture."
          />
          <div className="mt-4 flex gap-3">
            <Button onClick={() => setStep('plate')} variant="ghost">
              ← Back
            </Button>
            <Button
              onClick={submit}
              loading={submitting}
              className="ml-auto"
              size="lg"
            >
              <ShieldCheck className="size-4" /> Verify {mode}
            </Button>
          </div>
        </section>
      )}

      {/* Step: Result */}
      {step === 'result' && result && (
        <ResultPanel result={result} onReset={reset} />
      )}
    </div>
  );
}

function StepDot({
  active,
  done,
  label,
}: {
  active: boolean;
  done: boolean;
  label: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5',
        active
          ? 'text-amber'
          : done
          ? 'text-granted'
          : 'text-bone-600',
      )}
    >
      <span
        className={cn(
          'size-1.5 rounded-full',
          active
            ? 'bg-amber animate-pulse-soft'
            : done
            ? 'bg-granted'
            : 'bg-bone-700',
        )}
      />
      {label}
    </span>
  );
}

function ModeCard({
  mode,
  selected,
  onSelect,
}: {
  mode: Mode;
  selected: boolean;
  onSelect: () => void;
}) {
  const isEntry = mode === 'ENTRY';
  return (
    <button
      onClick={onSelect}
      className={cn(
        'rounded-lg border p-5 text-left transition-colors',
        selected
          ? 'border-amber bg-amber/5'
          : 'border-ink-600 bg-ink-800/40 hover:border-ink-500',
      )}
    >
      <div className="flex items-center justify-between">
        <div
          className={cn(
            'grid size-10 place-items-center rounded-md',
            selected
              ? isEntry
                ? 'bg-granted/20 text-granted'
                : 'bg-amber/20 text-amber'
              : 'bg-ink-700 text-bone-400',
          )}
        >
          {isEntry ? (
            <ArrowDownLeft className="size-5" />
          ) : (
            <ArrowUpRight className="size-5" />
          )}
        </div>
        {selected && (
          <CheckCircle2 className="size-5 text-amber" />
        )}
      </div>
      <p className="mt-3 font-display text-lg font-semibold text-bone-50">
        {isEntry ? 'Entry' : 'Exit'}
      </p>
      <p className="mt-1 text-xs text-bone-400">
        {isEntry
          ? 'Vehicle arriving — verify and open gate inward.'
          : 'Vehicle leaving — verify driver and close session.'}
      </p>
    </button>
  );
}

function ResultPanel({
  result,
  onReset,
}: {
  result: DecisionResult;
  onReset: () => void;
}) {
  const granted = result.decision === 'GRANTED';
  // Local animation state — drive the gate phases when granted
  const [phase, setPhase] = useState<'opening' | 'open' | 'closing' | 'closed' | null>(
    granted ? 'opening' : null,
  );
  useEffect(() => {
    if (!granted) return;
    const t1 = setTimeout(() => setPhase('open'), 1200);
    const t2 = setTimeout(() => setPhase('closing'), 4200);
    const t3 = setTimeout(() => setPhase('closed'), 5400);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [granted]);

  return (
    <section
      className={cn(
        'rounded-lg border p-6',
        granted
          ? 'border-granted/40 bg-granted/5'
          : 'border-denied/40 bg-denied/5',
      )}
    >
      <div className="flex items-start gap-4">
        {granted ? (
          <CheckCircle2
            className="size-12 shrink-0 text-granted"
            strokeWidth={1.5}
          />
        ) : (
          <XCircle
            className="size-12 shrink-0 text-denied"
            strokeWidth={1.5}
          />
        )}
        <div className="flex-1">
          <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
            {result.event_type} · {fmtDateTime(result.timestamp)}
          </p>
          <h2
            className={cn(
              'mt-1 font-display text-2xl font-semibold tracking-tight',
              granted ? 'text-granted' : 'text-denied',
            )}
          >
            {granted ? 'Access granted' : 'Access denied'}
          </h2>
          <p className="mt-2 text-sm text-bone-300">{result.reason}</p>

          {/* Gate animation when granted */}
          {granted && phase && <ManualGateAnimation phase={phase} />}

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-ink-700 pt-4 font-mono text-[11px]">
            <Row
              label="Plate"
              value={result.plate?.number || '—'}
              status={result.plate?.registered ? 'good' : 'bad'}
            />
            <Row
              label="OCR confidence"
              value={result.plate?.ocr_confidence || 'n/a'}
            />
            <Row
              label="Biometric"
              value={result.biometric?.matched ? 'matched' : 'not matched'}
              status={result.biometric?.matched ? 'good' : 'bad'}
            />
            <Row
              label="Passkey"
              value={result.webauthn?.matched ? 'verified' : '—'}
              status={result.webauthn?.matched ? 'good' : 'neutral'}
            />
            {result.event_type === 'EXIT' && (
              <Row
                label="Session"
                value={result.session_found ? 'found' : 'not found'}
                status={result.session_found ? 'good' : 'bad'}
              />
            )}
          </dl>

          <Button onClick={onReset} className="mt-5">
            <RefreshCw className="size-4" /> New verification
          </Button>
        </div>
      </div>
    </section>
  );
}

function ManualGateAnimation({ phase }: { phase: 'opening' | 'open' | 'closing' | 'closed' }) {
  const config = {
    opening: { label: '⚙ GATE OPENING…', color: 'text-amber', pct: 50, pulse: true },
    open: { label: '✓ GATE OPEN — vehicle passing', color: 'text-granted', pct: 100, pulse: false },
    closing: { label: '⚙ GATE CLOSING…', color: 'text-amber', pct: 30, pulse: true },
    closed: { label: '✓ GATE CLOSED — cycle complete', color: 'text-bone-400', pct: 0, pulse: false },
  } as const;
  const c = config[phase];
  return (
    <div className="mt-4 rounded border border-ink-700 bg-ink-900/60 px-3 py-2">
      <div className="flex items-center justify-between">
        <span className={cn('font-mono text-[11px] uppercase tracking-wider', c.color, c.pulse && 'animate-pulse-soft')}>
          {c.label}
        </span>
        <span className="font-mono text-[10px] text-bone-500">{c.pct}%</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-800">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-1000',
            phase === 'open' ? 'bg-granted' : phase === 'closed' ? 'bg-ink-700' : 'bg-amber',
          )}
          style={{ width: `${c.pct}%` }}
        />
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status?: 'good' | 'bad' | 'neutral';
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-bone-500 uppercase tracking-wider">{label}</span>
      <span
        className={cn(
          status === 'good' && 'text-granted',
          status === 'bad' && 'text-denied',
          (!status || status === 'neutral') && 'text-bone-300',
        )}
      >
        {value}
      </span>
    </div>
  );
}
