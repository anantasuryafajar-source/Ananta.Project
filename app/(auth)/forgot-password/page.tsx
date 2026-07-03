"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      await api("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4">
      <div className="w-full max-w-sm rounded-[var(--radius-card)] border border-line bg-surface p-7">
        <p className="font-display text-2xl font-bold tracking-tight text-ink">Ananta</p>
        <p className="mb-5 mt-1 text-sm text-ink-muted">Atur ulang kata sandi.</p>

        {sent ? (
          <div className="space-y-4">
            <div className="rounded-[var(--radius-input)] border border-success/30 bg-success/10 px-4 py-3">
              <p className="text-sm text-ink">
                Jika email <b>{email}</b> terdaftar, kami telah mengirim tautan untuk
                mengatur ulang kata sandi. Silakan cek kotak masuk (dan folder spam).
              </p>
            </div>
            <p className="text-caption text-ink-subtle">Tautan berlaku selama 1 jam.</p>
            <Link href="/login" className="block text-center text-sm text-primary hover:underline">
              Kembali ke halaman masuk
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-ink-muted">
              Masukkan email akun Anda. Kami akan mengirim tautan untuk membuat kata sandi baru.
            </p>
            <div>
              <label className="mb-1 block text-caption text-ink-muted">Email</label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email"
                onKeyDown={(e) => e.key === "Enter" && email && submit()}
                placeholder="nama@perusahaan.com" />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button onClick={submit} disabled={loading || !email} className="w-full">
              {loading ? "Mengirim…" : "Kirim Tautan Reset"}
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
