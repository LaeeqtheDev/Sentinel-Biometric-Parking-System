'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Car,
  Fingerprint,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { apiGet } from '@/lib/api';
import { authorizePickup, webauthnSupported } from '@/lib/webauthn';
import { cn } from '@/lib/utils';

type Phase = 'loading' | 'ready' | 'verifying' | 'success' | 'denied' | 'expired';

export default function ScanTokenPage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [phase, setPhase] = useState<Phase>('loading');
  const [tokenInfo, setTokenInfo] = useState<any>(null);
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    setSupported(webauthnSupported());
    if (!token) return;
    apiGet<any>(`/passkeys/pickup-tokens/${token}/`)
      .then((info) => {
        setTokenInfo(info);
        if (info.status === 'EXPIRED' || info.status === 'DENIED') {
          setPhase('expired');
        } else if (info.status === 'AUTHORIZED') {
          setPhase('success');
        } else {
          setPhase('ready');
        }
      })
      .catch((e) => {
        setError(e.message);
        setPhase('expired');
      });
  }, [token]);

  async function authorize() {
    setError('');
    setPhase('verifying');
    try {
      const res = await authorizePickup(token, username.trim());
      if (res.status === 'AUTHORIZED') {
        setPhase('success');
      } else {
        setError(res.detail || 'Authorization failed.');
        setPhase('denied');
      }
    } catch (e: any) {
      const raw = e?.message || String(e || 'Verification cancelled.');
      // Translate common WebAuthn / network errors into actionable hints
      let friendly = raw;
      if (
        raw.includes('NotAllowedError') ||
        raw.includes('not allowed') ||
        raw.includes('cancelled') ||
        raw.includes('canceled')
      ) {
        friendly =
          "You cancelled the prompt or the device timed out. Try again — when your phone shows FaceID/fingerprint, tap to confirm.";
      } else if (
        raw.includes('SecurityError') ||
        raw.includes('relying party') ||
        raw.includes('rpId') ||
        raw.includes('origin')
      ) {
        friendly =
          "Your phone can't access the parking system server. Make sure you're on the same Wi-Fi as the kiosk and that the URL the QR opened is reachable. If the URL says 'localhost', that's the bug — ask admin to use their LAN IP.";
      } else if (raw.includes('No matching passkey') || raw.includes('no passkeys')) {
        friendly =
          "No passkey enrolled for this username on this device. Open /driver/biometric on this phone and enroll one first.";
      } else if (raw.includes('Network')) {
        friendly =
          "Couldn't reach the server. Check your Wi-Fi and try again.";
      }
      setError(friendly);
      setPhase('denied');
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-5 py-8">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="grid size-12 place-items-center rounded-md bg-amber text-ink-950 glow-amber">
            <ShieldCheck className="size-6" strokeWidth={2.5} />
          </div>
          <p className="font-display text-xl font-semibold text-bone-50">
            Sentinel Pickup
          </p>
        </div>

        {phase === 'loading' && (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-8 text-center">
            <div className="mx-auto size-8 animate-spin rounded-full border-2 border-amber/30 border-t-amber" />
            <p className="mt-3 text-sm text-bone-400">
              Loading pickup request…
            </p>
          </div>
        )}

        {phase === 'ready' && tokenInfo && (
          <div className="space-y-5">
            <div className="rounded-lg border border-amber/40 bg-amber/5 p-5">
              <p
                className={
                  tokenInfo.event_type === 'ENTRY'
                    ? 'inline-flex items-center gap-1.5 rounded-full border border-granted/40 bg-granted/10 px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-granted'
                    : 'font-mono text-[10px] uppercase tracking-widest text-amber'
                }
              >
                {tokenInfo.event_type === 'ENTRY'
                  ? '↘ Entry verification'
                  : '· Pickup request'}
              </p>
              <div className="mt-3 flex items-center gap-3">
                <div className="grid size-12 place-items-center rounded-md border border-amber/40 bg-amber/10 text-amber">
                  <Car className="size-5" />
                </div>
                <div>
                  <p className="font-mono text-xl font-semibold tracking-wider text-bone-50">
                    {tokenInfo.vehicle.plate_number}
                  </p>
                  <p className="text-xs text-bone-400">
                    {tokenInfo.vehicle.make} {tokenInfo.vehicle.model}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-sm text-bone-300">
                {tokenInfo.event_type === 'ENTRY'
                  ? 'Verify your identity to enter the parking lot.'
                  : 'Verify your identity to pick up your car.'}
              </p>
              <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-bone-500">
                <Clock className="size-3" />
                Expires{' '}
                {new Date(tokenInfo.expires_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>

            {!supported && (
              <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
                Your browser doesn't support WebAuthn. Try Safari or Chrome
                on a recent device.
              </div>
            )}

            <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
              <p className="mb-3 text-sm text-bone-300">
                Enter your username and tap below — your device will prompt
                you for biometric verification.
              </p>
              <Input
                label="Your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. driver01"
                autoComplete="username"
              />
              {error && (
                <div className="mt-3 rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
                  {error}
                </div>
              )}
              <Button
                onClick={authorize}
                disabled={!supported || !username.trim()}
                className="mt-4 w-full"
                size="lg"
              >
                <Fingerprint className="size-4" /> Verify with biometric
              </Button>
            </div>
          </div>
        )}

        {phase === 'verifying' && (
          <div className="grid place-items-center rounded-lg border border-amber/40 bg-amber/5 p-12 text-center">
            <div className="size-14 animate-pulse rounded-full bg-amber/20 p-3">
              <Fingerprint
                className="size-8 text-amber"
                strokeWidth={1.5}
              />
            </div>
            <p className="mt-4 font-display text-lg font-semibold text-bone-50">
              Verifying…
            </p>
            <p className="mt-1 text-sm text-bone-400">
              Follow the prompt on your device.
            </p>
          </div>
        )}

        {phase === 'success' && (
          <ResultCard
            icon={CheckCircle2}
            color="granted"
            title={
              tokenInfo?.event_type === 'ENTRY'
                ? 'Entry authorized!'
                : 'Pickup authorized!'
            }
            subtitle="The gate will open momentarily. You can close this page."
          />
        )}

        {phase === 'denied' && (
          <ResultCard
            icon={XCircle}
            color="denied"
            title="Authorization denied"
            subtitle={error || 'Verification could not be completed.'}
            action={
              <Button onClick={() => setPhase('ready')} variant="ghost" className="mt-4">
                Try again
              </Button>
            }
          />
        )}

        {phase === 'expired' && (
          <ResultCard
            icon={XCircle}
            color="denied"
            title="Token expired or invalid"
            subtitle="Ask the kiosk to generate a new pickup QR code."
          />
        )}
      </div>
    </div>
  );
}

function ResultCard({
  icon: Icon,
  color,
  title,
  subtitle,
  action,
}: {
  icon: any;
  color: 'granted' | 'denied';
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border p-6 text-center',
        color === 'granted'
          ? 'border-granted/40 bg-granted/5'
          : 'border-denied/40 bg-denied/5',
      )}
    >
      <Icon
        className={cn(
          'mx-auto size-12',
          color === 'granted' ? 'text-granted' : 'text-denied',
        )}
        strokeWidth={1.5}
      />
      <h2
        className={cn(
          'mt-3 font-display text-2xl font-semibold tracking-tight',
          color === 'granted' ? 'text-granted' : 'text-denied',
        )}
      >
        {title}
      </h2>
      <p className="mt-2 text-sm text-bone-300">{subtitle}</p>
      {action}
    </div>
  );
}
