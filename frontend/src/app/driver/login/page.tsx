'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldCheck, ArrowRight } from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { useAuth } from '@/lib/auth';
import { ApiError } from '@/lib/api';

export default function DriverLoginPage() {
  const router = useRouter();
  const { login, user, loading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && user) router.replace('/driver');
  }, [user, loading, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(username, password);
      router.replace('/driver');
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
    <main className="grid min-h-screen place-items-center px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="grid size-14 place-items-center rounded-lg bg-amber text-ink-950 glow-amber-strong">
            <ShieldCheck className="size-7" strokeWidth={2.5} />
          </div>
          <p className="font-display text-2xl font-semibold tracking-tight text-bone-50">
            Sentinel · Driver
          </p>
          <p className="text-center text-sm text-bone-400">
            Sign in to manage your vehicles and pickup access.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
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
          <Button type="submit" size="lg" loading={submitting} className="w-full">
            Sign in <ArrowRight className="size-4" />
          </Button>
        </form>

        <div className="mt-6 text-center text-sm text-bone-500">
          Don&apos;t have an account?{' '}
          <a href="/driver/register" className="text-amber hover:underline">
            Sign up
          </a>
        </div>

        <div className="mt-3 rounded-md border border-ink-700 bg-ink-800/40 p-3 text-center text-xs text-bone-500">
          Are you an administrator?{' '}
          <a href="/login" className="text-amber hover:underline">
            Admin login →
          </a>
        </div>
      </div>
    </main>
  );
}
