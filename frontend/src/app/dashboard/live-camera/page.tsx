'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Webcam from 'react-webcam';
import { QRCodeCanvas } from 'qrcode.react';
import {
  Video,
  VideoOff,
  Car,
  ScanLine,
  ArrowDownLeft,
  ArrowUpRight,
  AlertCircle,
  CheckCircle2,
  XCircle,
  History,
  QrCode,
  X,
  Smartphone,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { apiPost } from '@/lib/api';
import { Vehicle, fmtDateTime, cn } from '@/lib/utils';

interface Detection {
  id: string;
  plate: string;
  confidence: 'high' | 'medium' | 'low' | 'none';
  registered: boolean;
  fresh: boolean;
  vehicle?: Vehicle | null;
  active_session?: { id: number; entry_time: string } | null;
  suggested_event?: 'ENTRY' | 'EXIT';
  timestamp: number;
  decisionLog?: { decision: string; reason: string };
}

export default function LiveCameraPage() {
  const webcamRef = useRef<Webcam>(null);
  const [running, setRunning] = useState(false);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lastFrame, setLastFrame] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // QR modal for sending verification link to driver's phone
  const [qrInfo, setQrInfo] = useState<{
    deep_link: string;
    plate: string;
    event_type: 'ENTRY' | 'EXIT';
    expires_at: string;
  } | null>(null);

  const captureAndDetect = useCallback(async () => {
    if (!webcamRef.current || busy) return;
    const screenshot = webcamRef.current.getScreenshot();
    if (!screenshot) return;

    setLastFrame(screenshot);
    setBusy(true);
    try {
      const res = await apiPost<any>('/access/live-detect/', {
        plate_image_base64: screenshot,
      });
      if (res.plate) {
        setDetections((prev) => {
          // dedupe consecutive same-plate detections
          if (prev[0]?.plate === res.plate && !res.fresh) return prev;
          const det: Detection = {
            id: `${Date.now()}-${Math.random()}`,
            plate: res.plate,
            confidence: res.confidence,
            registered: res.registered,
            fresh: res.fresh,
            vehicle: res.vehicle,
            active_session: res.active_session,
            suggested_event: res.suggested_event,
            timestamp: Date.now(),
          };
          return [det, ...prev].slice(0, 12);
        });
      }
    } catch (e: any) {
      // Silently retry on error
      console.warn('live-detect failed:', e?.message);
    } finally {
      setBusy(false);
    }
  }, [busy]);

  useEffect(() => {
    if (!running) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    captureAndDetect();
    intervalRef.current = setInterval(captureAndDetect, 2500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [running, captureAndDetect]);

  async function actOn(det: Detection) {
    if (!det.registered || !det.fresh) return;
    setError('');
    const endpoint =
      det.suggested_event === 'EXIT'
        ? '/access/verify-exit/'
        : '/access/verify-entry/';
    try {
      // For the simulation, we don't have a face on file at the live gate, so
      // we let the admin override-as-OCR-only. They'd then run biometric on
      // the kiosk or the driver's phone separately.
      const res = await apiPost<any>('/access/manual-override/', {
        plate_number: det.plate,
        event_type: det.suggested_event,
        reason: 'Triggered from live camera (OCR matched a registered plate).',
      });
      setDetections((prev) =>
        prev.map((d) =>
          d.id === det.id
            ? {
                ...d,
                decisionLog: {
                  decision: res.status,
                  reason: res.reason,
                },
              }
            : d,
        ),
      );
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function sendToPhone(det: Detection) {
    if (!det.registered || !det.fresh || !det.vehicle) return;
    setError('');
    try {
      const res = await apiPost<any>('/passkeys/pickup-tokens/', {
        vehicle_id: det.vehicle.id,
        event_type: det.suggested_event,
      });
      setQrInfo({
        deep_link: res.deep_link,
        plate: det.plate,
        event_type: res.event_type,
        expires_at: res.expires_at,
      });
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Live surveillance
        </p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
          Live camera feed
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          Continuous OCR every 2.5 seconds. The same plate is debounced for
          30 seconds to prevent duplicate triggers.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        {/* Camera */}
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold text-bone-50">
              Gate camera
            </h2>
            {running ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-granted/40 bg-granted/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-granted">
                <span className="size-1.5 rounded-full bg-granted animate-pulse-soft" />
                Live
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-ink-600 bg-ink-900 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                Idle
              </span>
            )}
          </div>

          <div className="relative aspect-video overflow-hidden rounded-md border border-ink-700 bg-ink-950">
            {running ? (
              <Webcam
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                videoConstraints={{ facingMode: 'environment' }}
                className="size-full object-cover"
              />
            ) : (
              <div className="grid size-full place-items-center text-bone-500">
                <div className="text-center">
                  <VideoOff className="mx-auto size-10" strokeWidth={1.5} />
                  <p className="mt-2 text-sm">Camera off</p>
                </div>
              </div>
            )}

            {/* Scanning overlay */}
            {running && (
              <>
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-1 animate-scan bg-gradient-to-b from-amber/50 to-transparent" />
                <div className="pointer-events-none absolute inset-4 z-10 rounded border border-amber/40">
                  <span className="absolute -left-px -top-px size-3 border-l-2 border-t-2 border-amber" />
                  <span className="absolute -right-px -top-px size-3 border-r-2 border-t-2 border-amber" />
                  <span className="absolute -bottom-px -left-px size-3 border-b-2 border-l-2 border-amber" />
                  <span className="absolute -bottom-px -right-px size-3 border-b-2 border-r-2 border-amber" />
                </div>
              </>
            )}
          </div>

          <div className="mt-4 flex gap-3">
            <Button
              onClick={() => setRunning(!running)}
              variant={running ? 'ghost' : 'primary'}
              className="flex-1"
              size="lg"
            >
              {running ? (
                <>
                  <VideoOff className="size-4" /> Stop feed
                </>
              ) : (
                <>
                  <Video className="size-4" /> Start feed
                </>
              )}
            </Button>
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
              <AlertCircle className="size-4" /> {error}
            </div>
          )}
        </section>

        {/* Detection feed */}
        <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
          <div className="mb-4 flex items-center gap-2">
            <ScanLine className="size-4 text-amber" />
            <h2 className="font-display text-lg font-semibold text-bone-50">
              Detection feed
            </h2>
          </div>

          {detections.length === 0 ? (
            <div className="rounded-md border border-dashed border-ink-700 bg-ink-900/40 p-8 text-center text-sm text-bone-500">
              {running
                ? 'Watching for plates…'
                : 'Press Start feed to begin OCR.'}
            </div>
          ) : (
            <ul className="space-y-2">
              {detections.map((det) => (
                <li
                  key={det.id}
                  className={cn(
                    'rounded-md border p-3 transition-colors',
                    det.registered && det.fresh
                      ? 'border-amber/40 bg-amber/5'
                      : det.registered
                      ? 'border-ink-600 bg-ink-900/40'
                      : 'border-denied/20 bg-denied/5',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <Car
                        className={cn(
                          'size-4 shrink-0',
                          det.registered ? 'text-amber' : 'text-bone-500',
                        )}
                      />
                      <p className="truncate font-mono text-sm font-semibold tracking-wider text-bone-50">
                        {det.plate}
                      </p>
                    </div>
                    <span
                      className={cn(
                        'shrink-0 rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
                        det.confidence === 'high'
                          ? 'bg-granted/10 text-granted'
                          : det.confidence === 'medium'
                          ? 'bg-amber/10 text-amber'
                          : 'bg-denied/10 text-denied',
                      )}
                    >
                      {det.confidence}
                    </span>
                  </div>

                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider">
                    {det.registered ? (
                      <span className="text-granted">✓ registered</span>
                    ) : (
                      <span className="text-denied">✗ unknown plate</span>
                    )}
                    {det.fresh ? (
                      <span className="text-amber">fresh</span>
                    ) : (
                      <span className="text-bone-600">debounced</span>
                    )}
                    {det.suggested_event && (
                      <span
                        className={cn(
                          'inline-flex items-center gap-0.5',
                          det.suggested_event === 'EXIT'
                            ? 'text-amber'
                            : 'text-bone-400',
                        )}
                      >
                        {det.suggested_event === 'EXIT' ? (
                          <ArrowUpRight className="size-3" />
                        ) : (
                          <ArrowDownLeft className="size-3" />
                        )}
                        {det.suggested_event}
                      </span>
                    )}
                  </div>

                  {det.decisionLog ? (
                    <div
                      className={cn(
                        'mt-2 rounded border px-2 py-1.5 text-[11px]',
                        det.decisionLog.decision === 'GRANTED'
                          ? 'border-granted/30 bg-granted/5 text-granted'
                          : 'border-denied/30 bg-denied/5 text-denied',
                      )}
                    >
                      {det.decisionLog.decision === 'GRANTED' ? (
                        <CheckCircle2 className="mr-1 inline size-3" />
                      ) : (
                        <XCircle className="mr-1 inline size-3" />
                      )}
                      {det.decisionLog.reason}
                    </div>
                  ) : (
                    det.registered &&
                    det.fresh && (
                      <div className="mt-2 grid grid-cols-2 gap-1.5">
                        <Button
                          onClick={() => sendToPhone(det)}
                          variant="primary"
                          size="sm"
                        >
                          <Smartphone className="size-3" /> Send QR
                        </Button>
                        <Button
                          onClick={() => actOn(det)}
                          variant="ghost"
                          size="sm"
                        >
                          {det.suggested_event} →
                        </Button>
                      </div>
                    )
                  )}
                </li>
              ))}
            </ul>
          )}

          <p className="mt-3 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest text-bone-600">
            <History className="size-3" /> last 12 detections
          </p>
        </section>
      </div>

      {/* Last frame preview (debug) */}
      {lastFrame && running && (
        <details className="rounded-lg border border-ink-700 bg-ink-800/40 p-4">
          <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-widest text-bone-500 hover:text-bone-300">
            Debug · last frame sent to OCR
          </summary>
          <img
            src={lastFrame}
            alt="last frame"
            className="mt-3 max-h-64 rounded border border-ink-700"
          />
        </details>
      )}

      {/* QR Modal — shown when admin clicks "Send to phone" */}
      {qrInfo && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-lg border border-ink-700 bg-ink-900 p-6">
            <button
              onClick={() => setQrInfo(null)}
              className="absolute right-3 top-3 rounded-md p-1.5 text-bone-500 hover:bg-ink-800 hover:text-bone-200"
            >
              <X className="size-4" />
            </button>

            <div className="text-center">
              <p
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                  qrInfo.event_type === 'ENTRY'
                    ? 'border-granted/40 bg-granted/10 text-granted'
                    : 'border-amber/40 bg-amber/10 text-amber',
                )}
              >
                {qrInfo.event_type === 'ENTRY' ? (
                  <ArrowDownLeft className="size-3" />
                ) : (
                  <ArrowUpRight className="size-3" />
                )}
                {qrInfo.event_type} verification
              </p>
              <p className="mt-3 font-mono text-xl font-semibold tracking-wider text-bone-50">
                {qrInfo.plate}
              </p>
            </div>

            <div className="mt-5 grid place-items-center rounded-lg bg-bone-50 p-6">
              <QRCodeCanvas
                value={qrInfo.deep_link}
                size={220}
                level="M"
                includeMargin={false}
              />
            </div>

            <div className="mt-4 space-y-1.5 text-center">
              <p className="text-sm text-bone-300">
                Driver scans this QR with their phone camera.
              </p>
              <p className="text-xs text-bone-500">
                On their phone they enter their username, then verify with
                FaceID / fingerprint. Gate opens automatically.
              </p>
              <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
                Expires{' '}
                {new Date(qrInfo.expires_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>

            <div className="mt-4 break-all rounded border border-ink-700 bg-ink-800/40 p-3 font-mono text-[10px] text-bone-400">
              {qrInfo.deep_link}
            </div>

            <Button
              onClick={() => setQrInfo(null)}
              variant="ghost"
              className="mt-4 w-full"
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
