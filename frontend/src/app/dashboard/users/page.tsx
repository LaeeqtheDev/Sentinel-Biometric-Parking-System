'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Search, Users as UsersIcon, ScanFace, Trash2 } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { apiGet, apiDelete } from '@/lib/api';
import { PaginatedResponse, fmtDateTime } from '@/lib/utils';
import { User } from '@/lib/auth';
import { cn } from '@/lib/utils';

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'ALL' | 'ADMIN' | 'DRIVER'>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (filter !== 'ALL') params.set('role', filter);
      const res = await apiGet<PaginatedResponse<User>>(
        `/auth/users/?${params.toString()}`,
      );
      setUsers(res.results);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, filter]);

  async function remove(id: number, username: string) {
    if (!confirm(`Delete user @${username}?`)) return;
    try {
      await apiDelete(`/auth/users/${id}/`);
      setUsers((u) => u.filter((x) => x.id !== id));
    } catch (e: any) {
      alert(e.message);
    }
  }

  return (
    <>
      <Topbar title="Users" subtitle="System administrators and registered drivers." />

      <main className="flex-1 p-6 lg:p-8">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <div className="relative max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-bone-500" />
              <Input
                placeholder="Search users…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex rounded-md border border-ink-600 bg-ink-800/40 p-0.5">
              {(['ALL', 'ADMIN', 'DRIVER'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    'rounded px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors',
                    filter === f
                      ? 'bg-amber text-ink-950'
                      : 'text-bone-400 hover:text-bone-200',
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <Link href="/dashboard/users/new">
            <Button>
              <Plus className="size-4" /> Add user
            </Button>
          </Link>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-denied/30 bg-denied/10 px-4 py-3 text-sm text-denied">
            {error}
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-ink-600 bg-ink-800/40">
          <table className="w-full">
            <thead>
              <tr className="border-b border-ink-700 bg-ink-900/40 text-left">
                <Th>User</Th>
                <Th>Role</Th>
                <Th>Email</Th>
                <Th>Phone</Th>
                <Th>Biometric</Th>
                <Th>Joined</Th>
                <Th className="text-right pr-5">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-sm text-bone-500">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && users.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-16 text-center">
                    <div className="flex flex-col items-center gap-3 text-bone-500">
                      <UsersIcon className="size-8 opacity-50" />
                      <p className="text-sm">No users found.</p>
                    </div>
                  </td>
                </tr>
              )}
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-ink-700 transition-colors last:border-0 hover:bg-ink-700/20"
                >
                  <Td>
                    <div className="flex items-center gap-3">
                      <div className="grid size-9 place-items-center rounded-full bg-ink-700 font-mono text-xs font-semibold uppercase text-bone-200">
                        {(u.first_name?.[0] || u.username[0]).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm text-bone-100">
                          {u.first_name} {u.last_name}
                        </p>
                        <p className="font-mono text-[11px] text-bone-500">
                          @{u.username}
                        </p>
                      </div>
                    </div>
                  </Td>
                  <Td>
                    <span
                      className={cn(
                        'rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                        u.role === 'ADMIN'
                          ? 'border-amber/30 bg-amber/10 text-amber'
                          : 'border-ink-600 bg-ink-700/40 text-bone-300',
                      )}
                    >
                      {u.role}
                    </span>
                  </Td>
                  <Td>
                    <span className="text-sm text-bone-300">{u.email || '—'}</span>
                  </Td>
                  <Td>
                    <span className="font-mono text-xs text-bone-400">{u.phone || '—'}</span>
                  </Td>
                  <Td>
                    {u.has_biometric ? (
                      <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-granted">
                        <span className="size-1.5 rounded-full bg-granted" /> Enrolled
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">
                        Not enrolled
                      </span>
                    )}
                  </Td>
                  <Td>
                    <span className="font-mono text-[11px] tabular-nums text-bone-400">
                      {fmtDateTime(u.created_at)}
                    </span>
                  </Td>
                  <Td className="pr-5 text-right">
                    <div className="flex justify-end gap-1">
                      <Link
                        href={`/dashboard/users/${u.id}/biometric`}
                        className="rounded-md p-1.5 text-bone-500 transition-colors hover:bg-amber/10 hover:text-amber"
                        title="Enroll biometric"
                      >
                        <ScanFace className="size-4" />
                      </Link>
                      <button
                        onClick={() => remove(u.id, u.username)}
                        className="rounded-md p-1.5 text-bone-500 transition-colors hover:bg-denied/10 hover:text-denied"
                        title="Delete"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}

function Th({ children, className = '' }: any) {
  return (
    <th className={`px-5 py-3 font-mono text-[10px] font-medium uppercase tracking-widest text-bone-500 ${className}`}>
      {children}
    </th>
  );
}

function Td({ children, className = '' }: any) {
  return <td className={`px-5 py-4 ${className}`}>{children}</td>;
}
