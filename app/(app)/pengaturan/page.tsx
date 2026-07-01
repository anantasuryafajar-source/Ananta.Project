"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Building2, Warehouse as WhIcon, Users } from "lucide-react";
import { api } from "@/lib/api";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field } from "@/components/ui/form";

type Company = { name: string; npwp: string | null; address: string | null; currency: string; costing_method: string };
type Warehouse = { id: string; code: string; name: string; is_default: boolean };
type UserRow = { id: string; full_name: string; email: string; is_active: boolean; roles: string[] };

export default function PengaturanPage() {
  const [company, setCompany] = useState<Company | null>(null);
  const [whs, setWhs] = useState<Warehouse[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [whForm, setWhForm] = useState({ code: "", name: "" });
  const [formError, setFormError] = useState<string | null>(null);

  function muat() {
    api<Company>("/settings/company").then(setCompany).catch((e) => setError(e.message));
    api<Warehouse[]>("/warehouses").then(setWhs).catch(() => {});
    api<UserRow[]>("/settings/users").then(setUsers).catch(() => {});
  }
  useEffect(muat, []);

  async function simpanWh(e: FormEvent) {
    e.preventDefault(); setFormError(null);
    try {
      await api("/warehouses", { method: "POST", body: JSON.stringify({ ...whForm, is_default: false }) });
      setOpen(false); setWhForm({ code: "", name: "" }); muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal."); }
  }

  return (
    <>
      <Topbar title="Pengaturan" />
      <div className="space-y-4 p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}

        {/* Perusahaan */}
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Building2 size={18} className="text-primary" />
            <p className="text-sm font-medium text-ink">Perusahaan</p>
          </div>
          {company ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <Info k="Nama" v={company.name} />
              <Info k="NPWP" v={company.npwp || "—"} />
              <Info k="Mata uang" v={company.currency} />
              <Info k="Metode HPP" v={company.costing_method === "average" ? "Rata-rata (average)" : company.costing_method} />
              <Info k="Alamat" v={company.address || "—"} />
            </dl>
          ) : <p className="text-sm text-ink-subtle">Memuat…</p>}
          <p className="mt-3 text-caption text-ink-subtle">Perubahan data perusahaan saat ini via seed/API. Form edit menyusul.</p>
        </Card>

        {/* Gudang */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <WhIcon size={18} className="text-primary" />
              <p className="text-sm font-medium text-ink">Gudang</p>
            </div>
            <Button variant="secondary" onClick={() => setOpen(true)}><Plus size={15} /> Tambah</Button>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-caption uppercase text-ink-subtle"><th className="py-1">Kode</th><th>Nama</th><th className="text-right">Default</th></tr></thead>
            <tbody>
              {whs.map((w) => (
                <tr key={w.id} className="border-t border-line">
                  <td className="py-1 text-ink-muted">{w.code}</td>
                  <td className="text-ink">{w.name}</td>
                  <td className="text-right">{w.is_default ? <span className="text-success">✓</span> : ""}</td>
                </tr>
              ))}
              {whs.length === 0 && <tr><td colSpan={3} className="py-3 text-center text-ink-subtle">Belum ada gudang.</td></tr>}
            </tbody>
          </table>
        </Card>

        {/* Pengguna */}
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Users size={18} className="text-primary" />
            <p className="text-sm font-medium text-ink">Pengguna & Peran</p>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-caption uppercase text-ink-subtle"><th className="py-1">Nama</th><th>Email</th><th>Peran</th><th className="text-right">Status</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-line">
                  <td className="py-1 text-ink">{u.full_name}</td>
                  <td className="text-ink-muted">{u.email}</td>
                  <td className="text-ink-muted capitalize">{u.roles.join(", ") || "—"}</td>
                  <td className="text-right">{u.is_active ? <span className="text-success">Aktif</span> : <span className="text-ink-subtle">Nonaktif</span>}</td>
                </tr>
              ))}
              {users.length === 0 && <tr><td colSpan={4} className="py-3 text-center text-ink-subtle">Belum ada pengguna.</td></tr>}
            </tbody>
          </table>
          <p className="mt-3 text-caption text-ink-subtle">Menambah pengguna/mengubah peran via API. Manajemen user penuh menyusul.</p>
        </Card>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Tambah Gudang">
        <form onSubmit={simpanWh} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Kode"><Input value={whForm.code} onChange={(e) => setWhForm((f) => ({ ...f, code: e.target.value }))} required placeholder="GD-02" /></Field>
            <Field label="Nama"><Input value={whForm.name} onChange={(e) => setWhForm((f) => ({ ...f, name: e.target.value }))} required placeholder="Gudang Cabang" /></Field>
          </div>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Batal</Button>
            <Button type="submit">Simpan</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function Info({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-caption uppercase text-ink-subtle">{k}</dt>
      <dd className="text-ink">{v}</dd>
    </div>
  );
}
