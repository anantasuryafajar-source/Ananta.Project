import Link from "next/link";
import { ContinuityRibbon } from "@/components/ananta/continuity-ribbon";

export default function Home() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4">
      <div className="w-full max-w-md text-center">
        <p className="font-display text-4xl font-bold tracking-tight text-ink">
          Ananta
        </p>
        <ContinuityRibbon className="mx-auto my-4 max-w-xs" />
        <p className="text-ink-muted">
          Sistem manajemen bisnis &amp; akuntansi yang tenang, presisi, dan mengalir
          tanpa putus.
        </p>

        <div className="mt-8 flex items-center justify-center gap-3">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-[var(--radius-button)] bg-primary px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
          >
            Masuk
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-[var(--radius-button)] border border-line bg-surface px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-surface-sunken"
          >
            Lihat dashboard
          </Link>
        </div>

        <p className="mt-10 text-caption text-ink-subtle">
          v0.1.0 · Calm Ledger
        </p>
      </div>
    </main>
  );
}
