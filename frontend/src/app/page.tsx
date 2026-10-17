import type { Metadata } from 'next';
import Link from 'next/link';
import {
  ShieldCheck,
  ScanLine,
  Gauge,
  Fingerprint,
  DoorOpen,
  KeyRound,
  QrCode,
  FileClock,
  Camera,
  Bot,
  Wallet,
  ParkingSquare,
  Siren,
  Smartphone,
  Server,
} from 'lucide-react';
import { AuthCta } from '@/components/landing/AuthCta';
import { GateFeed } from '@/components/landing/GateFeed';

export const metadata: Metadata = {
  title: 'Sentinel: autonomous biometric parking access',
  description:
    'Sentinel reads licence plates, scores every entry and exit for risk, and lets drivers release their own car with a passkey. Built for facilities that need a gate they can trust.',
  openGraph: {
    title: 'Sentinel: autonomous biometric parking access',
    description:
      'Plate recognition, risk scoring and device-bound passkeys for parking gates.',
    type: 'website',
  },
};

const STEPS = [
  {
    icon: ScanLine,
    title: 'Read the plate',
    body: 'The entry camera reads plates continuously. Each read carries a confidence level, and blurry or partial reads are never acted on alone.',
  },
  {
    icon: Gauge,
    title: 'Score the risk',
    body: 'Every event gets a 0 to 100 score from plate status, driver trust, time of day and recent failures, with a readable trace of why.',
  },
  {
    icon: Fingerprint,
    title: 'Verify the driver',
    body: 'Low-risk trusted vehicles pass automatically. Everyone else confirms with Face ID or fingerprint on their own phone.',
  },
  {
    icon: DoorOpen,
    title: 'Open the gate',
    body: 'The session opens or closes in one atomic step, so the system and the lot always agree on which cars are inside.',
  },
];

const SECURITY = [
  {
    icon: KeyRound,
    title: 'Biometrics stay on the phone',
    body: 'Passkeys are checked by the phone’s secure hardware. The server keeps a public key, so a database leak exposes no fingerprints or faces.',
  },
  {
    icon: QrCode,
    title: 'A QR code is not a key',
    body: 'Kiosk QR codes expire in minutes and only point to a session. Releasing the car still needs the owner’s passkey on their own device.',
  },
  {
    icon: FileClock,
    title: 'Every override is on record',
    body: 'Manual gate openings are logged with the operator, time and reason. There is no unaudited master key.',
  },
];

const FEATURES = [
  { icon: Camera, title: 'Live camera console', body: 'Entry and exit feeds with plate reads, face matches and one-click actions.' },
  { icon: Bot, title: 'Autonomous mode', body: 'Trusted, low-risk vehicles go through without anyone touching the gate.' },
  { icon: Wallet, title: 'Peak / off-peak pricing', body: 'Fees split by the minute across peak and off-peak windows, with a grace period.' },
  { icon: ParkingSquare, title: 'Capacity control', body: 'Entries stop when the lot is full, even with several cameras at once.' },
  { icon: Siren, title: 'Incident feed', body: 'Blocked vehicles, face mismatches and repeated failures raise incidents automatically.' },
  { icon: Smartphone, title: 'Driver app', body: 'Drivers register cars, upload documents and release their car with one tap.' },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950 text-bone-200">
      {/* ---------------- Nav ---------------- */}
      <header className="sticky top-0 z-30 border-b border-ink-700/70 bg-ink-950/80 backdrop-blur">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="glow-amber grid size-8 place-items-center rounded-md bg-amber text-ink-950">
              <ShieldCheck className="size-4" strokeWidth={2.5} />
            </span>
            <span className="font-display text-lg font-semibold text-bone-50">Sentinel</span>
          </Link>
          <div className="hidden items-center gap-6 text-sm text-bone-400 md:flex">
            <a href="#how-it-works" className="hover:text-bone-50">How it works</a>
            <a href="#security" className="hover:text-bone-50">Security</a>
            <a href="#operators" className="hover:text-bone-50">For operators</a>
          </div>
          <AuthCta variant="nav" />
        </nav>
      </header>

      <main>
        {/* ---------------- Hero ---------------- */}
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 border-grid opacity-30 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />
          <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-4 pb-20 pt-16 sm:px-6 lg:grid-cols-2 lg:pb-28 lg:pt-24">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">
                · Autonomous parking access
              </p>
              <h1 className="mt-5 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-bone-50 text-balance sm:text-5xl lg:text-6xl">
                The gate knows the car.
                <br />
                <span className="text-amber-glow">The phone proves the driver.</span>
              </h1>
              <p className="mt-6 max-w-lg text-lg text-bone-400 text-balance">
                Sentinel reads licence plates, scores every entry and exit for risk, and lets
                drivers release their own car with Face ID or a fingerprint. No tickets, no
                guard booth queue, and a full record of every decision.
              </p>
              <div className="mt-8">
                <AuthCta variant="hero" />
              </div>
            </div>
            <GateFeed />
          </div>
        </section>

        {/* ---------------- How it works ---------------- */}
        <section id="how-it-works" className="scroll-mt-20 border-t border-ink-700 bg-ink-900/40">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">· How it works</p>
            <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
              Four checks between the camera and the barrier
            </h2>
            <ol className="mt-12 grid gap-px overflow-hidden rounded-xl border border-ink-700 bg-ink-700 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((s, i) => (
                <li key={s.title} className="bg-ink-900 p-6">
                  <div className="flex items-center justify-between">
                    <s.icon className="size-5 text-amber" />
                    <span className="font-mono text-xs text-bone-500">0{i + 1}</span>
                  </div>
                  <h3 className="mt-6 font-display text-lg font-semibold text-bone-50">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-bone-400">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---------------- Security ---------------- */}
        <section id="security" className="scroll-mt-20 border-t border-ink-700">
          <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1fr_1.4fr]">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">· Security model</p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
                Biometric, without storing your biometrics
              </h2>
              <p className="mt-5 text-bone-400">
                A gate controls a real barrier. A mistake either traps a car inside or lets the
                wrong one out, so the system is built around what fails safely.
              </p>
            </div>
            <div className="space-y-4">
              {SECURITY.map((s) => (
                <div key={s.title} className="flex gap-4 rounded-lg border border-ink-700 bg-ink-900/60 p-5">
                  <span className="grid size-10 shrink-0 place-items-center rounded-md border border-amber/30 bg-amber/10 text-amber">
                    <s.icon className="size-5" />
                  </span>
                  <div>
                    <h3 className="font-display font-semibold text-bone-50">{s.title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-bone-400">{s.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------- Operators ---------------- */}
        <section id="operators" className="scroll-mt-20 border-t border-ink-700 bg-ink-900/40">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-amber">· For operators</p>
            <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold tracking-tight text-bone-50 sm:text-4xl">
              One console for the whole facility
            </h2>
            <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <div key={f.title} className="rounded-lg border border-ink-700 bg-ink-900 p-5 transition-colors hover:border-ink-500">
                  <f.icon className="size-5 text-amber" />
                  <h3 className="mt-4 font-display font-semibold text-bone-50">{f.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-bone-400">{f.body}</p>
                </div>
              ))}
            </div>

            <div className="mt-12 flex flex-col gap-4 rounded-xl border border-ink-700 bg-ink-950 p-6 sm:flex-row sm:items-center sm:gap-6">
              <Server className="size-6 shrink-0 text-amber" />
              <p className="text-sm leading-relaxed text-bone-400">
                <span className="font-medium text-bone-50">Built to scale out.</span> Plate and face
                recognition run on their own worker pool, the API is stateless behind a load
                balancer, and gate state changes are locked per vehicle, so adding cameras or
                gates means adding workers, not rewriting the system.
              </p>
            </div>
          </div>
        </section>

        {/* ---------------- CTA ---------------- */}
        <section className="border-t border-ink-700">
          <div className="mx-auto max-w-6xl px-4 py-20 text-center sm:px-6">
            <h2 className="mx-auto max-w-2xl font-display text-3xl font-semibold tracking-tight text-bone-50 text-balance sm:text-4xl">
              Park, walk away, and leave with one tap
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-bone-400">
              Register your vehicle once. After an operator approves it, your phone is your gate pass.
            </p>
            <div className="mt-8 flex justify-center">
              <AuthCta variant="hero" />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-ink-700">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-bone-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-amber" /> Sentinel Biometric Parking System
          </p>
          <div className="flex gap-5">
            <Link href="/driver/login" className="hover:text-bone-200">Driver sign in</Link>
            <Link href="/driver/register" className="hover:text-bone-200">Register</Link>
            <Link href="/login" className="hover:text-bone-200">Operator console</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
