'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  ScanFace,
  Fingerprint,
  ShieldCheck,
  Trash2,
  Plus,
  Smartphone,
  AlertCircle,
  CheckCircle2,
  Camera,
  PartyPopper,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { WebcamCapture } from '@/components/WebcamCapture';
import { apiGet, apiDelete, apiPost } from '@/lib/api';
import { registerPasskey, webauthnSupported } from '@/lib/webauthn';
import { useAuth } from '@/lib/auth';
import { PasskeyCredential, fmtDateTime, cn } from '@/lib/utils';

type Mode = 'passkey' | 'face';

export default function DriverBiometricPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const isWelcome = searchParams.get('welcome') === '1';

  const [mode, setMode] = useState<Mode>('passkey');
  const [credentials, setCredentials] = useState<PasskeyCredential[]>([]);
  const [hasFace, setHasFace] = useState(false);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [nickname, setNickname] = useState('');
  const [supported, setSupported] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [faceImage, setFaceImage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const list = await apiGet<PasskeyCredential[]>('/passkeys/my/');
      setCredentials(list);
      setHasFace(Boolean(user?.has_biometric));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setSupported(webauthnSupported());
    load();
  }, []);

  async function enrollPasskey() {
    setError('');
    setSuccess('');
    setEnrolling(true);
    try {
      await registerPasskey(nickname || 'My device');
      setSuccess('✓ Passkey enrolled. You can use it for pickup verification.');
      setNickname('');
      load();
    } catch (e: any) {
      setError(e?.message || 'Enrollment cancelled or failed.');
    } finally {
      setEnrolling(false);
    }
  }

  async function enrollFace() {
    if (!faceImage) {
      setError('Please capture your face first.');
      return;
    }
    setError('');
    setSuccess('');
    setEnrolling(true);
    try {
      await apiPost('/biometrics/enroll/', {
        image_base64: faceImage,
      });
      setSuccess('✓ Face encoding stored. You can use face match as a fallback.');
      setFaceImage(null);
      setHasFace(true);
    } catch (e: any) {
      setError(e?.message || 'Face enrollment failed.');
    } finally {
      setEnrolling(false);
    }
  }

  async function removePasskey(id: number) {
    if (!confirm('Remove this passkey?')) return;
    try {
      await apiDelete(`/passkeys/credentials/${id}/`);
      setCredentials((c) => c.filter((x) => x.id !== id));
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-6">
      {isWelcome && (
        <div className="rounded-lg border border-amber/40 bg-amber/5 p-4">
          <div className="flex items-start gap-3">
            <PartyPopper className="mt-0.5 size-5 shrink-0 text-amber" />
            <div>
              <p className="font-display text-base font-semibold text-bone-50">
                Welcome to Sentinel!
              </p>
              <p className="mt-1 text-sm text-bone-300">
                One last step — set up biometric access. Choose either option
                below. <strong className="text-amber">Passkey</strong> is
                recommended (fingerprint or FaceID on your phone).{' '}
                <strong className="text-amber">Face match</strong> works as a
                fallback if your device doesn't support passkeys.
              </p>
            </div>
          </div>
        </div>
      )}

      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber">
          · Biometric setup
        </p>
        <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-bone-50 sm:text-3xl">
          Choose your verification method
        </h1>
        <p className="mt-2 text-sm text-bone-400">
          You can enroll one or both. The system will try passkey first, then
          fall back to face match.
        </p>
      </div>

      {/* Mode tabs */}
      <div className="grid grid-cols-2 gap-2 rounded-lg border border-ink-700 bg-ink-800/40 p-1">
        <ModeTab
          active={mode === 'passkey'}
          onClick={() => setMode('passkey')}
          icon={Fingerprint}
          label="Passkey"
          hint="Fingerprint / FaceID"
          enrolled={credentials.length}
          recommended
        />
        <ModeTab
          active={mode === 'face'}
          onClick={() => setMode('face')}
          icon={ScanFace}
          label="Face match"
          hint="Camera-based"
          enrolled={hasFace ? 1 : 0}
        />
      </div>

      {/* Universal feedback area */}
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

      {/* PASSKEY mode */}
      {mode === 'passkey' && (
        <>
          {!supported && (
            <div className="flex items-start gap-3 rounded-lg border border-denied/30 bg-denied/5 p-4 text-sm text-denied">
              <AlertCircle className="mt-0.5 size-5 shrink-0" />
              <div>
                <p className="font-medium">WebAuthn not supported</p>
                <p className="mt-1 text-bone-400">
                  Your browser doesn't support passkeys. Use Face match
                  instead, or open this page on a phone (iOS 16+ / Android 8+).
                </p>
              </div>
            </div>
          )}

          {/* Existing passkeys */}
          <section>
            <h3 className="mb-3 font-mono text-[11px] uppercase tracking-widest text-bone-500">
              Your passkeys
            </h3>
            {loading ? (
              <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-6 text-center text-sm text-bone-500">
                Loading…
              </div>
            ) : credentials.length === 0 ? (
              <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-6 text-center">
                <ShieldCheck className="mx-auto size-8 text-bone-500" />
                <p className="mt-3 text-sm text-bone-400">No passkeys yet.</p>
              </div>
            ) : (
              <ul className="space-y-2">
                {credentials.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-800/40 p-4"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="grid size-10 shrink-0 place-items-center rounded-md border border-granted/40 bg-granted/10 text-granted">
                        <Smartphone className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-bone-100">
                          {c.nickname || 'Untitled passkey'}
                        </p>
                        <p className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
                          Enrolled {fmtDateTime(c.created_at)}
                          {c.last_used_at && (
                            <> · last used {fmtDateTime(c.last_used_at)}</>
                          )}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => removePasskey(c.id)}
                      className="rounded-md p-2 text-bone-500 transition-colors hover:bg-denied/10 hover:text-denied"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
            <div className="mb-4 flex items-center gap-2">
              <Fingerprint className="size-4 text-amber" />
              <h3 className="font-display text-base font-semibold text-bone-50">
                Add a passkey
              </h3>
            </div>
            <p className="mb-4 text-xs text-bone-400">
              Tap below — your device prompts for fingerprint, FaceID, or your
              device PIN. The biometric data <strong>never</strong> leaves
              your device.
            </p>
            <Input
              label="Nickname (optional)"
              placeholder="e.g. My iPhone"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
            />
            <Button
              onClick={enrollPasskey}
              disabled={!supported || enrolling}
              loading={enrolling}
              className="mt-4 w-full"
              size="lg"
            >
              <Plus className="size-4" /> Enroll device biometric
            </Button>
          </section>
        </>
      )}

      {/* FACE mode */}
      {mode === 'face' && (
        <>
          <section className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
            <div className="mb-3 flex items-center gap-2">
              <ScanFace className="size-4 text-amber" />
              <h3 className="font-display text-base font-semibold text-bone-50">
                Face enrollment
              </h3>
              {hasFace && (
                <span className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-granted/40 bg-granted/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-granted">
                  <CheckCircle2 className="size-3" /> Enrolled
                </span>
              )}
            </div>
            <p className="mb-4 text-xs text-bone-400">
              Capture a clear photo of your face in good lighting. We compute
              a 128-number vector from your face and store only that —{' '}
              <strong>not</strong> the photo itself.
            </p>
            <WebcamCapture
              value={faceImage}
              onCapture={setFaceImage}
              placeholder="Look directly at the camera, then capture."
            />
            <Button
              onClick={enrollFace}
              disabled={!faceImage || enrolling}
              loading={enrolling}
              className="mt-4 w-full"
              size="lg"
            >
              <Camera className="size-4" />{' '}
              {hasFace ? 'Update face encoding' : 'Enroll face'}
            </Button>
          </section>
        </>
      )}
    </div>
  );
}

function ModeTab({
  active,
  onClick,
  icon: Icon,
  label,
  hint,
  enrolled,
  recommended,
}: {
  active: boolean;
  onClick: () => void;
  icon: any;
  label: string;
  hint: string;
  enrolled: number;
  recommended?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'relative flex flex-col items-start gap-1 rounded-md border p-3 text-left transition-colors',
        active
          ? 'border-amber bg-amber/10'
          : 'border-transparent hover:bg-ink-700/40',
      )}
    >
      <div className="flex w-full items-center gap-2">
        <Icon className={cn('size-4', active ? 'text-amber' : 'text-bone-400')} />
        <span
          className={cn(
            'text-sm font-medium',
            active ? 'text-bone-50' : 'text-bone-300',
          )}
        >
          {label}
        </span>
        {recommended && (
          <span className="ml-auto rounded-full bg-amber/20 px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider text-amber">
            Recommended
          </span>
        )}
      </div>
      <p className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
        {hint}
      </p>
      {enrolled > 0 && (
        <p className="font-mono text-[10px] text-granted">
          ✓ {enrolled} enrolled
        </p>
      )}
    </button>
  );
}
