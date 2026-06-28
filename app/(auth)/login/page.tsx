"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ContinuityRibbon } from "@/components/ananta/continuity-ribbon";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@ananta.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal masuk.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4">
      <div className="w-full max-w-sm rounded-[var(--radius-card)] border border-line bg-surface p-7">
        <p className="font-display text-2xl font-bold tracking-tight text-ink">Ananta</p>
        <ContinuityRibbon className="mb-5 mt-1" />
        <p className="mb-5 text-sm text-ink-muted">Masuk untuk melanjutkan.</p>

        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-caption text-ink-muted">Email</label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
          </div>
          <div>
            <label className="mb-1 block text-caption text-ink-muted">Kata sandi</label>
            <Input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button onClick={submit} disabled={loading} className="w-full">
            {loading ? "Memproses…" : "Masuk"}
          </Button>
        </div>
      </div>
    </main>
  );
}
