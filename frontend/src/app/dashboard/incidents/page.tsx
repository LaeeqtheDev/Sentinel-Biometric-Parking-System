'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCw, Shield, XCircle } from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { apiGet } from '@/lib/api';
import { fmtDateTime, cn } from '@/lib/utils';

interface Incident {
  id: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  reason: string;
  resolved: boolean;
  resolved_by: string | null;
  resolution_notes: string;
  created_at: string;
  vehicle: { id: number; plate_number: string } | null;
  access_log_id: number | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [showResolved, setShowResolved] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet<Incident[]>(
        `/access/incidents/?resolved=${showResolved}`,
      );
      setIncidents(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [showResolved]);

  async function resolve(id: number) {
    const notes = prompt('Resolution notes (optional):') ?? '';
    const token = typeof window !== 'undefined'
      ? localStorage.getItem('sentinel_access') : null;
    await fetch(`${API_URL}/access/incidents/?id=${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ notes }),
    });
    load();
  }

  const severityConfig = {
    LOW: { color: 'text-bone-400', bg: 'bg-ink-800', border: 'border-ink-600', icon: Shield },
    MEDIUM: { color: 'text-amber', bg: 'bg-amber/5', border: 'border-amber/30', icon: AlertTriangle },
    HIGH: { color: 'text-denied', bg: 'bg-denied/5', border: 'border-denied/30', icon: XCircle },
    CRITICAL: { color: 'text-denied', bg: 'bg-denied/10', border: 'border-denied/50', icon: XCircle },
  };

  return (
    <>
      <Topbar title="Incidents" subtitle="Security events requiring admin attention." />
      <main className="flex-1 space-y-6 p-6 lg:p-8">
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            <button
              onClick={() => setShowResolved(false)}
              className={cn(
                'rounded-md border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider',
                !showResolved ? 'border-amber bg-amber/10 text-amber' : 'border-ink-600 text-bone-500',
              )}
            >
              Open ({incidents.length})
            </button>
            <button
              onClick={() => setShowResolved(true)}
              className={cn(
                'rounded-md border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider',
                showResolved ? 'border-granted bg-granted/10 text-granted' : 'border-ink-600 text-bone-500',
              )}
            >
              Resolved
            </button>
          </div>
          <Button onClick={load} variant="ghost" size="sm">
            <RefreshCw className="size-3.5" /> Refresh
          </Button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-bone-500">Loading…</div>
        ) : incidents.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-ink-700 p-12 text-center">
            <CheckCircle2 className="mx-auto size-10 text-granted" />
            <p className="mt-3 text-bone-300">
              {showResolved ? 'No resolved incidents.' : 'No open incidents.'}
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {incidents.map((inc) => {
              const cfg = severityConfig[inc.severity];
              const Icon = cfg.icon;
              return (
                <li
                  key={inc.id}
                  className={cn('rounded-lg border p-4', cfg.bg, cfg.border)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <Icon className={cn('mt-0.5 size-5 shrink-0', cfg.color)} />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={cn('font-mono text-[10px] uppercase tracking-wider', cfg.color)}>
                            {inc.severity}
                          </span>
                          {inc.vehicle && (
                            <span className="font-mono text-xs text-bone-300">
                              · {inc.vehicle.plate_number}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-bone-200">{inc.reason}</p>
                        <p className="mt-1 font-mono text-[10px] text-bone-500">
                          {fmtDateTime(inc.created_at)}
                          {inc.resolved_by && ` · Resolved by @${inc.resolved_by}`}
                        </p>
                        {inc.resolution_notes && (
                          <p className="mt-1 text-xs text-bone-400">
                            Note: {inc.resolution_notes}
                          </p>
                        )}
                      </div>
                    </div>
                    {!inc.resolved && (
                      <Button
                        onClick={() => resolve(inc.id)}
                        variant="ghost"
                        size="sm"
                        className="shrink-0 border-granted/30 text-granted hover:bg-granted/10"
                      >
                        <CheckCircle2 className="size-3.5" /> Resolve
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </>
  );
}
