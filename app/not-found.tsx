import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4">
      <div className="text-center">
        <p className="num text-5xl font-bold text-ink">404</p>
        <p className="mt-2 text-ink-muted">Halaman tidak ditemukan.</p>
        <Link
          href="/"
          className="mt-6 inline-flex rounded-[var(--radius-button)] bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-[var(--primary-hover)]"
        >
          Kembali ke beranda
        </Link>
      </div>
    </main>
  );
}
