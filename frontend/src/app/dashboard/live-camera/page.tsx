'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Webcam from 'react-webcam';
import {
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle2,
  XCircle,
  X,
  Smartphone,
  UserPlus,
  Pencil,
  HelpCircle,
  Power,
  ScanFace,
  Car,
} from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiGet, apiPost } from '@/lib/api';
import { Vehicle, cn } from '@/lib/utils';
import dynamic from 'next/dynamic';

const QRCodeSVG = dynamic(
  () => import('qrcode.react').then((m) => m.QRCodeSVG),
  { ssr: false, loading: () => <div className="size-[220px] bg-ink-800" /> },
);

type GateRole = 'ENTRY' | 'EXIT';

interface FaceMatch {
  detected: boolean;
  matched_user: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    trust_level: string;
  } | null;
  distance: number | null;
}

interface Detection {
  id: string;
  gate: GateRole;
  plate: string;
  confidence: 'high' | 'medium' | 'low' | 'none';
  registered: boolean;
  fresh: boolean;
  vehicle?: Vehicle | null;
  active_session?: { id: number; entry_time: string } | null;
  suggested_event?: GateRole;
  timestamp: number;
  decisionLog?: { decision: string; reason: string };
  snapshot?: string;
  candidates?: { text: string; score: number; engine: string }[];
  face?: FaceMatch;
  gatePhase?: 'opening' | 'open' | 'closing' | 'closed';
}

const POLL_MS = 2500;

export default function LiveCameraPage() {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [entryDeviceId, setEntryDeviceId] = useState<string>('');
  const [exitDeviceId, setExitDeviceId] = useState<string>('');
  const [entryActive, setEntryActive] = useState(true);
  const [exitActive, setExitActive] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [error, setError] = useState('');

  // Autonomous EXIT mode — when ON, the EXIT camera auto-decides:
  //   plate registered + active session + face matches  → auto-grant
  //   plate registered + active session + no face match → auto-show QR
  const [autonomousExit, setAutonomousExit] = useState(true);
  // Track which detections we've already auto-acted on so we don't re-fire
  const autoActedRef = useRef<Set<string>>(new Set());

  const [qrInfo, setQrInfo] = useState<{
    deep_link: string;
    plate: string;
    event_type: GateRole;
    token?: string;
    detectionId?: string;
  } | null>(null);

  const [walkUpFor, setWalkUpFor] = useState<Detection | null>(null);
  const [walkUpPlate, setWalkUpPlate] = useState('');
  const [walkUpForm, setWalkUpForm] = useState({
    make: '', model: '', color: '', vehicle_type: 'CAR',
    new_username: '', new_password: '', first_name: '', last_name: '', phone: '',
  });
  const [walkUpSubmitting, setWalkUpSubmitting] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  // Enumerate cameras
  useEffect(() => {
    (async () => {
      try {
        await navigator.mediaDevices.getUserMedia({ video: true });
      } catch {/* */ }
      const all = await navigator.mediaDevices.enumerateDevices();
      const cams = all.filter((d) => d.kind === 'videoinput');
      setDevices(cams);
      if (cams[0] && !entryDeviceId) setEntryDeviceId(cams[0].deviceId);
      if (cams[1] && !exitDeviceId) {
        setExitDeviceId(cams[1].deviceId);
        setExitActive(true);
      }
    })();
  }, []);

  // Autonomous EXIT auto-actions — fires when a new EXIT detection arrives
  // that satisfies all conditions for self-service.
  useEffect(() => {
    if (!autonomousExit) return;
    const latest = detections[0];
    if (!latest) return;
    if (latest.gate !== 'EXIT') return;
    if (!latest.fresh) return;                  // already acted recently
    if (!latest.registered) return;             // unknown plate — admin must intervene
    if (!latest.active_session) return;         // can't exit if not parked
    if (latest.decisionLog) return;             // already has a decision
    if (autoActedRef.current.has(latest.id)) return;
    autoActedRef.current.add(latest.id);

    if (latest.face?.matched_user) {
      // Plate + face match → auto-grant immediately (no admin click)
      actOnDetection(latest);
    } else {
      // Face missing or no match → display QR for the driver to verify on the spot
      autoSendQR(latest);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detections, autonomousExit]);

  function startEdit(det: Detection) {
    setEditingId(det.id);
    setEditValue(det.plate === '(unreadable)' ? '' : det.plate);
  }

  async function commitEdit(det: Detection) {
    const corrected = editValue.trim().toUpperCase();
    if (!corrected) { setEditingId(null); return; }
    setEditingId(null);
    try {
      const v = await apiGet<any>(`/vehicles/lookup/${encodeURIComponent(corrected)}/`).catch(() => null);
      const vehicle = v && v.id ? v : null;
      let suggested: GateRole = det.gate;
      let active: { id: number; entry_time: string } | null = null;
      if (vehicle) {
        const s = await apiGet<any>(`/parking/active-for/${encodeURIComponent(corrected)}/`).catch(() => null);
        if (s && s.id) {
          active = { id: s.id, entry_time: s.entry_time };
          suggested = 'EXIT';
        }
      }
      setDetections((prev) => prev.map((d) =>
        d.id === det.id
          ? { ...d, plate: corrected, registered: !!vehicle, fresh: true, vehicle, active_session: active, suggested_event: suggested, confidence: 'high', decisionLog: undefined }
          : d
      ));
    } catch {
      setDetections((prev) => prev.map((d) =>
        d.id === det.id ? { ...d, plate: corrected, fresh: true, confidence: 'high' } : d
      ));
    }
  }

  // Helper: drive the gate animation phases on a specific detection
  function triggerGateAnimation(detectionId: string, decision: string, reason: string) {
    setDetections((prev) =>
      prev.map((d) =>
        d.id === detectionId
          ? { ...d, decisionLog: { decision, reason }, gatePhase: decision === 'GRANTED' ? 'opening' : undefined }
          : d,
      ),
    );
    if (decision === 'GRANTED') {
      setTimeout(() => setDetections((p) => p.map((d) => d.id === detectionId ? { ...d, gatePhase: 'open' } : d)), 1200);
      setTimeout(() => setDetections((p) => p.map((d) => d.id === detectionId ? { ...d, gatePhase: 'closing' } : d)), 4200);
      setTimeout(() => setDetections((p) => p.map((d) => d.id === detectionId ? { ...d, gatePhase: 'closed' } : d)), 5400);
    }
  }

  // Internal: trigger verify-entry/exit + gate animation on a specific detection
  async function actOnDetection(det: Detection) {
    setError('');
    try {
      const event = det.suggested_event || det.gate;
      const endpoint = event === 'EXIT' ? '/access/verify-exit/' : '/access/verify-entry/';
      const res = await apiPost<any>(endpoint, { plate_number: det.plate, via: 'live_camera' });
      triggerGateAnimation(det.id, res.decision, res.reason);
    } catch (e: any) { setError(e.message); }
  }

  // Internal: auto-issue a pickup token and show the QR (used by autonomous EXIT)
  async function autoSendQR(det: Detection) {
    if (!det.registered || !det.vehicle) return;
    setError('');
    try {
      const res = await apiPost<any>('/passkeys/pickup-tokens/', {
        vehicle_id: det.vehicle.id,
        event_type: det.suggested_event || det.gate,
      });
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      setQrInfo({
        deep_link: `${origin}/driver/scan/${res.token}`,
        plate: det.plate,
        event_type: res.event_type,
        token: res.token,
        detectionId: det.id,
      });
    } catch (e: any) { setError(e.message); }
  }

  // Wrappers used by the manual UI buttons
  async function actOn(det: Detection) { return actOnDetection(det); }
  async function sendToPhone(det: Detection) { return autoSendQR(det); }

  // Poll the QR pickup token while a QR modal is open. When the driver
  // scans + verifies on their phone, status flips to AUTHORIZED — at that
  // point we close the modal and play the gate animation on the original
  // detection so the admin sees the same outcome as the driver.
  useEffect(() => {
    if (!qrInfo?.token) return;
    let stopped = false;
    const id = setInterval(async () => {
      if (stopped) return;
      try {
        const res = await apiGet<any>(`/passkeys/pickup-tokens/${qrInfo.token}/`);
        if (res.status === 'AUTHORIZED') {
          stopped = true;
          clearInterval(id);
          if (qrInfo.detectionId) {
            triggerGateAnimation(qrInfo.detectionId, 'GRANTED', 'Driver verified via QR scan — gate opening.');
          }
          setTimeout(() => setQrInfo(null), 600); // Brief delay so admin sees the transition
        } else if (res.status === 'EXPIRED' || res.status === 'CONSUMED') {
          stopped = true;
          clearInterval(id);
        }
      } catch {/* keep polling */ }
    }, 2000);
    return () => { stopped = true; clearInterval(id); };
  }, [qrInfo?.token]);

  function openWalkUp(det: Detection) {
    setWalkUpFor(det);
    setWalkUpPlate(det.plate === '(unreadable)' ? '' : det.plate);
  }

  async function submitWalkUp() {
    if (!walkUpFor) return;
    const plate = walkUpPlate.trim();
    if (!plate) { setError('Type the plate number first.'); return; }
    setWalkUpSubmitting(true);
    setError('');
    try {
      await apiPost('/vehicles/walk-up/', {
        plate_number: plate, ...walkUpForm,
        ...(walkUpForm.new_username.trim() ? {
          driver: {
            username: walkUpForm.new_username.trim(),
            password: walkUpForm.new_password,
            first_name: walkUpForm.first_name,
            last_name: walkUpForm.last_name,
            phone: walkUpForm.phone,
          },
        } : {}),
      });
      setDetections((prev) => prev.map((d) =>
        d.id === walkUpFor.id
          ? { ...d, plate: plate.toUpperCase(), registered: true, decisionLog: { decision: 'GRANTED', reason: 'Vehicle registered. Click ENTRY.' } }
          : d
      ));
      setWalkUpFor(null);
      setWalkUpPlate('');
      setWalkUpForm({ make: '', model: '', color: '', vehicle_type: 'CAR', new_username: '', new_password: '', first_name: '', last_name: '', phone: '' });
    } catch (e: any) { setError(e.message); }
    finally { setWalkUpSubmitting(false); }
  }

  return (
    <>
      <Topbar title="Live Camera" subtitle="Continuous OCR + face match — automatic gate decisions." />
      <main className="flex-1 space-y-4 p-6 lg:p-8">
        {/* Autonomous EXIT toggle banner */}
        <div className="rounded-lg border border-amber/40 bg-amber/5 p-4">
          <div className="flex items-start gap-3">
            <ScanFace className="mt-0.5 size-5 shrink-0 text-amber" />
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <p className="font-mono text-[11px] uppercase tracking-widest text-amber">
                  · Autonomous exit kiosk
                </p>
                <label className="inline-flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={autonomousExit}
                    onChange={(e) => setAutonomousExit(e.target.checked)}
                    className="size-4 rounded border-ink-600 bg-ink-900 text-amber focus:ring-amber"
                  />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-bone-300">
                    {autonomousExit ? 'enabled' : 'disabled'}
                  </span>
                </label>
              </div>
              <p className="mt-1 text-xs text-bone-400">
                When ON, the EXIT camera self-decides:{' '}
                <span className="text-bone-200">plate + face match → gate opens automatically</span>.{' '}
                If face is missing or doesn't match, a{' '}
                <span className="text-bone-200">QR code appears on screen</span> for the driver to verify on the spot with their phone. ENTRY camera always stays manual (admin reviews unknown plates).
              </p>
            </div>
          </div>
        </div>

        {/* Help banner */}
        <div className="rounded-lg border border-ink-700 bg-ink-800/40">
          <button
            onClick={() => setShowHelp((s) => !s)}
            className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm"
          >
            <span className="flex items-center gap-2 font-medium text-bone-200">
              <HelpCircle className="size-4 text-amber" /> How does this page work?
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
              {showHelp ? 'hide' : 'show'}
            </span>
          </button>
          {showHelp && (
            <div className="space-y-2 border-t border-ink-700 px-4 py-3 text-xs text-bone-400">
              <p>Each camera below polls every {POLL_MS / 1000}s — captures a frame, runs OCR + face detection, looks up the plate in your DB.</p>
              <p><strong className="text-bone-200">ENTRY</strong> camera watches arrivals (admin-supervised). <strong className="text-bone-200">EXIT</strong> camera watches departures (autonomous when toggle above is ON).</p>
              <p>If OCR misreads, click the pencil to correct it. If the plate isn't registered, click "Register at gate" to onboard the driver on the spot.</p>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">{error}</div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <CameraPanel
            role="ENTRY"
            active={entryActive}
            onToggle={() => setEntryActive((a) => !a)}
            devices={devices}
            deviceId={entryDeviceId}
            onDeviceChange={setEntryDeviceId}
            onDetection={(d) => setDetections((p) => [d, ...p].slice(0, 14))}
          />
          <CameraPanel
            role="EXIT"
            active={exitActive}
            onToggle={() => setExitActive((a) => !a)}
            devices={devices}
            deviceId={exitDeviceId}
            onDeviceChange={setExitDeviceId}
            onDetection={(d) => setDetections((p) => [d, ...p].slice(0, 14))}
          />
        </div>

        {/* Detection feed */}
        <section className="rounded-lg border border-ink-700 bg-ink-800/40">
          <div className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
            <h2 className="font-display text-base font-semibold text-bone-50">Detection feed</h2>
            <span className="font-mono text-[10px] uppercase tracking-widest text-bone-500">{detections.length}</span>
          </div>
          {detections.length === 0 ? (
            <p className="p-8 text-center text-sm text-bone-500">No detections yet. Make sure a camera is on and a plate is in frame.</p>
          ) : (
            <ul className="divide-y divide-ink-700">
              {detections.map((det) => (
                <DetectionItem
                  key={det.id}
                  det={det}
                  isEditing={editingId === det.id}
                  editValue={editValue}
                  setEditValue={setEditValue}
                  onStartEdit={() => startEdit(det)}
                  onCommitEdit={() => commitEdit(det)}
                  onCancelEdit={() => setEditingId(null)}
                  onAct={() => actOn(det)}
                  onSendQR={() => sendToPhone(det)}
                  onWalkUp={() => openWalkUp(det)}
                  onPickAlt={(t) => { setEditValue(t); setEditingId(det.id); }}
                />
              ))}
            </ul>
          )}
        </section>
      </main>

      {/* QR modal */}
      {qrInfo && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-4 backdrop-blur-sm">
          <div className="relative max-w-md rounded-lg border border-ink-700 bg-ink-900 p-6 text-center">
            <button onClick={() => setQrInfo(null)} className="absolute right-3 top-3 rounded-md p-1.5 text-bone-500 hover:bg-ink-800"><X className="size-4" /></button>
            <p className="font-mono text-[10px] uppercase tracking-widest text-amber">· {qrInfo.event_type} verification</p>
            <h3 className="mt-1 font-display text-lg font-semibold text-bone-50">Driver — scan with phone</h3>
            <p className="mt-1 font-mono text-sm tracking-wider text-bone-300">{qrInfo.plate}</p>
            <div className="mx-auto mt-4 inline-block rounded-md bg-bone-50 p-3">
              <QRCodeSVG value={qrInfo.deep_link} size={220} />
            </div>
            <p className="mt-3 break-all px-2 font-mono text-[10px] text-bone-500">{qrInfo.deep_link}</p>
            {/* Live status — admin sees this update when driver scans */}
            {qrInfo.token && (
              <div className="mt-4 flex items-center justify-center gap-2 rounded-md border border-amber/30 bg-amber/5 px-3 py-1.5">
                <span className="size-1.5 animate-pulse-soft rounded-full bg-amber" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-amber">
                  waiting for driver to verify…
                </span>
              </div>
            )}
            <Button onClick={() => setQrInfo(null)} variant="ghost" className="mt-4 w-full">Close</Button>
          </div>
        </div>
      )}

      {/* Walk-up modal */}
      {walkUpFor && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-4 backdrop-blur-sm">
          <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg border border-ink-700 bg-ink-900 p-6">
            <button onClick={() => setWalkUpFor(null)} className="absolute right-3 top-3 rounded-md p-1.5 text-bone-500 hover:bg-ink-800"><X className="size-4" /></button>
            <p className="font-mono text-[10px] uppercase tracking-widest text-amber">· Walk-up registration</p>
            <h2 className="mt-1 font-display text-xl font-semibold text-bone-50">Register vehicle at gate</h2>
            {walkUpFor.snapshot && (
              <img src={walkUpFor.snapshot} alt="snap" className="mt-3 w-full rounded border border-ink-700" />
            )}
            <div className="mt-3 space-y-3">
              <Input label="Plate number *" value={walkUpPlate} onChange={(e) => setWalkUpPlate(e.target.value.toUpperCase())} placeholder="AAP-1478" className="font-mono tracking-widest" />
              <Select label="Vehicle type" value={walkUpForm.vehicle_type} onChange={(e) => setWalkUpForm({ ...walkUpForm, vehicle_type: e.target.value })}>
                <option value="CAR">Car</option>
                <option value="BIKE">Motorcycle</option>
                <option value="SUV">SUV</option>
                <option value="TRUCK">Truck</option>
                <option value="OTHER">Other</option>
              </Select>
              <div className="grid grid-cols-3 gap-2">
                <Input label="Make" value={walkUpForm.make} onChange={(e) => setWalkUpForm({ ...walkUpForm, make: e.target.value })} />
                <Input label="Model" value={walkUpForm.model} onChange={(e) => setWalkUpForm({ ...walkUpForm, model: e.target.value })} />
                <Input label="Color" value={walkUpForm.color} onChange={(e) => setWalkUpForm({ ...walkUpForm, color: e.target.value })} />
              </div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">Driver (optional)</p>
              <div className="grid grid-cols-2 gap-2">
                <Input label="First name" value={walkUpForm.first_name} onChange={(e) => setWalkUpForm({ ...walkUpForm, first_name: e.target.value })} />
                <Input label="Last name" value={walkUpForm.last_name} onChange={(e) => setWalkUpForm({ ...walkUpForm, last_name: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Input label="Username" value={walkUpForm.new_username} onChange={(e) => setWalkUpForm({ ...walkUpForm, new_username: e.target.value })} />
                <Input label="Password" type="password" value={walkUpForm.new_password} onChange={(e) => setWalkUpForm({ ...walkUpForm, new_password: e.target.value })} />
              </div>
            </div>
            <div className="mt-5 flex gap-2">
              <Button onClick={() => setWalkUpFor(null)} variant="ghost" className="flex-1">Cancel</Button>
              <Button onClick={submitWalkUp} loading={walkUpSubmitting} className="flex-1"><UserPlus className="size-4" /> Register & continue</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// =================== Camera Panel ===================
function CameraPanel({
  role, active, onToggle, devices, deviceId, onDeviceChange, onDetection,
}: {
  role: GateRole; active: boolean; onToggle: () => void;
  devices: MediaDeviceInfo[]; deviceId: string;
  onDeviceChange: (id: string) => void;
  onDetection: (d: Detection) => void;
}) {
  const webcamRef = useRef<Webcam>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const tick = useCallback(async () => {
    if (!active || busy || !webcamRef.current) return;
    const shot = webcamRef.current.getScreenshot();
    if (!shot) return;
    setBusy(true);
    try {
      const res = await apiPost<any>('/access/live-detect/', { plate_image_base64: shot });
      // Push detection IF backend returned anything interesting
      const hasSomething = res.plate || (res.candidates && res.candidates.length > 0) || res.face?.detected;
      if (hasSomething) {
        onDetection({
          id: `${Date.now()}-${Math.random()}`,
          gate: role,
          plate: res.plate || '(unreadable)',
          confidence: res.confidence || 'none',
          registered: !!res.registered,
          fresh: !!res.fresh,
          vehicle: res.vehicle,
          active_session: res.active_session,
          suggested_event: res.suggested_event || role,
          timestamp: Date.now(),
          snapshot: shot,
          candidates: res.candidates || [],
          face: res.face,
        });
      }
      setErr('');
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  }, [active, busy, role, onDetection]);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(tick, POLL_MS);
    return () => clearInterval(id);
  }, [active, tick]);

  const Icon = role === 'ENTRY' ? ArrowDownLeft : ArrowUpRight;

  return (
    <section className={cn('rounded-lg border bg-ink-800/40 transition-colors', active ? 'border-amber/40' : 'border-ink-700')}>
      <header className="flex items-center justify-between border-b border-ink-700 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Icon className="size-4 text-amber" />
          <h3 className="font-display text-sm font-semibold text-bone-50">{role} camera</h3>
          {active && (
            <span className="inline-flex items-center gap-1 rounded-full bg-granted/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-granted">
              <span className="size-1.5 animate-pulse-soft rounded-full bg-granted" /> live
            </span>
          )}
          {busy && active && <span className="font-mono text-[9px] text-bone-500">scanning…</span>}
        </div>
        <button
          onClick={onToggle}
          className={cn(
            'rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-wider',
            active ? 'border-denied/40 bg-denied/10 text-denied' : 'border-amber/40 bg-amber/10 text-amber',
          )}
        >
          <Power className="mr-1 inline size-3" />
          {active ? 'Off' : 'On'}
        </button>
      </header>
      {devices.length > 0 && (
        <div className="border-b border-ink-700 px-4 py-2">
          <select
            value={deviceId}
            onChange={(e) => onDeviceChange(e.target.value)}
            className="w-full rounded border border-ink-700 bg-ink-900 px-2 py-1 text-xs text-bone-200 focus:border-amber focus:outline-none"
          >
            {devices.map((d, i) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Camera ${i + 1}`}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="relative aspect-video bg-ink-950">
        {active ? (
          <Webcam
            ref={webcamRef}
            audio={false}
            screenshotFormat="image/jpeg"
            screenshotQuality={0.92}
            videoConstraints={deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'environment' }}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="grid h-full place-items-center text-bone-600">
            <div className="text-center">
              <Power className="mx-auto size-8" />
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wider">camera off</p>
            </div>
          </div>
        )}
      </div>
      {err && <div className="border-t border-denied/30 bg-denied/10 px-4 py-1.5 font-mono text-[10px] text-denied">{err}</div>}
    </section>
  );
}

// =================== Detection Item ===================
function DetectionItem({
  det, isEditing, editValue, setEditValue,
  onStartEdit, onCommitEdit, onCancelEdit,
  onAct, onSendQR, onWalkUp, onPickAlt,
}: {
  det: Detection; isEditing: boolean; editValue: string;
  setEditValue: (v: string) => void;
  onStartEdit: () => void; onCommitEdit: () => void; onCancelEdit: () => void;
  onAct: () => void; onSendQR: () => void; onWalkUp: () => void;
  onPickAlt: (text: string) => void;
}) {
  return (
    <li className="p-3">
      <div className="flex gap-3">
        {det.snapshot && (
          <img src={det.snapshot} alt="frame" className="size-14 shrink-0 rounded border border-ink-700 object-cover" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {/* Gate badge */}
            <span className={cn(
              'rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
              det.gate === 'ENTRY' ? 'bg-amber/10 text-amber' : 'bg-amber/10 text-amber',
            )}>{det.gate}</span>
            <Car className={cn('size-4 shrink-0', det.registered ? 'text-amber' : 'text-bone-500')} />
            {isEditing ? (
              <>
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value.toUpperCase())}
                  onKeyDown={(e) => { if (e.key === 'Enter') onCommitEdit(); if (e.key === 'Escape') onCancelEdit(); }}
                  className="min-w-0 flex-1 rounded border border-amber bg-ink-900 px-2 py-1 font-mono text-sm tracking-wider text-bone-50 focus:outline-none"
                  placeholder="AAP-1478"
                />
                <button onClick={onCommitEdit} className="rounded bg-amber px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-ink-950 hover:bg-amber/80">OK</button>
              </>
            ) : (
              <>
                <p className="min-w-0 flex-1 truncate font-mono text-sm font-semibold tracking-wider text-bone-50">{det.plate}</p>
                <button onClick={onStartEdit} className="rounded p-1 text-bone-500 hover:bg-ink-700 hover:text-amber" title="Correct plate"><Pencil className="size-3" /></button>
              </>
            )}
            <span className={cn(
              'shrink-0 rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
              det.confidence === 'high' ? 'bg-granted/10 text-granted'
              : det.confidence === 'medium' ? 'bg-amber/10 text-amber' : 'bg-denied/10 text-denied',
            )}>{det.confidence}</span>
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider">
            {det.registered ? <span className="text-granted">✓ registered</span> : <span className="text-denied">✗ unknown</span>}
            {det.fresh ? <span className="text-amber">fresh</span> : <span className="text-bone-600">debounced</span>}
            {/* Face match indicator */}
            {det.face?.matched_user ? (
              <span className="inline-flex items-center gap-1 text-granted">
                <ScanFace className="size-3" /> matched @{det.face.matched_user.username}
              </span>
            ) : det.face?.detected ? (
              <span className="inline-flex items-center gap-1 text-amber">
                <ScanFace className="size-3" /> face seen, no match
              </span>
            ) : null}
          </div>

          {/* OCR alternates */}
          {det.candidates && det.candidates.length > 1 && (
            <details className="mt-1.5">
              <summary className="cursor-pointer font-mono text-[9px] uppercase tracking-wider text-bone-500 hover:text-bone-300">
                {det.candidates.length} OCR alternates
              </summary>
              <div className="mt-1 flex flex-wrap gap-1">
                {det.candidates.slice(0, 6).map((c) => (
                  <button
                    key={c.text}
                    onClick={() => onPickAlt(c.text)}
                    className="rounded border border-ink-600 bg-ink-900 px-1.5 py-0.5 font-mono text-[10px] text-bone-300 hover:border-amber hover:text-amber"
                    title={`${c.engine} · score ${c.score}`}
                  >{c.text}</button>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>

      {det.decisionLog ? (
        <>
          <div className={cn(
            'mt-2 rounded border px-2 py-1.5 text-[11px]',
            det.decisionLog.decision === 'GRANTED' ? 'border-granted/30 bg-granted/5 text-granted' : 'border-denied/30 bg-denied/5 text-denied',
          )}>
            {det.decisionLog.decision === 'GRANTED' ? <CheckCircle2 className="mr-1 inline size-3" /> : <XCircle className="mr-1 inline size-3" />}
            {det.decisionLog.reason}
          </div>
          {det.gatePhase && <GateAnimation phase={det.gatePhase} />}
        </>
      ) : det.registered && det.fresh ? (
        <div className="mt-2 grid grid-cols-2 gap-1.5">
          <Button onClick={onSendQR} variant="primary" size="sm"><Smartphone className="size-3" /> Send QR</Button>
          <Button onClick={onAct} variant="ghost" size="sm">{det.suggested_event} →</Button>
        </div>
      ) : (
        // Register button ONLY on ENTRY camera — you can't register a vehicle
        // that's trying to leave (no active session = it never entered).
        !det.registered && det.gate === 'ENTRY' ? (
          <Button onClick={onWalkUp} variant="ghost" size="sm" className="mt-2 w-full border-amber/30 text-amber hover:bg-amber/10">
            <UserPlus className="size-3" /> Register at gate
          </Button>
        ) : !det.registered && det.gate === 'EXIT' ? (
          <div className="mt-2 rounded border border-denied/30 bg-denied/5 px-2 py-1.5 text-[11px] text-denied">
            <XCircle className="mr-1 inline size-3" />
            Unknown vehicle at exit — not registered or never entered. Flag for security.
          </div>
        ) : null
      )}
    </li>
  );
}

// =================== Gate Animation ===================
function GateAnimation({ phase }: { phase: 'opening' | 'open' | 'closing' | 'closed' }) {
  const config = {
    opening:  { label: '⚙ GATE OPENING…', color: 'text-amber',   pct: 50, pulse: true  },
    open:     { label: '✓ GATE OPEN — vehicle passing', color: 'text-granted', pct: 100, pulse: false },
    closing:  { label: '⚙ GATE CLOSING…', color: 'text-amber',   pct: 30, pulse: true  },
    closed:   { label: '✓ GATE CLOSED — cycle complete', color: 'text-bone-400', pct: 0, pulse: false },
  } as const;
  const c = config[phase];
  return (
    <div className="mt-2 rounded border border-ink-700 bg-ink-900/60 px-3 py-2">
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
