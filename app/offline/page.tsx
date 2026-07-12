import { ContinuityRibbon } from "@/components/ananta/continuity-ribbon";

export const metadata = { title: "Offline" };

export default function OfflinePage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-6 text-center">
      <div className="w-full max-w-sm">
        <p className="font-display text-3xl font-bold tracking-tight text-ink">Ananta</p>
        <ContinuityRibbon className="mx-auto my-4 max-w-[12rem]" />
        <h1 className="text-h3 font-semibold text-ink">Kamu sedang offline</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Aplikasi butuh koneksi internet untuk memuat data terbaru. Periksa jaringanmu, lalu coba
          lagi.
        </p>
        <a
          href="/dashboard"
          className="mt-6 inline-flex items-center justify-center rounded-[var(--radius-button)] bg-primary px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
        >
          Coba lagi
        </a>
      </div>
    </main>
  );
}
