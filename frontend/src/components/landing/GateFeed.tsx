/**
 * Static illustration of the operator's live gate view: a camera frame with
 * a detected plate, the risk read-out and the decision. Pure markup + CSS
 * animation, so it renders on the server and costs no JS.
 */
export function GateFeed() {
  return (
    <div className="relative">
      <div className="absolute -inset-6 rounded-3xl bg-amber/10 blur-3xl" aria-hidden />
      <figure
        className="relative overflow-hidden rounded-xl border border-ink-600 bg-ink-900 shadow-2xl"
        aria-label="Illustration of the live gate camera view"
      >
        {/* Window chrome */}
        <div className="flex items-center justify-between border-b border-ink-700 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="size-1.5 animate-pulse-soft rounded-full bg-granted" />
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-bone-400">
              Entry cam · Gate A
            </span>
          </div>
          <span className="font-mono text-[10px] text-bone-500">REC 18:42:07</span>
        </div>

        {/* Camera frame */}
        <div className="scanlines relative aspect-[16/10] overflow-hidden bg-[radial-gradient(ellipse_at_50%_80%,#1b1b25,#08080a_70%)]">
          <div className="absolute inset-0 border-grid opacity-40" />

          {/* Abstract car silhouette */}
          <svg viewBox="0 0 400 250" className="absolute inset-0 h-full w-full" aria-hidden>
            <path
              d="M70 190 L95 125 Q105 100 135 98 L265 98 Q295 100 305 125 L330 190 Z"
              fill="#13131a"
              stroke="#26262f"
              strokeWidth="2"
            />
            <path d="M118 128 L132 108 L268 108 L282 128 Z" fill="#0d0d11" stroke="#26262f" />
            <rect x="60" y="186" width="280" height="26" rx="6" fill="#1b1b25" />
            <circle cx="96" cy="160" r="10" fill="#fde04722" stroke="#fde04755" />
            <circle cx="304" cy="160" r="10" fill="#fde04722" stroke="#fde04755" />
          </svg>

          {/* Plate + detection box */}
          <div className="absolute left-1/2 top-[63%] -translate-x-1/2 -translate-y-1/2">
            <div className="relative rounded-[3px] border border-bone-200/70 bg-bone-50 px-3 py-1 font-mono text-sm font-bold tracking-[0.18em] text-ink-950 sm:text-base">
              LEA · 1234
              <span className="absolute -inset-2 rounded border-2 border-amber" />
              <span className="absolute -left-2 -top-6 whitespace-nowrap rounded-sm bg-amber px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider text-ink-950">
                plate · high
              </span>
            </div>
          </div>

          {/* Sweeping scan line */}
          <div className="pointer-events-none absolute inset-x-0 top-0 h-1/2 animate-scan">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-amber/70 to-transparent" />
          </div>
        </div>

        {/* Decision panel */}
        <figcaption className="grid grid-cols-3 divide-x divide-ink-700 border-t border-ink-700 font-mono text-[11px]">
          <div className="px-4 py-3">
            <p className="uppercase tracking-wider text-bone-500">Risk</p>
            <p className="mt-1 text-lg font-semibold text-granted">18 · LOW</p>
          </div>
          <div className="px-4 py-3">
            <p className="uppercase tracking-wider text-bone-500">Identity</p>
            <p className="mt-1 text-lg font-semibold text-bone-50">Passkey</p>
          </div>
          <div className="px-4 py-3">
            <p className="uppercase tracking-wider text-bone-500">Gate</p>
            <p className="mt-1 text-lg font-semibold text-amber">Granted</p>
          </div>
        </figcaption>
      </figure>
    </div>
  );
}
