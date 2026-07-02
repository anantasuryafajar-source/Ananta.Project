"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Building2, Warehouse as WhIcon, Users, Pencil } from "lucide-react";
import { api } from "@/lib/api";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Textarea } from "@/components/ui/form";

type Company = { name: string; npwp: string | null; address: string | null; currency: string; costing_method: string };
type Warehouse = { id: string; code: string; name: string; is_default: boolean };
type UserRow = { id: string; full_name: string; email: string; is_active: boolean; roles: string[] };
type RoleOpt = { id: string; name: string; label: string };

export default function PengaturanPage() {
  const [company, setCompany] = useState<Company | null>(null);
  const [whs, setWhs] = useState<Warehouse[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleOpt[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [openWh, setOpenWh] = useState(false);
  const [whForm, setWhForm] = useState({ code: "", name: "" });

  const [openCo, setOpenCo] = useState(false);
  const [coForm, setCoForm] = useState({ name: "", npwp: "", address: "" });

  const [openUser, setOpenUser] = useState(false);
  const [uf, setUf] = useState({ full_name: "", email: "", password: "", roles: ["viewer"] as string[] });

  const [editUser, setEditUser] = useState<UserRow | null>(null);
  const [eu, setEu] = useState<{ roles: string[]; is_active: boolean }>({ roles: [], is_active: true });

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function muat() {
    api<Company>("/settings/company").then((c) => {
      setCompany(c);
      setCoForm({ name: c.name, npwp: c.npwp ?? "", address: c.address ?? "" });
    }).catch((e) => setError(e.message));
    api<Warehouse[]>("/warehouses").then(setWhs).catch(() => {});
    api<UserRow[]>("/settings/users").then(setUsers).catch(() => {});
    api<RoleOpt[]>("/settings/roles").then(setRoles).catch(() => {});
  }
  useEffect(muat, []);

  async function simpanWh(e: FormEvent) {
    e.preventDefault(); setFormError(null);
    try {
      await api("/warehouses", { method: "POST", body: JSON.stringify({ ...whForm, is_default: false }) });
      setOpenWh(false); setWhForm({ code: "", name: "" }); muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal."); }
  }

  async function simpanCo(e: FormEvent) {
    e.preventDefault(); setFormError(null); setSaving(true);
    try {
      await api("/settings/company", {
        method: "PATCH",
        body: JSON.stringify({ name: coForm.name.trim(), npwp: coForm.npwp || null, address: coForm.address || null }),
      });
      setOpenCo(false); muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal menyimpan."); }
    finally { setSaving(false); }
  }

  async function simpanUser(e: FormEvent) {
    e.preventDefault(); setFormError(null);
    if (uf.password.length < 8) return setFormError("Password minimal 8 karakter.");
    if (uf.roles.length === 0) return setFormError("Pilih minimal satu peran.");
    setSaving(true);
    try {
      await api("/settings/users", {
        method: "POST",
        body: JSON.stringify({ ...uf, full_name: uf.full_name.trim(), email: uf.email.trim() }),
      });
      setOpenUser(false);
      setUf({ full_name: "", email: "", password: "", roles: ["viewer"] });
      muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal menyimpan."); }
    finally { setSaving(false); }
  }

  async function simpanEdit(e: FormEvent) {
    e.preventDefault();
    if (!editUser) return;
    setFormError(null);
    if (eu.roles.length === 0) return setFormError("Pilih minimal satu peran.");
    setSaving(true);
    try {
      await api(`/settings/users/${editUser.id}`, {
        method: "PATCH",
        body: JSON.stringify({ roles: eu.roles, is_active: eu.is_active }),
      });
      setEditUser(null); muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal menyimpan."); }
    finally { setSaving(false); }
  }

  function toggleRole(list: string[], name: string): string[] {
    return list.includes(name) ? list.filter((r) => r !== name) : [...list, name];
  }

  return (
    <>
      <Topbar title="Pengaturan" />
      <div className="space-y-4 p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}

        {/* Perusahaan */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Building2 size={18} className="text-primary" />
              <p className="text-sm font-medium text-ink">Perusahaan</p>
            </div>
            <Button variant="secondary" onClick={() => { setFormError(null); setOpenCo(true); }}><Pencil size={14} /> Edit</Button>
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
        </Card>

        {/* Gudang */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <WhIcon size={18} className="text-primary" />
              <p className="text-sm font-medium text-ink">Gudang</p>
            </div>
            <Button variant="secondary" onClick={() => { setFormError(null); setOpenWh(true); }}><Plus size={15} /> Tambah</Button>
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
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users size={18} className="text-primary" />
              <p className="text-sm font-medium text-ink">Pengguna & Peran</p>
            </div>
            <Button variant="secondary" onClick={() => { setFormError(null); setOpenUser(true); }}><Plus size={15} /> Tambah User</Button>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-caption uppercase text-ink-subtle"><th className="py-1">Nama</th><th>Email</th><th>Peran</th><th className="text-right">Status</th><th className="w-16" /></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-line">
                  <td className="py-1 text-ink">{u.full_name}</td>
                  <td className="text-ink-muted">{u.email}</td>
                  <td className="text-ink-muted capitalize">{u.roles.join(", ") || "—"}</td>
                  <td className="text-right">{u.is_active ? <span className="text-success">Aktif</span> : <span className="text-ink-subtle">Nonaktif</span>}</td>
                  <td className="text-right">
                    <button onClick={() => { setFormError(null); setEu({ roles: u.roles, is_active: u.is_active }); setEditUser(u); }}
                      className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-ink" aria-label="Edit user">
                      <Pencil size={15} />
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-ink-subtle">Belum ada pengguna.</td></tr>}
            </tbody>
          </table>
          <p className="mt-3 text-caption text-ink-subtle">Menambah/mengubah user hanya bisa dilakukan oleh pemilik (owner).</p>
        </Card>
      </div>

      {/* Modal edit perusahaan */}
      <Modal open={openCo} onClose={() => setOpenCo(false)} title="Edit Perusahaan">
        <form onSubmit={simpanCo} className="space-y-4">
          <Field label="Nama"><Input value={coForm.name} onChange={(e) => setCoForm((f) => ({ ...f, name: e.target.value }))} required /></Field>
          <Field label="NPWP"><Input value={coForm.npwp} onChange={(e) => setCoForm((f) => ({ ...f, npwp: e.target.value }))} placeholder="opsional" /></Field>
          <Field label="Alamat"><Textarea rows={2} value={coForm.address} onChange={(e) => setCoForm((f) => ({ ...f, address: e.target.value }))} placeholder="opsional" /></Field>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenCo(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      {/* Modal tambah gudang */}
      <Modal open={openWh} onClose={() => setOpenWh(false)} title="Tambah Gudang">
        <form onSubmit={simpanWh} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Kode"><Input value={whForm.code} onChange={(e) => setWhForm((f) => ({ ...f, code: e.target.value }))} required placeholder="GD-02" /></Field>
            <Field label="Nama"><Input value={whForm.name} onChange={(e) => setWhForm((f) => ({ ...f, name: e.target.value }))} required placeholder="Gudang Cabang" /></Field>
          </div>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenWh(false)}>Batal</Button>
            <Button type="submit">Simpan</Button>
          </div>
        </form>
      </Modal>

      {/* Modal tambah user */}
      <Modal open={openUser} onClose={() => setOpenUser(false)} title="Tambah User">
        <form onSubmit={simpanUser} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Nama lengkap"><Input value={uf.full_name} onChange={(e) => setUf((f) => ({ ...f, full_name: e.target.value }))} required /></Field>
            <Field label="Email"><Input type="email" value={uf.email} onChange={(e) => setUf((f) => ({ ...f, email: e.target.value }))} required /></Field>
          </div>
          <Field label="Password" hint="Minimal 8 karakter">
            <Input type="password" value={uf.password} onChange={(e) => setUf((f) => ({ ...f, password: e.target.value }))} required />
          </Field>
          <Field label="Peran">
            <div className="flex flex-wrap gap-3 pt-1">
              {roles.map((r) => (
                <label key={r.name} className="flex items-center gap-1.5 text-sm text-ink">
                  <input type="checkbox" checked={uf.roles.includes(r.name)}
                    onChange={() => setUf((f) => ({ ...f, roles: toggleRole(f.roles, r.name) }))} />
                  {r.label}
                </label>
              ))}
            </div>
          </Field>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenUser(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      {/* Modal edit user */}
      <Modal open={!!editUser} onClose={() => setEditUser(null)} title={`Edit — ${editUser?.full_name ?? ""}`}>
        <form onSubmit={simpanEdit} className="space-y-4">
          <Field label="Peran">
            <div className="flex flex-wrap gap-3 pt-1">
              {roles.map((r) => (
                <label key={r.name} className="flex items-center gap-1.5 text-sm text-ink">
                  <input type="checkbox" checked={eu.roles.includes(r.name)}
                    onChange={() => setEu((f) => ({ ...f, roles: toggleRole(f.roles, r.name) }))} />
                  {r.label}
                </label>
              ))}
            </div>
          </Field>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={eu.is_active}
              onChange={(e) => setEu((f) => ({ ...f, is_active: e.target.checked }))} />
            Akun aktif
          </label>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setEditUser(null)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
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
