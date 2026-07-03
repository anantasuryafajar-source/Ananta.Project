"use client";
import { useEffect, useState, useRef, useMemo, type FormEvent } from "react";
import { Plus, Upload, Pencil, Trash2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { readSheet } from "@/lib/excel";
import { rupiah } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select } from "@/components/ui/form";

type Product = {
  id: string; sku: string; name: string; unit: string;
  sale_price: string; purchase_price: string;
};
type StockItem = { sku: string; quantity: string; avg_cost: string; value: string };
type Stock = { items: StockItem[]; total_value: string };

const KOSONG = {
  sku: "", name: "", kind: "good", unit: "pcs",
  sale_price: "0", purchase_price: "0", min_stock: "0",
};

export default function ProdukPage() {
  const [items, setItems] = useState<Product[] | null>(null);
  const [stock, setStock] = useState<Record<string, StockItem>>({});
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...KOSONG });
  const [editId, setEditId] = useState<string | null>(null);
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
      for (const col of ["sku", "name"]) {
        if (!(col in first)) throw new Error(`Kolom wajib: ${["sku", "name"].join(", ")}.`);
      }
      const res = await api<{ created: number; updated: number; failed: { row: number; reason: string }[] }>(
        "/products/import", { method: "POST", body: JSON.stringify({ rows }) });
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
    api<Product[]>("/products").then(setItems).catch((e) => setError(e.message));
    api<Stock>("/reports/stock-valuation")
      .then((s) => setStock(Object.fromEntries(s.items.map((i) => [i.sku, i]))))
      .catch(() => {});
  }
  useEffect(muat, []);

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    // --- validasi ramah ---
    if (!form.name.trim()) return setFormError("Nama produk wajib diisi.");
    if (!form.sku.trim()) return setFormError("SKU wajib diisi.");
    const modal = Number(form.purchase_price || 0);
    const jual = Number(form.sale_price || 0);
    const minst = Number(form.min_stock || 0);
    if (modal < 0 || jual < 0 || minst < 0) return setFormError("Harga & stok minimum tidak boleh negatif.");
    if (jual > 0 && modal > 0 && jual < modal)
      return setFormError("Harga jual di bawah harga modal — periksa kembali (rugi per unit).");
    setSaving(true);
    try {
      await api(editId ? `/products/${editId}` : "/products", {
        method: editId ? "PATCH" : "POST",
        body: JSON.stringify({
          sku: form.sku.trim(),
          name: form.name.trim(),
          kind: form.kind,
          unit: form.unit.trim() || "pcs",
          sale_price: form.sale_price || "0",
          purchase_price: form.purchase_price || "0",
          min_stock: form.min_stock || "0",
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

  function bukaEdit(p: Product) {
    setFormError(null);
    setEditId(p.id);
    setForm({
      sku: p.sku, name: p.name, kind: "good", unit: p.unit,
      sale_price: p.sale_price, purchase_price: p.purchase_price,
      min_stock: (p as any).min_stock ?? "0",
    });
    setOpen(true);
  }

  async function hapus(p: Product) {
    if (!window.confirm(`Hapus produk "${p.name}"? Hanya bisa bila belum pernah dipakai transaksi. Hanya owner.`)) return;
    try {
      await api(`/products/${p.id}`, { method: "DELETE" });
      muat();
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal menghapus."); }
  }

  const filtered = useMemo(() => {
    if (!items) return null;
    const t = q.trim().toLowerCase();
    if (!t) return items;
    return items.filter((p) =>
      p.name.toLowerCase().includes(t) || (p.sku ?? "").toLowerCase().includes(t));
  }, [items, q]);

  return (
    <>
      <Topbar title="Produk & Stok" />
      <div className="p-6">
        <div className="mb-4 flex items-center justify-end gap-2">
          <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImport(f); }} />
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={importing}>
            <Upload size={16} /> {importing ? "Mengimpor…" : "Import Excel"}
          </Button>
          <Button onClick={() => { setEditId(null); setForm({ ...KOSONG }); setFormError(null); setOpen(true); }}>
            <Plus size={16} /> Tambah Produk
          </Button>
        </div>
        {importMsg && <Card className="mb-4"><p className="text-sm text-ink-muted">{importMsg}</p></Card>}

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items && items.length > 0 && (
          <div className="mb-3 flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-[var(--radius-input)] border border-line bg-surface px-3 py-1.5">
              <Search size={15} className="text-ink-subtle" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nama atau SKU…"
                className="w-64 bg-transparent text-sm text-ink outline-none placeholder:text-ink-subtle" />
            </div>
            <span className="text-caption text-ink-subtle">{filtered?.length ?? 0} dari {items.length} produk</span>
          </div>
        )}
        {filtered && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Nama</th>
                <th className="px-4 py-3 text-right font-medium">Modal</th>
                <th className="px-4 py-3 text-right font-medium">Harga Jual</th>
                <th className="px-4 py-3 text-right font-medium">Stok</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
                <th className="w-16" />
              </tr></thead>
              <tbody>
                {filtered.map((p) => {
                  const s = stock[p.sku];
                  return (
                    <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-3 text-ink-muted">{p.sku}</td>
                      <td className="px-4 py-3 text-ink">{p.name}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(p.purchase_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(p.sale_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{s ? Number(s.quantity) : 0}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{s ? rupiah(s.value) : rupiah(0)}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">
                          <button onClick={() => bukaEdit(p)} title="Edit produk"
                            className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-ink">
                            <Pencil size={15} />
                          </button>
                          <button onClick={() => hapus(p)} title="Hapus (hanya bila belum dipakai; owner)"
                            className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editId ? "Edit Produk" : "Tambah Produk"}>
        <form onSubmit={simpan} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="SKU">
              <Input value={form.sku} onChange={(e) => set("sku", e.target.value)} required placeholder="BRG-001" />
            </Field>
            <Field label="Jenis">
              <Select value={form.kind} onChange={(e) => set("kind", e.target.value)}>
                <option value="good">Barang</option>
                <option value="service">Jasa</option>
              </Select>
            </Field>
          </div>
          <Field label="Nama Produk">
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="Contoh Produk" />
          </Field>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Satuan">
              <Input value={form.unit} onChange={(e) => set("unit", e.target.value)} placeholder="pcs" />
            </Field>
            <Field label="Harga Beli (Rp)">
              <Input type="number" min={0} value={form.purchase_price} onChange={(e) => set("purchase_price", e.target.value)} />
            </Field>
            <Field label="Harga Jual (Rp)">
              <Input type="number" min={0} value={form.sale_price} onChange={(e) => set("sale_price", e.target.value)} />
            </Field>
          </div>
          <Field label="Stok Minimum">
            <Input type="number" min={0} value={form.min_stock} onChange={(e) => set("min_stock", e.target.value)} />
          </Field>

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
