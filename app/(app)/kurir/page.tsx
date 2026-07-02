"use client";
import { useEffect, useState, useRef, type FormEvent } from "react";
import { Plus, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { readSheet } from "@/lib/excel";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/form";

type Courier = {
  id: string; number: string; date: string; courier_name: string;
  amount: string; supplier_share: string; company_share: string;
};
type Invoice = { id: string; number: string };

const today = () => new Date().toISOString().slice(0, 10);
const KOSONG = { courier_name: "", amount: "", supplier_share: "0", invoice_id: "", paid_account_code: "1-1000", note: "" };

export default function KurirPage() {
  const [items, setItems] = useState<Courier[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [form, setForm] = useState({ ...KOSONG });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  // Parse CSV sederhana: header wajib -> date,courier_name,amount[,invoice_number,supplier_share,note]
  async function handleCsv(file: File) {
    setImportMsg(null); setImporting(true);
    try {
      const parsed = await readSheet(file);
      if (parsed.length === 0) throw new Error("File kosong atau tanpa data.");
      const first = parsed[0];
      if (!("date" in first) || !("courier_name" in first) || !("amount" in first)) {
        throw new Error("Kolom wajib: date, courier_name, amount (opsional: invoice_number, supplier_share, note).");
      }
      const rows = parsed.map((r) => ({
        date: r.date, courier_name: r.courier_name, amount: r.amount,
        invoice_number: r.invoice_number || null,
        supplier_share: r.supplier_share || null,
        note: r.note || null,
      }));
      const res = await api<{ created: number; failed: { row: number; reason: string }[] }>(
        "/courier-expenses/import",
        { method: "POST", body: JSON.stringify({ rows }) },
      );
      const failNote = res.failed.length
        ? ` Gagal ${res.failed.length} baris (baris ${res.failed.map((f) => f.row).join(", ")}: ${res.failed[0].reason}${res.failed.length > 1 ? " …" : ""})`
        : "";
      setImportMsg(`Import selesai: ${res.created} baris masuk.${failNote}`);
      muat();
    } catch (err) {
      setImportMsg(err instanceof Error ? err.message : "Gagal import file.");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function muat() {
    api<Courier[]>("/courier-expenses").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(muat, []);

  function buka() {
    setFormError(null); setForm({ ...KOSONG }); setOpen(true);
    api<Invoice[]>("/invoices").then(setInvoices).catch(() => {});
  }
  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!(Number(form.amount) > 0)) return setFormError("Nominal ongkir harus lebih dari 0.");
    if (Number(form.supplier_share) > Number(form.amount)) return setFormError("Porsi supplier melebihi total ongkir.");
    setSaving(true);
    try {
      await api("/courier-expenses", {
        method: "POST",
        body: JSON.stringify({
          date: today(),
          courier_name: form.courier_name.trim(),
          amount: form.amount,
          supplier_share: form.supplier_share || "0",
          invoice_id: form.invoice_id || null,
          paid_account_code: form.paid_account_code,
          note: form.note || null,
        }),
      });
      setOpen(false); muat();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Gagal menyimpan.");
    } finally { setSaving(false); }
  }

  const share = Number(form.amount || 0) - Number(form.supplier_share || 0);

  return (
    <>
      <Topbar title="Kurir & Ongkir" />
      <div className="p-6">
        <div className="mb-4 flex items-center justify-end gap-2">
          <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleCsv(f); }} />
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={importing}>
            <Upload size={16} /> {importing ? "Mengimpor…" : "Import Excel/CSV"}
          </Button>
          <Button onClick={buka}><Plus size={16} /> Catat Ongkir</Button>
        </div>
        {importMsg && <Card className="mb-4"><p className="text-sm text-ink-muted">{importMsg}</p></Card>}

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada pengeluaran kurir.</p>
            <p className="mt-1 text-sm text-ink-muted">Catat ongkir dan tautkan ke faktur — jurnal beban otomatis dibuat.</p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Kurir</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 text-right font-medium">Supplier</th>
                <th className="px-4 py-3 text-right font-medium">Beban ASF</th>
              </tr></thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{c.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(c.date)}</td>
                    <td className="px-4 py-3 text-ink">{c.courier_name}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(c.amount)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(c.supplier_share)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(c.company_share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Catat Pengeluaran Ongkir">
        <form onSubmit={simpan} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Nama kurir/ekspedisi">
              <Input value={form.courier_name} onChange={(e) => set("courier_name", e.target.value)} required placeholder="JNE / kurir internal" />
            </Field>
            <Field label="Total ongkir (Rp)">
              <Input type="number" min={0} value={form.amount} onChange={(e) => set("amount", e.target.value)} required />
            </Field>
          </div>
          <Field label="Tautkan ke faktur (opsional)">
            <Select value={form.invoice_id} onChange={(e) => set("invoice_id", e.target.value)}>
              <option value="">— tidak ditautkan —</option>
              {invoices.map((i) => <option key={i.id} value={i.id}>{i.number}</option>)}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Ditanggung supplier (Rp)" hint="Untuk ekspedisi yang dibagi dengan supplier">
              <Input type="number" min={0} value={form.supplier_share} onChange={(e) => set("supplier_share", e.target.value)} />
            </Field>
            <Field label="Dibayar dari">
              <Select value={form.paid_account_code} onChange={(e) => set("paid_account_code", e.target.value)}>
                <option value="1-1000">Kas</option>
                <option value="1-1100">Bank</option>
                <option value="1-1110">Bank BCA - Silo</option>
                <option value="1-1120">Bank OCBC - Silo</option>
              </Select>
            </Field>
          </div>
          <p className="text-caption text-ink-subtle">Beban ASF (setelah dikurangi porsi supplier): <b className="text-ink">{rupiah(share > 0 ? share : 0)}</b></p>
          <Field label="Catatan"><Textarea rows={2} value={form.note} onChange={(e) => set("note", e.target.value)} placeholder="opsional" /></Field>

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
