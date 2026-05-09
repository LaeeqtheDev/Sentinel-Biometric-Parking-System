'use client';

import { useEffect, useState } from 'react';
import {
  Shield,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { apiGet } from '@/lib/api';
import { fmtDateTime, cn } from '@/lib/utils';

interface RiskEvent {
  id: number;
  score: number;
  band: 'LOW' | 'MEDIUM' | 'HIGH';
  factors: Record<string, number>;
  decision_path: string;
  timestamp: string;
  access_log: {
    id: number;
    event_type: string;
    plate_detected: string;
    status: string;
    username: string | null;
    via: string;
  } | null;
}

export default function RiskEventsPage() {
  const [events, setEvents] = useState<RiskEvent[]>([]);
  const [filter, setFilter] = useState<'all' | 'LOW' | 'MEDIUM' | 'HIGH'>('all');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const url = filter === 'all' ? '/access/risk-events/' : `/access/risk-events/?band=${filter}`;
    try {
      const data = await apiGet<RiskEvent[]>(url);
      setEvents(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [filter]);

  return (
    <>
      <Topbar
        title="Risk events"
        subtitle="Per-decision audit trail with score breakdown."
      />
      <main className="flex-1 space-y-6 p-6 lg:p-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex gap-2">
            {(['all', 'LOW', 'MEDIUM', 'HIGH'] as const).map((b) => (
              <button
                key={b}
                onClick={() => setFilter(b)}
                className={cn(
                  'rounded-md border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors',
                  filter === b
                    ? 'border-amber bg-amber/10 text-amber'
                    : 'border-ink-600 bg-ink-800/40 text-bone-500 hover:text-bone-300',
                )}
              >
                {b}
              </button>
            ))}
          </div>
          <Button onClick={load} variant="ghost" size="sm">
            <RefreshCw className="size-3.5" /> Refresh
          </Button>
        </div>

        {loading ? (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-8 text-center text-bone-500">
            Loading…
          </div>
        ) : events.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-ink-700 bg-ink-800/20 p-8 text-center text-bone-500">
            No risk events yet.
          </div>
        ) : (
          <ul className="space-y-3">
            {events.map((e) => (
              <li
                key={e.id}
                className={cn(
                  'rounded-lg border p-4',
                  e.band === 'HIGH'
                    ? 'border-denied/40 bg-denied/5'
                    : e.band === 'MEDIUM'
                    ? 'border-amber/40 bg-amber/5'
                    : 'border-granted/40 bg-granted/5',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        'grid size-10 shrink-0 place-items-center rounded-md border',
                        e.band === 'HIGH'
                          ? 'border-denied/40 bg-denied/10 text-denied'
                          : e.band === 'MEDIUM'
                          ? 'border-amber/40 bg-amber/10 text-amber'
                          : 'border-granted/40 bg-granted/10 text-granted',
                      )}
                    >
                      {e.band === 'HIGH' ? (
                        <AlertTriangle className="size-4" />
                      ) : e.band === 'MEDIUM' ? (
                        <Shield className="size-4" />
                      ) : (
                        <CheckCircle2 className="size-4" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider',
                            e.band === 'HIGH'
                              ? 'bg-denied/10 text-denied'
                              : e.band === 'MEDIUM'
                              ? 'bg-amber/10 text-amber'
                              : 'bg-granted/10 text-granted',
                          )}
                        >
                          {e.band} · {e.score}
                        </span>
                        {e.access_log && (
                          <span className="font-mono text-[11px] text-bone-300">
                            {e.access_log.event_type} ·{' '}
                            <span className="font-semibold text-bone-50">
                              {e.access_log.plate_detected}
                            </span>
                            {e.access_log.username && (
                              <> · @{e.access_log.username}</>
                            )}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-bone-500">
                        {fmtDateTime(e.timestamp)}
                        {e.access_log && <> · via {e.access_log.via}</>}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="mt-3 border-t border-ink-700 pt-3">
                  <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                    Factors
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(e.factors).map(([k, v]) => (
                      <span
                        key={k}
                        className={cn(
                          'rounded border px-2 py-0.5 font-mono text-[10px]',
                          v > 0
                            ? 'border-denied/30 text-denied'
                            : 'border-granted/30 text-granted',
                        )}
                      >
                        {k} {v > 0 ? '+' : ''}
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
