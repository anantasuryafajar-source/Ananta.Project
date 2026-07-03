"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { KeyRound, LogOut } from "lucide-react";
import { api, setToken } from "@/lib/api";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/form";
import { CommandPalette } from "@/components/ananta/command-palette";

type Me = { full_name?: string; email?: string };

export function Topbar({ title }: { title: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);           // dropdown
  const [openPw, setOpenPw] = useState(false);       // modal ganti sandi
  const [me, setMe] = useState<Me | null>(null);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Me>("/auth/me").then(setMe).catch(() => {});
  }, []);

  // tutup dropdown saat klik di luar
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const initial = (me?.full_name?.trim()?.[0] ?? "A").toUpperCase();

  function keluar() {
    setToken(null);
    router.replace("/login");
  }

  async function simpanPw(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (pw.new_password.length < 8) return setMsg({ type: "err", text: "Kata sandi baru minimal 8 karakter." });
    if (pw.new_password !== pw.confirm) return setMsg({ type: "err", text: "Konfirmasi kata sandi tidak sama." });
    setSaving(true);
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: pw.current_password, new_password: pw.new_password }),
      });
      setMsg({ type: "ok", text: "Kata sandi berhasil diganti." });
      setPw({ current_password: "", new_password: "", confirm: "" });
      setTimeout(() => { setOpenPw(false); setMsg(null); }, 1200);
    } catch (err) {
      setMsg({ type: "err", text: err instanceof Error ? err.message : "Gagal mengganti kata sandi." });
    } finally { setSaving(false); }
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-line bg-surface px-6">
      <h1 className="text-h3 font-semibold text-ink">{title}</h1>
      <div className="flex items-center gap-3">
        <CommandPalette />

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setOpen((v) => !v)}
            className="grid h-8 w-8 place-items-center rounded-full bg-primary-soft text-sm font-medium text-primary transition-shadow hover:ring-2 hover:ring-primary/30"
            aria-label="Menu akun"
          >
            {initial}
          </button>

          {open && (
            <div className="absolute right-0 top-10 z-50 w-56 rounded-[var(--radius-card)] border border-line bg-surface p-1.5 shadow-[var(--shadow-pop)]">
              <div className="border-b border-line px-3 pb-2 pt-1.5">
                <p className="truncate text-sm font-medium text-ink">{me?.full_name ?? "Pengguna"}</p>
                <p className="truncate text-caption text-ink-subtle">{me?.email ?? ""}</p>
              </div>
              <button
                onClick={() => { setOpen(false); setMsg(null); setPw({ current_password: "", new_password: "", confirm: "" }); setOpenPw(true); }}
                className="mt-1 flex w-full items-center gap-2 rounded-[var(--radius-input)] px-3 py-2 text-left text-sm text-ink hover:bg-surface-sunken"
              >
                <KeyRound size={15} className="text-ink-subtle" /> Ganti Kata Sandi
              </button>
              <button
                onClick={keluar}
                className="flex w-full items-center gap-2 rounded-[var(--radius-input)] px-3 py-2 text-left text-sm text-danger hover:bg-surface-sunken"
              >
                <LogOut size={15} /> Keluar
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Modal ganti kata sandi */}
      <Modal open={openPw} onClose={() => setOpenPw(false)} title="Ganti Kata Sandi">
        <form onSubmit={simpanPw} className="space-y-4">
          <Field label="Kata sandi saat ini">
            <Input type="password" value={pw.current_password}
              onChange={(e) => setPw((f) => ({ ...f, current_password: e.target.value }))} required autoFocus />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Kata sandi baru" hint="Minimal 8 karakter">
              <Input type="password" value={pw.new_password}
                onChange={(e) => setPw((f) => ({ ...f, new_password: e.target.value }))} required />
            </Field>
            <Field label="Ulangi kata sandi baru">
              <Input type="password" value={pw.confirm}
                onChange={(e) => setPw((f) => ({ ...f, confirm: e.target.value }))} required />
            </Field>
          </div>
          {msg && <p className={`text-sm ${msg.type === "ok" ? "text-success" : "text-danger"}`}>{msg.text}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenPw(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>
    </header>
  );
}
