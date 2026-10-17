import { Check, Car, Gauge, KeyRound, DoorOpen, ScanLine } from 'lucide-react';

/**
 * Hero visual: a stylised operator console showing one gate decision end to
 * end (camera read -> checks -> gate). Pure server-rendered markup + CSS.
 */

const PIPELINE = [
  { icon: ScanLine, label: 'Plate read', value: 'LEA-1234', meta: '97% · 142 ms' },
  { icon: Car, label: 'Vehicle', value: 'Registered · Active', meta: 'Toyota Corolla' },
  { icon: Gauge, label: 'Risk score', value: '18 / 100', meta: 'Low', risk: 18 },
  { icon: KeyRound, label: 'Identity', value: 'Passkey verified', meta: 'on driver’s phone' },
  { icon: DoorOpen, label: 'Gate', value: 'Opened', meta: 'session #4821', final: true },
];

function Corner({ className }: { className: string }) {
  return <span className={`absolute size-4 border-amber ${className}`} aria-hidden />;
}

export function GateFeed() {
  return (
    <div className="relative">
      <div className="absolute -inset-8 rounded-[2rem] bg-amber/[0.07] blur-3xl" aria-hidden />

      <figure
        className="relative overflow-hidden rounded-2xl border border-ink-600/80 bg-ink-900/90 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.8)] ring-1 ring-white/[0.03]"
        aria-label="Sentinel operator console showing an entry decision"
      >
        {/* Title bar */}
        <div className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5" aria-hidden>
              <span className="size-2.5 rounded-full bg-ink-600" />
              <span className="size-2.5 rounded-full bg-ink-600" />
              <span className="size-2.5 rounded-full bg-ink-600" />
            </div>
            <span className="text-xs font-medium text-bone-200">Gate A · Entry</span>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-granted/20 bg-granted/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-granted">
            <span className="size-1.5 animate-pulse-soft rounded-full bg-granted" />
            Live
          </span>
        </div>

        <div className="grid sm:grid-cols-[1.15fr_1fr]">
          {/* Camera viewport */}
          <div className="relative flex border-b border-ink-700 p-4 sm:border-b-0 sm:border-r">
            <div className="relative min-h-[240px] w-full overflow-hidden rounded-lg bg-[radial-gradient(120%_90%_at_50%_100%,#26262f_0%,#13131a_45%,#08080a_100%)]">
              {/* Road perspective */}
              <svg viewBox="0 0 320 320" preserveAspectRatio="xMidYMax slice" className="absolute inset-0 h-full w-full" aria-hidden>
                <defs>
                  <linearGradient id="lane" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="#f5f5f7" stopOpacity="0" />
                    <stop offset="1" stopColor="#f5f5f7" stopOpacity="0.18" />
                  </linearGradient>
                  <radialGradient id="beam" cx="0.5" cy="0.5" r="0.5">
                    <stop offset="0" stopColor="#fde047" stopOpacity="0.35" />
                    <stop offset="1" stopColor="#fde047" stopOpacity="0" />
                  </radialGradient>
                </defs>
                <path d="M148 90 L20 320" stroke="url(#lane)" strokeWidth="2" />
                <path d="M172 90 L300 320" stroke="url(#lane)" strokeWidth="2" />
                <path d="M160 100 L160 120 M160 145 L160 180 M160 210 L160 260 M160 290 L160 320" stroke="#f5f5f7" strokeOpacity="0.1" strokeWidth="3" />
                {/* Headlight glow suggests an approaching car without drawing one */}
                <ellipse cx="96" cy="222" rx="58" ry="26" fill="url(#beam)" />
                <ellipse cx="224" cy="222" rx="58" ry="26" fill="url(#beam)" />
              </svg>

              {/* Plate with detection brackets */}
              <div className="absolute left-1/2 top-[70%] -translate-x-1/2 -translate-y-1/2">
                <div className="relative px-3 py-2.5">
                  <Corner className="left-0 top-0 border-l-2 border-t-2" />
                  <Corner className="right-0 top-0 border-r-2 border-t-2" />
                  <Corner className="bottom-0 left-0 border-b-2 border-l-2" />
                  <Corner className="bottom-0 right-0 border-b-2 border-r-2" />
                  <div className="rounded-[3px] bg-bone-50 px-2.5 py-0.5 font-mono text-[13px] font-bold tracking-[0.16em] text-ink-950 shadow-[0_0_24px_rgba(253,224,71,0.25)]">
                    LEA-1234
                  </div>
                </div>
              </div>

              {/* HUD */}
              <div className="absolute inset-x-0 top-0 flex justify-between p-2.5 font-mono text-[9px] uppercase tracking-wider text-bone-400">
                <span>CAM-01 · 1280×720</span>
                <span className="flex items-center gap-1 text-denied">
                  <span className="size-1.5 rounded-full bg-denied" /> rec
                </span>
              </div>
              <div className="absolute inset-x-0 bottom-0 flex justify-between bg-gradient-to-t from-ink-950/90 to-transparent p-2.5 pt-6 font-mono text-[9px] uppercase tracking-wider">
                <span className="text-bone-400">18:42:07</span>
                <span className="text-amber">ocr 0.97</span>
              </div>
            </div>
          </div>

          {/* Decision pipeline */}
          <ol className="divide-y divide-ink-700/70 p-2">
            {PIPELINE.map((step) => (
              <li key={step.label} className="flex items-center gap-3 px-2 py-2.5">
                <span
                  className={
                    step.final
                      ? 'grid size-7 shrink-0 place-items-center rounded-md bg-amber text-ink-950'
                      : 'grid size-7 shrink-0 place-items-center rounded-md border border-ink-600 bg-ink-800 text-bone-400'
                  }
                >
                  <step.icon className="size-3.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-[9px] uppercase tracking-wider text-bone-500">{step.label}</p>
                  <p className={step.final ? 'truncate text-sm font-semibold text-amber' : 'truncate text-sm font-medium text-bone-50'}>
                    {step.value}
                  </p>
                  {step.risk !== undefined ? (
                    <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-ink-700">
                      <div className="h-full rounded-full bg-granted" style={{ width: `${step.risk}%` }} />
                    </div>
                  ) : (
                    <p className="truncate text-[11px] text-bone-500">{step.meta}</p>
                  )}
                </div>
                <Check className="size-3.5 shrink-0 text-granted" aria-hidden />
              </li>
            ))}
          </ol>
        </div>

        {/* Footer strip */}
        <figcaption className="flex items-center justify-between border-t border-ink-700 bg-ink-950/60 px-4 py-2.5 font-mono text-[10px] text-bone-500">
          <span>Decision in 0.9 s</span>
          <span className="hidden sm:inline">No staff action needed</span>
          <span className="text-granted">Access granted</span>
        </figcaption>
      </figure>
    </div>
  );
}
