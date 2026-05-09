'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ShieldCheck, ArrowRight, UserPlus } from 'lucide-react';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { useAuth } from '@/lib/auth';
import { apiPost, ApiError } from '@/lib/api';

export default function DriverRegisterPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>('');
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    phone: '',
    cnic: '',
    password: '',
    confirm: '',
    // Optional vehicle onboarding (in same flow)
    vehicle_plate: '',
    vehicle_make: '',
    vehicle_model: '',
    vehicle_color: '',
    vehicle_type: 'CAR',
  });
  const [includeVehicle, setIncludeVehicle] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace('/driver');
  }, [user, loading, router]);

  function update<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');

    // basic client-side validation
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (form.password !== form.confirm) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      // Hit the public register endpoint
      await apiPost(
        '/auth/register/',
        {
          username: form.username.trim(),
          email: form.email.trim(),
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          phone: form.phone.trim(),
          cnic: form.cnic.trim(),
          password: form.password,
          ...(includeVehicle && form.vehicle_plate.trim()
            ? {
                vehicle_plate: form.vehicle_plate.trim(),
                vehicle_make: form.vehicle_make.trim(),
                vehicle_model: form.vehicle_model.trim(),
                vehicle_color: form.vehicle_color.trim(),
                vehicle_type: form.vehicle_type,
              }
            : {}),
        },
        { skipAuth: true },
      );

      // Auto-login after successful registration
      await login(form.username.trim(), form.password);
      // Redirect straight to biometric setup so the driver can immediately
      // enroll either a passkey (fingerprint/face on their device) or
      // a face encoding via webcam.
      router.replace('/driver/biometric?welcome=1');
    } catch (err) {
      if (err instanceof ApiError) {
        // Try to extract a sensible message from DRF's validation response
        const data: any = err.data;
        if (data && typeof data === 'object') {
          const firstField = Object.keys(data)[0];
          const firstMsg = Array.isArray(data[firstField])
            ? data[firstField][0]
            : data[firstField] || data.detail;
          setError(
            firstField && firstField !== 'detail'
              ? `${firstField}: ${firstMsg}`
              : String(firstMsg) || 'Registration failed.',
          );
        } else {
          setError(err.message || 'Registration failed.');
        }
      } else {
        setError('Could not connect to server.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-6 py-10">
      <div className="w-full max-w-md">
        <div className="mb-7 flex flex-col items-center gap-3 text-center">
          <div className="grid size-14 place-items-center rounded-lg bg-amber text-ink-950 glow-amber-strong">
            <ShieldCheck className="size-7" strokeWidth={2.5} />
          </div>
          <p className="font-display text-2xl font-semibold tracking-tight text-bone-50">
            Create driver account
          </p>
          <p className="text-sm text-bone-400">
            After signing up, an admin will link your registered vehicles to
            your account. You can enroll a passkey right away.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="First name"
              value={form.first_name}
              onChange={(e) => update('first_name', e.target.value)}
              required
              autoFocus
            />
            <Input
              label="Last name"
              value={form.last_name}
              onChange={(e) => update('last_name', e.target.value)}
              required
            />
          </div>

          <Input
            label="Username"
            value={form.username}
            onChange={(e) => update('username', e.target.value)}
            required
            autoComplete="username"
            placeholder="e.g. ahmed_2026"
          />

          <Input
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => update('email', e.target.value)}
            autoComplete="email"
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Phone"
              value={form.phone}
              onChange={(e) => update('phone', e.target.value)}
              placeholder="03xx-xxxxxxx"
            />
            <Input
              label="CNIC"
              value={form.cnic}
              onChange={(e) => update('cnic', e.target.value)}
              placeholder="35202-xxxxxxx-x"
            />
          </div>

          <Input
            label="Password"
            type="password"
            value={form.password}
            onChange={(e) => update('password', e.target.value)}
            required
            autoComplete="new-password"
            placeholder="At least 6 characters"
          />

          <Input
            label="Confirm password"
            type="password"
            value={form.confirm}
            onChange={(e) => update('confirm', e.target.value)}
            required
            autoComplete="new-password"
          />

          {/* Optional vehicle onboarding */}
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-bone-200">
              <input
                type="checkbox"
                checked={includeVehicle}
                onChange={(e) => setIncludeVehicle(e.target.checked)}
                className="size-4 rounded border-ink-600 bg-ink-900 text-amber focus:ring-amber"
              />
              I want to add my vehicle now (optional)
            </label>
            {includeVehicle && (
              <div className="mt-3 space-y-2.5 border-t border-ink-700 pt-3">
                <Input
                  label="Plate number"
                  value={form.vehicle_plate}
                  onChange={(e) =>
                    update('vehicle_plate', e.target.value.toUpperCase())
                  }
                  placeholder="AAP-1478"
                  className="font-mono tracking-widest"
                />
                <div className="grid grid-cols-2 gap-2.5">
                  <Input
                    label="Make"
                    value={form.vehicle_make}
                    onChange={(e) => update('vehicle_make', e.target.value)}
                    placeholder="Toyota"
                  />
                  <Input
                    label="Model"
                    value={form.vehicle_model}
                    onChange={(e) => update('vehicle_model', e.target.value)}
                    placeholder="Corolla"
                  />
                </div>
                <p className="text-[11px] text-bone-500">
                  Your vehicle starts as <strong>under review</strong>. An
                  admin will approve it before the gate trusts it.
                </p>
              </div>
            )}
          </div>

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
            <UserPlus className="size-4" /> Create account
            <ArrowRight className="size-4" />
          </Button>
        </form>

        <div className="mt-6 text-center text-sm text-bone-500">
          Already have an account?{' '}
          <Link href="/driver/login" className="text-amber hover:underline">
            Sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
