'use client';

import { FormEvent, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldCheck, ArrowRight, Camera, ScanFace, Cpu } from 'lucide-react';
import { Input } from '@/components/Input';
import { Button } from '@/components/Button';
import { useAuth } from '@/lib/auth';
import { ApiError } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const { login, user, loading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && user) router.replace('/dashboard');
  }, [user, loading, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(username, password);
      router.replace('/dashboard');
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.status === 401
            ? 'Invalid credentials.'
            : err.message
          : 'Could not connect to server.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative grid min-h-screen lg:grid-cols-5">
      {/* ----- Left: brand showcase ----- */}
      <section className="relative hidden overflow-hidden border-r border-ink-700 bg-ink-900 lg:col-span-3 lg:block">
        {/* Grid background */}
        <div className="absolute inset-0 border-grid opacity-50" />
        {/* Amber glow */}
        <div className="absolute -left-32 top-1/3 h-96 w-96 rounded-full bg-amber/20 blur-[120px]" />
        <div className="absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-amber/10 blur-[120px]" />

        <div className="relative flex h-full flex-col justify-between p-12">
          {/* Top brand mark */}
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-md bg-amber text-ink-950 glow-amber">
              <ShieldCheck className="size-5" strokeWidth={2.5} />
            </div>
            <div className="leading-tight">
              <p className="font-display text-lg font-semibold text-bone-50">
                Sentinel
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-bone-500">
                Biometric Parking · Surveillance
              </p>
            </div>
          </div>

          {/* Headline */}
          <div className="max-w-xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">
              · Smart Parking Surveillance & Recognition
            </p>
            <h2 className="mt-5 font-display text-5xl font-semibold leading-[1.05] tracking-tight text-bone-50 text-balance">
              Two layers of identity.
              <br />
              <span className="text-amber-glow">Zero room for doubt.</span>
            </h2>
            <p className="mt-6 max-w-md text-bone-400 text-balance">
              Combining license-plate recognition with biometric verification to
              automate vehicle access — secure, contactless, and entirely
              hands-off.
            </p>
          </div>

          {/* Feature row */}
          <div className="grid grid-cols-3 gap-4 border-t border-ink-700 pt-6">
            {[
              { icon: Camera, label: 'OCR Plate Capture' },
              { icon: ScanFace, label: 'Biometric Match' },
              { icon: Cpu, label: 'Auto Gate Control' },
            ].map(({ icon: I, label }) => (
              <div key={label} className="flex items-center gap-2.5">
                <div className="grid size-8 place-items-center rounded-md border border-ink-600 bg-ink-800/60 text-amber">
                  <I className="size-4" />
                </div>
                <span className="font-mono text-[11px] uppercase tracking-wider text-bone-400">
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ----- Right: form ----- */}
      <section className="relative grid place-items-center px-6 py-12 lg:col-span-2">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-md bg-amber text-ink-950 glow-amber">
              <ShieldCheck className="size-5" strokeWidth={2.5} />
            </div>
            <p className="font-display text-lg font-semibold text-bone-50">
              Sentinel
            </p>
          </div>

          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">
            · Sign in
          </p>
          <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight text-bone-50">
            Operator access
          </h1>
          <p className="mt-2 text-sm text-bone-400">
            Enter your administrator credentials to continue.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <Input
              label="Username"
              name="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              autoFocus
            />
            <Input
              label="Password"
              name="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />

            {error && (
              <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
                {error}
              </div>
            )}

            <Button
              type="submit"
              size="lg"
              loading={submitting}
              className="w-full"
            >
              Authenticate
              <ArrowRight className="size-4" />
            </Button>
          </form>

          <div className="mt-8 rounded-md border border-ink-700 bg-ink-800/40 p-4">
            <p className="font-mono text-[10px] uppercase tracking-widest text-bone-500">
              Default seeded admin
            </p>
            <p className="mt-1 font-mono text-xs text-bone-300">
              admin · admin12345
            </p>
            <p className="mt-1 text-[11px] text-bone-500">
              See README for setup steps.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
