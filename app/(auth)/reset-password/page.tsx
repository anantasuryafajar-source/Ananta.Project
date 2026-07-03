"use client";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function ResetInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) setError("Tautan tidak lengkap. Minta tautan reset baru.");
  }, [token]);

  async function submit() {
    setError(null);
    if (pw.length < 8) return setError("Kata sandi baru minimal 8 karakter.");
    if (pw !== confirm) return setError("Konfirmasi kata sandi tidak sama.");
    setLoading(true);
    try {
      await api("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: pw }),
      });
      setDone(true);
      setTimeout(() => router.push("/login"), 1800);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal mengatur ulang.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4">
      <div className="w-full max-w-sm rounded-[var(--radius-card)] border border-line bg-surface p-7">
        <p className="font-display text-2xl font-bold tracking-tight text-ink">Ananta</p>
        <p className="mb-5 mt-1 text-sm text-ink-muted">Buat kata sandi baru.</p>

        {done ? (
          <div className="space-y-4">
            <div className="rounded-[var(--radius-input)] border border-success/30 bg-success/10 px-4 py-3">
              <p className="text-sm text-ink">Kata sandi berhasil diperbarui. Mengalihkan ke halaman masuk…</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-caption text-ink-muted">Kata sandi baru</label>
              <Input value={pw} onChange={(e) => setPw(e.target.value)} type="password"
                placeholder="Minimal 8 karakter" disabled={!token} />
            </div>
            <div>
              <label className="mb-1 block text-caption text-ink-muted">Ulangi kata sandi baru</label>
              <Input value={confirm} onChange={(e) => setConfirm(e.target.value)} type="password"
                onKeyDown={(e) => e.key === "Enter" && submit()} disabled={!token} />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button onClick={submit} disabled={loading || !token} className="w-full">
              {loading ? "Menyimpan…" : "Simpan Kata Sandi Baru"}
            </Button>
            <p className="pt-1 text-center text-caption">
              <Link href="/login" className="text-primary hover:underline">Kembali ke masuk</Link>
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<main className="grid min-h-screen place-items-center bg-canvas"><p className="text-sm text-ink-muted">Memuat…</p></main>}>
      <ResetInner />
    </Suspense>
  );
}
