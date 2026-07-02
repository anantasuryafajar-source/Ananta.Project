"use client";
import { useEffect, useState, useRef, type FormEvent } from "react";
import { Plus, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { readSheet } from "@/lib/excel";
import { rupiah } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/form";

type Contact = {
  id: string; name: string; type: string; phone: string | null;
  payment_term_days: number; credit_limit: string;
};

const KOSONG = {
  type: "customer", name: "", npwp: "", email: "", phone: "",
  address: "", payment_term_days: "0", credit_limit: "0",
};

export default function KontakPage() {
  const [items, setItems] = useState<Contact[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...KOSONG });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  async function handleImport(file: File) {
    setImportMsg(null); setImporting(true);
    try {
      const rows = await readSheet(file);
      if (rows.length === 0) throw new Error("File kosong atau tanpa data.");
      const first = rows[0];
      for (const col of ["name"]) {
        if (!(col in first)) throw new Error(`Kolom wajib: ${["name"].join(", ")}.`);
      }
      const res = await api<{ created: number; updated: number; failed: { row: number; reason: string }[] }>(
        "/contacts/import", { method: "POST", body: JSON.stringify({ rows }) });
      const failNote = res.failed.length
        ? ` Gagal ${res.failed.length} baris (baris ${res.failed[0].row}: ${res.failed[0].reason}${res.failed.length > 1 ? " …" : ""})`
        : "";
      setImportMsg(`Import selesai: ${res.created} baru, ${res.updated} diperbarui.${failNote}`);
      muat();
    } catch (err) {
      setImportMsg(err instanceof Error ? err.message : "Gagal import file.");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function muat() {
    api<Contact[]>("/contacts").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(muat, []);

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await api("/contacts", {
        method: "POST",
        body: JSON.stringify({
          type: form.type,
          name: form.name.trim(),
          npwp: form.npwp || null,
          email: form.email || null,
          phone: form.phone || null,
          address: form.address || null,
          payment_term_days: Number(form.payment_term_days) || 0,
          credit_limit: form.credit_limit || "0",
        }),
      });
      setOpen(false);
      setForm({ ...KOSONG });
      muat();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Gagal menyimpan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Topbar title="Kontak" />
      <div className="p-6">
        <div className="mb-4 flex items-center justify-end gap-2">
          <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImport(f); }} />
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={importing}>
            <Upload size={16} /> {importing ? "Mengimpor…" : "Import Excel"}
          </Button>
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} /> Tambah Kontak
          </Button>
        </div>
        {importMsg && <Card className="mb-4"><p className="text-sm text-ink-muted">{importMsg}</p></Card>}

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada kontak.</p>
            <p className="mt-1 text-sm text-ink-muted">Tambah pelanggan atau pemasok pertamamu.</p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-caption text-ink-muted">
                  <th className="px-4 py-3 font-medium">Nama</th>
                  <th className="px-4 py-3 font-medium">Tipe</th>
                  <th className="px-4 py-3 font-medium">Termin</th>
                  <th className="px-4 py-3 text-right font-medium">Limit kredit</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{c.name}</td>
                    <td className="px-4 py-3 text-ink-muted capitalize">{c.type}</td>
                    <td className="px-4 py-3 text-ink-muted">{c.payment_term_days} hari</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(c.credit_limit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Tambah Kontak">
        <form onSubmit={simpan} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Tipe">
              <Select value={form.type} onChange={(e) => set("type", e.target.value)}>
                <option value="customer">Pelanggan</option>
                <option value="supplier">Pemasok</option>
                <option value="both">Keduanya</option>
              </Select>
            </Field>
            <Field label="Nama">
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="PT Contoh Jaya" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="NPWP">
              <Input value={form.npwp} onChange={(e) => set("npwp", e.target.value)} placeholder="opsional" />
            </Field>
            <Field label="Telepon">
              <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="opsional" />
            </Field>
          </div>
          <Field label="Email">
            <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="opsional" />
          </Field>
          <Field label="Alamat">
            <Textarea rows={2} value={form.address} onChange={(e) => set("address", e.target.value)} placeholder="opsional" />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Termin (hari)">
              <Input type="number" min={0} value={form.payment_term_days} onChange={(e) => set("payment_term_days", e.target.value)} />
            </Field>
            <Field label="Limit Kredit (Rp)">
              <Input type="number" min={0} value={form.credit_limit} onChange={(e) => set("credit_limit", e.target.value)} />
            </Field>
          </div>

          {formError && <p className="text-sm text-danger">{formError}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
