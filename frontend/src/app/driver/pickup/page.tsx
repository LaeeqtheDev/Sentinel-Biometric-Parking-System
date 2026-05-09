'use client';

import { useEffect, useState } from 'react';
import {
  Car,
  ParkingCircle,
  CheckCircle2,
  XCircle,
  Fingerprint,
  RefreshCw,
  ScanFace,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { WebcamCapture } from '@/components/WebcamCapture';
import { apiGet, apiPost } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { authenticatePasskey, webauthnSupported } from '@/lib/webauthn';
import { ParkingSession, fmtDateTime, fmtDuration, cn } from '@/lib/utils';

type Phase =
  | 'select'
  | 'choose-method'
  | 'verifying-passkey'
  | 'face-capture'
  | 'verifying-face'
  | 'success'
  | 'denied';

type Method = 'passkey' | 'face';

export default function DriverPickupPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [phase, setPhase] = useState<Phase>('select');
  const [selectedSession, setSelectedSession] =
    useState<ParkingSession | null>(null);
  const [result, setResult] = useState<any>(null);
  const [faceImage, setFaceImage] = useState<string | null>(null);
  const passkeyAvailable = webauthnSupported();
  const faceAvailable = Boolean(user?.has_biometric);

  async function load() {
    setLoading(true);
    try {
      const all = await apiGet<ParkingSession[]>('/parking/my/');
      setSessions(all.filter((s) => s.status === 'PARKED'));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function startVerification(session: ParkingSession) {
    setSelectedSession(session);
    setError('');
    setFaceImage(null);
    // If only one method available, go straight to it.
    if (passkeyAvailable && !faceAvailable) {
      tryPasskey(session);
    } else if (!passkeyAvailable && faceAvailable) {
      setPhase('face-capture');
    } else if (passkeyAvailable && faceAvailable) {
      setPhase('choose-method');
    } else {
      setError(
        'You have no biometric enrolled. Set up a passkey or face match in the Passkey tab first.',
      );
    }
  }

  async function tryPasskey(session: ParkingSession) {
    setPhase('verifying-passkey');
    setError('');
    try {
      const auth = await authenticatePasskey(user!.username);
      if (!auth.matched) throw new Error('Passkey verification failed.');

      const res = await apiPost<any>('/access/verify-exit/', {
        plate_number: session.vehicle_detail.plate_number,
        webauthn_user_id: auth.user_id,
        via: 'driver_app',
      });

      setResult(res);
      setPhase(res.decision === 'GRANTED' ? 'success' : 'denied');
      if (res.decision === 'GRANTED') load();
    } catch (e: any) {
      // Passkey failed — offer face fallback if available
      if (faceAvailable) {
        setError(`Passkey failed: ${e.message}. Try face match instead.`);
        setPhase('face-capture');
      } else {
        setError(e.message || 'Authorization cancelled.');
        setPhase('denied');
        setResult({ reason: e.message });
      }
    }
  }

  async function tryFace() {
    if (!selectedSession || !faceImage) return;
    setPhase('verifying-face');
    setError('');
    try {
      const res = await apiPost<any>('/access/verify-exit/', {
        plate_number: selectedSession.vehicle_detail.plate_number,
        face_image_base64: faceImage,
        via: 'driver_app_face',
      });
      setResult(res);
      setPhase(res.decision === 'GRANTED' ? 'success' : 'denied');
      if (res.decision === 'GRANTED') load();
    } catch (e: any) {
      setError(e.message || 'Face verification failed.');
      setPhase('denied');
      setResult({ reason: e.message });
    }
  }

  function reset() {
    setPhase('select');
    setSelectedSession(null);
    setResult(null);
    setError('');
    setFaceImage(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Exit verification
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          Pickup my car
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          Choose the vehicle you're picking up and verify with passkey OR
          face match. The system tries passkey first and falls back to face
          if that fails.
        </p>
      </div>

      {phase === 'select' && (
        <>
          {error && (
            <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
              {error}
            </div>
          )}
          {loading ? (
            <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
              Loading parked cars…
            </div>
          ) : sessions.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-8 text-center">
              <ParkingCircle className="mx-auto size-10 text-bone-500" />
              <p className="mt-3 font-medium text-bone-300">
                No parked cars right now
              </p>
              <p className="mt-1 text-sm text-bone-500">
                When one of your vehicles is parked, it will show up here.
              </p>
            </div>
          ) : (
            <ul className="space-y-3">
              {sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => startVerification(s)}
                  className="group flex w-full items-center justify-between rounded-lg border border-ink-700 bg-ink-800/40 p-4 text-left transition-colors hover:border-amber/40 hover:bg-amber/5"
                >
                  <div className="flex items-center gap-3">
                    <div className="grid size-12 place-items-center rounded-md border border-amber/40 bg-amber/10 text-amber">
                      <Car className="size-5" />
                    </div>
                    <div>
                      <p className="font-mono text-base font-semibold tracking-wider text-bone-50">
                        {s.vehicle_detail.plate_number}
                      </p>
                      <p className="text-xs text-bone-500">
                        Parked since {fmtDateTime(s.entry_time)}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className="size-5 text-bone-500 group-hover:text-amber" />
                </button>
              ))}
            </ul>
          )}
        </>
      )}

      {phase === 'choose-method' && selectedSession && (
        <div className="space-y-4">
          <p className="text-sm text-bone-300">
            Verifying pickup of{' '}
            <span className="font-mono font-semibold text-bone-50">
              {selectedSession.vehicle_detail.plate_number}
            </span>
            . Choose method:
          </p>
          <button
            onClick={() => tryPasskey(selectedSession)}
            className="flex w-full items-center justify-between rounded-lg border border-amber/40 bg-amber/5 p-4 text-left hover:bg-amber/10"
          >
            <div className="flex items-center gap-3">
              <Fingerprint className="size-6 text-amber" />
              <div>
                <p className="font-medium text-bone-50">
                  Passkey (recommended)
                </p>
                <p className="text-xs text-bone-400">
                  FaceID / fingerprint via your device
                </p>
              </div>
            </div>
            <ArrowRight className="size-4 text-amber" />
          </button>
          <button
            onClick={() => setPhase('face-capture')}
            className="flex w-full items-center justify-between rounded-lg border border-ink-700 bg-ink-800/40 p-4 text-left hover:border-ink-500"
          >
            <div className="flex items-center gap-3">
              <ScanFace className="size-6 text-bone-300" />
              <div>
                <p className="font-medium text-bone-50">Face match</p>
                <p className="text-xs text-bone-400">
                  Camera-based, fallback option
                </p>
              </div>
            </div>
            <ArrowRight className="size-4 text-bone-400" />
          </button>
          <Button onClick={reset} variant="ghost" className="w-full">
            Cancel
          </Button>
        </div>
      )}

      {phase === 'verifying-passkey' && (
        <div className="grid place-items-center rounded-lg border border-amber/40 bg-amber/5 p-12 text-center">
          <div className="size-14 animate-pulse rounded-full bg-amber/20 p-3">
            <Fingerprint className="size-8 text-amber" strokeWidth={1.5} />
          </div>
          <p className="mt-4 font-display text-lg font-semibold text-bone-50">
            Verifying passkey…
          </p>
          <p className="mt-1 text-sm text-bone-400">
            Follow the prompt on your device.
          </p>
        </div>
      )}

      {phase === 'face-capture' && (
        <div className="space-y-4">
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
            <h3 className="mb-2 font-display text-base font-semibold text-bone-50">
              Face verification
            </h3>
            <p className="mb-4 text-xs text-bone-400">
              Capture a clear photo of your face. The system compares it to
              your enrolled face encoding.
            </p>
            {error && (
              <div className="mb-3 rounded-md border border-amber/30 bg-amber/10 px-3 py-2 text-sm text-amber">
                {error}
              </div>
            )}
            <WebcamCapture
              value={faceImage}
              onCapture={setFaceImage}
              placeholder="Look at the camera. Make sure your face is well lit."
              minSharpness={20}
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={reset} variant="ghost" className="flex-1">
              Cancel
            </Button>
            <Button
              onClick={tryFace}
              disabled={!faceImage}
              className="flex-1"
              size="lg"
            >
              <ScanFace className="size-4" /> Verify face
            </Button>
          </div>
        </div>
      )}

      {phase === 'verifying-face' && (
        <div className="grid place-items-center rounded-lg border border-amber/40 bg-amber/5 p-12 text-center">
          <div className="size-14 animate-pulse rounded-full bg-amber/20 p-3">
            <ScanFace className="size-8 text-amber" strokeWidth={1.5} />
          </div>
          <p className="mt-4 font-display text-lg font-semibold text-bone-50">
            Matching face…
          </p>
        </div>
      )}

      {phase === 'success' && result && (
        <ResultPanel
          icon={CheckCircle2}
          color="granted"
          title="Access granted"
          subtitle={result.reason}
          session={selectedSession}
          onReset={reset}
        />
      )}

      {phase === 'denied' && (
        <ResultPanel
          icon={XCircle}
          color="denied"
          title="Access denied"
          subtitle={result?.reason || error || 'Verification failed.'}
          session={selectedSession}
          onReset={reset}
          allowFaceRetry={faceAvailable && !!selectedSession}
          onRetryFace={() => {
            setError('');
            setFaceImage(null);
            setPhase('face-capture');
          }}
        />
      )}
    </div>
  );
}

function ResultPanel({
  icon: Icon,
  color,
  title,
  subtitle,
  session,
  onReset,
  allowFaceRetry,
  onRetryFace,
}: {
  icon: any;
  color: 'granted' | 'denied';
  title: string;
  subtitle: string;
  session: ParkingSession | null;
  onReset: () => void;
  allowFaceRetry?: boolean;
  onRetryFace?: () => void;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border p-6',
        color === 'granted'
          ? 'border-granted/40 bg-granted/5'
          : 'border-denied/40 bg-denied/5',
      )}
    >
      <div className="flex items-start gap-4">
        <Icon
          className={cn(
            'size-10 shrink-0',
            color === 'granted' ? 'text-granted' : 'text-denied',
          )}
          strokeWidth={1.5}
        />
        <div className="flex-1">
          <h2
            className={cn(
              'font-display text-2xl font-semibold tracking-tight',
              color === 'granted' ? 'text-granted' : 'text-denied',
            )}
          >
            {title}
          </h2>
          <p className="mt-2 text-sm text-bone-300">{subtitle}</p>
          {session && (
            <div className="mt-4 space-y-1 border-t border-ink-700 pt-3 font-mono text-xs text-bone-500">
              <p>
                <span className="text-bone-400">Plate · </span>
                <span className="text-bone-200">
                  {session.vehicle_detail.plate_number}
                </span>
              </p>
              <p>
                <span className="text-bone-400">Entered · </span>
                <span className="text-bone-200">
                  {fmtDateTime(session.entry_time)}
                </span>
              </p>
            </div>
          )}
          <div className="mt-5 flex gap-2">
            {color === 'denied' && allowFaceRetry && (
              <Button onClick={onRetryFace} variant="primary">
                <ScanFace className="size-4" /> Try face match
              </Button>
            )}
            <Button onClick={onReset} variant="ghost">
              <RefreshCw className="size-4" /> Done
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
