'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, UserPlus } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiPost } from '@/lib/api';

export default function NewUserPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: '',
    cnic: '',
    role: 'DRIVER',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  function update<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const created: any = await apiPost('/auth/users/', form);
      // After creating a driver, suggest biometric enrollment.
      if (form.role === 'DRIVER') {
        router.push(`/dashboard/users/${created.id}/biometric`);
      } else {
        router.push('/dashboard/users');
      }
    } catch (e: any) {
      const data = e.data;
      if (data && typeof data === 'object') {
        const first = Object.entries(data)[0];
        if (first) {
          setError(`${first[0]}: ${(first[1] as any)?.[0] ?? first[1]}`);
        } else {
          setError(e.message);
        }
      } else {
        setError(e.message || 'Failed to create user');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Topbar title="Add User" subtitle="Create an admin or driver account." />

      <main className="flex-1 p-6 lg:p-8">
        <Link
          href="/dashboard/users"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-bone-500 transition-colors hover:text-bone-300"
        >
          <ArrowLeft className="size-3.5" /> Back to users
        </Link>

        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-5">
              <div className="mb-3 grid size-10 place-items-center rounded-md bg-amber/10 text-amber">
                <UserPlus className="size-5" />
              </div>
              <h2 className="font-display text-lg font-semibold text-bone-50">
                New account
              </h2>
              <p className="mt-2 text-sm text-bone-400">
                Drivers will be redirected to the biometric enrollment screen
                after creation.
              </p>
            </div>
          </div>

          <form
            onSubmit={submit}
            className="space-y-5 rounded-lg border border-ink-600 bg-ink-800/40 p-6 lg:col-span-2"
          >
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <Input
                label="First name"
                value={form.first_name}
                onChange={(e) => update('first_name', e.target.value)}
              />
              <Input
                label="Last name"
                value={form.last_name}
                onChange={(e) => update('last_name', e.target.value)}
              />
              <Input
                label="Username *"
                value={form.username}
                onChange={(e) => update('username', e.target.value)}
                required
                autoComplete="off"
              />
              <Input
                label="Password *"
                type="password"
                value={form.password}
                onChange={(e) => update('password', e.target.value)}
                hint="Minimum 6 characters"
                required
                autoComplete="new-password"
              />
              <Input
                label="Email"
                type="email"
                value={form.email}
                onChange={(e) => update('email', e.target.value)}
              />
              <Input
                label="Phone"
                value={form.phone}
                onChange={(e) => update('phone', e.target.value)}
                placeholder="+92 300 0000000"
              />
              <Input
                label="CNIC"
                value={form.cnic}
                onChange={(e) => update('cnic', e.target.value)}
                placeholder="35202-0000000-0"
              />
              <Select
                label="Role *"
                value={form.role}
                onChange={(e) => update('role', e.target.value)}
              >
                <option value="DRIVER">Driver</option>
                <option value="ADMIN">Administrator</option>
              </Select>
            </div>

            {error && (
              <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
                {error}
              </div>
            )}

            <div className="flex justify-end gap-3 border-t border-ink-700 pt-5">
              <Link href="/dashboard/users">
                <Button type="button" variant="ghost">
                  Cancel
                </Button>
              </Link>
              <Button type="submit" loading={submitting}>
                Create user
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}
