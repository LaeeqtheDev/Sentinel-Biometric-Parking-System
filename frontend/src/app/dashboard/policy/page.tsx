'use client';

import { useEffect, useState } from 'react';
import {
  Settings,
  Save,
  Clock,
  Zap,
  Shield,
  ToggleRight,
  CheckCircle2,
} from 'lucide-react';
import { Topbar } from '@/components/Topbar';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Select } from '@/components/Select';
import { apiGet, apiPost } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PolicyConfig {
  trusted_threshold: number;
  normal_threshold: number;
  peak_start: string;
  peak_end: string;
  peak_enabled: boolean;
  is_peak_now: boolean;
  autonomous_mode: boolean;
  force_biometric_during_peak: boolean;
  auto_entry_for_trusted: boolean;
  ocr_min_confidence_normal: string;
  ocr_min_confidence_peak: string;
  risk_low_max: number;
  risk_medium_max: number;
  updated_at: string | null;
}

export default function PolicyConfigPage() {
  const [cfg, setCfg] = useState<PolicyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    apiGet<PolicyConfig>('/parking/policy/')
      .then(setCfg)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function update<K extends keyof PolicyConfig>(k: K, v: PolicyConfig[K]) {
    if (!cfg) return;
    setCfg({ ...cfg, [k]: v });
  }

  async function save() {
    if (!cfg) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const updated = await apiPost<PolicyConfig>('/parking/policy/', cfg);
      setCfg(updated);
      setSuccess('Policy updated.');
      setTimeout(() => setSuccess(''), 3000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Topbar
        title="Policy"
        subtitle="System-wide rules for the gate decision engine."
      />
      <main className="flex-1 space-y-6 p-6 lg:p-8">
        {error && (
          <div className="rounded-md border border-denied/30 bg-denied/10 px-3 py-2 text-sm text-denied">
            {error}
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 rounded-md border border-granted/30 bg-granted/10 px-3 py-2 text-sm text-granted">
            <CheckCircle2 className="size-4" /> {success}
          </div>
        )}

        {loading || !cfg ? (
          <div className="rounded-lg border border-ink-700 bg-ink-800/40 p-8 text-center text-bone-500">
            Loading policy…
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Peak hours */}
            <Section icon={Clock} title="Peak hours">
              <div
                className={cn(
                  'mb-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                  cfg.is_peak_now
                    ? 'bg-amber/10 text-amber'
                    : 'bg-ink-700 text-bone-500',
                )}
              >
                <span
                  className={cn(
                    'size-1.5 rounded-full',
                    cfg.is_peak_now ? 'bg-amber animate-pulse-soft' : 'bg-bone-600',
                  )}
                />
                {cfg.is_peak_now ? 'Currently peak' : 'Off-peak'}
              </div>
              <Toggle
                label="Enable peak-hours rules"
                value={cfg.peak_enabled}
                onChange={(v) => update('peak_enabled', v)}
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Peak start (HH:MM)"
                  value={cfg.peak_start}
                  onChange={(e) => update('peak_start', e.target.value)}
                  placeholder="18:00"
                />
                <Input
                  label="Peak end (HH:MM)"
                  value={cfg.peak_end}
                  onChange={(e) => update('peak_end', e.target.value)}
                  placeholder="23:00"
                />
              </div>
              <p className="text-[11px] text-bone-500">
                Overnight wrap supported (e.g. 22:00 → 02:00).
              </p>
            </Section>

            {/* Trust thresholds */}
            <Section icon={Shield} title="Trust thresholds">
              <p className="text-xs text-bone-400">
                Where on the 0–100 trust scale each level starts.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  type="number"
                  label="Trusted ≥"
                  value={cfg.trusted_threshold}
                  onChange={(e) =>
                    update('trusted_threshold', parseInt(e.target.value) || 0)
                  }
                />
                <Input
                  type="number"
                  label="Normal ≥"
                  value={cfg.normal_threshold}
                  onChange={(e) =>
                    update('normal_threshold', parseInt(e.target.value) || 0)
                  }
                />
              </div>
              <p className="text-[11px] text-bone-500">
                Below "Normal ≥" threshold = SUSPICIOUS.
              </p>
            </Section>

            {/* Behavior toggles */}
            <Section icon={ToggleRight} title="Behavior">
              <Toggle
                label="Autonomous mode"
                hint="If off, every entry/exit must be explicitly verified."
                value={cfg.autonomous_mode}
                onChange={(v) => update('autonomous_mode', v)}
              />
              <Toggle
                label="Auto-entry for TRUSTED"
                hint="Trusted users skip biometric (low risk only)."
                value={cfg.auto_entry_for_trusted}
                onChange={(v) => update('auto_entry_for_trusted', v)}
              />
              <Toggle
                label="Force biometric during peak"
                hint="Even TRUSTED users verify during peak hours."
                value={cfg.force_biometric_during_peak}
                onChange={(v) => update('force_biometric_during_peak', v)}
              />
            </Section>

            {/* Risk + OCR */}
            <Section icon={Zap} title="Risk & OCR">
              <p className="text-xs text-bone-400">
                Risk score thresholds (0–100, higher = riskier).
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  type="number"
                  label="LOW risk ≤"
                  value={cfg.risk_low_max}
                  onChange={(e) =>
                    update('risk_low_max', parseInt(e.target.value) || 0)
                  }
                />
                <Input
                  type="number"
                  label="MEDIUM risk ≤"
                  value={cfg.risk_medium_max}
                  onChange={(e) =>
                    update('risk_medium_max', parseInt(e.target.value) || 0)
                  }
                />
              </div>
              <Select
                label="Min OCR confidence (normal)"
                value={cfg.ocr_min_confidence_normal}
                onChange={(e) =>
                  update('ocr_min_confidence_normal', e.target.value)
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </Select>
              <Select
                label="Min OCR confidence (peak)"
                value={cfg.ocr_min_confidence_peak}
                onChange={(e) =>
                  update('ocr_min_confidence_peak', e.target.value)
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </Select>
            </Section>
          </div>
        )}

        {cfg && (
          <Button onClick={save} loading={saving} size="lg" className="w-full sm:w-auto">
            <Save className="size-4" /> Save policy
          </Button>
        )}
      </main>
    </>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: any;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-lg border border-ink-700 bg-ink-800/40 p-5">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-amber" />
        <h2 className="font-display text-base font-semibold text-bone-50">
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

function Toggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-md border border-ink-700 bg-ink-900/40 p-3">
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 size-4 rounded border-ink-600 bg-ink-900 text-amber focus:ring-amber"
      />
      <div className="flex-1">
        <p className="text-sm font-medium text-bone-100">{label}</p>
        {hint && <p className="text-[11px] text-bone-500">{hint}</p>}
      </div>
    </label>
  );
}
