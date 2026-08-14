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
  pack_unit: string; pack_size: number;
  pack_purchase_price: string;   // modal per dus (yang diketik)
  purchase_price: string;        // modal per botol (dihitung sistem)
  min_stock: string;
  note: string | null;           // keterangan kondisi barang
};
type StockItem = {
  sku: string; quantity: string; qty_display: string;
  avg_cost: string; value: string;
};
type Stock = { items: StockItem[]; total_value: string };

// Harga jual TIDAK ada di master produk: berbeda per customer, ditentukan saat
// pembuatan faktur penjualan. SKU juga tidak diketik — dibuat otomatis.
const KOSONG = {
  name: "", kind: "good", pack_size: "12",
  pack_purchase_price: "0", min_stock: "0", note: "",
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
      // Hanya `name` yang wajib. Kolom lain opsional: `pack_size` (isi per dus,
      // default 12) dan `purchase_price` yang dibaca sebagai modal PER DUS.
      if (!("name" in rows[0]))
        throw new Error("Kolom wajib: name. Opsional: pack_size (isi per dus), purchase_price (modal per dus), min_stock.");
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
    const modalDus = Number(form.pack_purchase_price || 0);
    const isiDus = Number(form.pack_size || 0);
    const minst = Number(form.min_stock || 0);
    if (modalDus < 0 || minst < 0)
      return setFormError("Harga modal & stok minimum tidak boleh negatif.");
    if (!Number.isInteger(isiDus) || isiDus < 1)
      return setFormError("Isi per dus harus bilangan bulat minimal 1 (mis. 12, 24, 48).");
    setSaving(true);
    try {
      await api(editId ? `/products/${editId}` : "/products", {
        method: editId ? "PATCH" : "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          kind: form.kind,
          unit: "botol",
          pack_unit: "dus",
          pack_size: isiDus,
          // Modal dikirim per DUS; backend membagi ke per botol.
          pack_purchase_price: form.pack_purchase_price || "0",
          min_stock: form.min_stock || "0",
          // kosong = hapus keterangan
          note: form.note.trim() || null,
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
      name: p.name, kind: "good",
      pack_size: String(p.pack_size ?? 12),
      pack_purchase_price: p.pack_purchase_price ?? "0",
      min_stock: p.min_stock ?? "0",
      note: p.note ?? "",
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

  // Pratinjau modal per botol supaya user langsung sadar kalau salah satuan.
  const modalPerBotol = useMemo(() => {
    const dus = Number(form.pack_purchase_price || 0);
    const isi = Number(form.pack_size || 0);
    if (!dus || !isi || isi < 1) return null;
    return dus / isi;
  }, [form.pack_purchase_price, form.pack_size]);

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
                <th className="px-4 py-3 font-medium">Nama</th>
                <th className="px-4 py-3 text-center font-medium">Isi/Dus</th>
                <th className="px-4 py-3 text-right font-medium">Modal / Dus</th>
                <th className="px-4 py-3 text-right font-medium">Modal / Botol</th>
                <th className="px-4 py-3 text-right font-medium">Stok</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
                <th className="w-16" />
              </tr></thead>
              <tbody>
                {filtered.map((p) => {
                  const s = stock[p.sku];
                  return (
                    <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-3 text-ink">
                        {p.name}
                        {/* Keterangan kondisi barang dari pembelian terakhir. */}
                        {p.note && (
                          <span className="mt-0.5 block text-caption text-ink-subtle">{p.note}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center tabular-nums text-ink-muted">{p.pack_size} btl</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(p.pack_purchase_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(p.purchase_price)}</td>
                      {/* Stok disimpan dalam botol, ditampilkan sebagai "1 dus 5 botol". */}
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{s ? s.qty_display : "0 botol"}</td>
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
          <div className="grid grid-cols-[1fr_auto] gap-4">
            <Field label="Nama Produk">
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="Chivas 200ml" />
            </Field>
            <Field label="Jenis">
              <Select value={form.kind} onChange={(e) => set("kind", e.target.value)}>
                <option value="good">Barang</option>
                <option value="service">Jasa</option>
              </Select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Isi per Dus (botol)">
              <Input type="number" min={1} step={1} value={form.pack_size}
                onChange={(e) => set("pack_size", e.target.value)} placeholder="12" />
            </Field>
            {/* Label harus eksplisit "per dus": inilah cara client mencatat modal,
                dan salah baca sebagai per botol membuat HPP salah 12-48x. */}
            <Field label="Harga Modal per DUS (Rp)">
              <Input type="number" min={0} value={form.pack_purchase_price}
                onChange={(e) => set("pack_purchase_price", e.target.value)} placeholder="1800000" />
            </Field>
          </div>

          {modalPerBotol !== null && (
            <p className="-mt-2 text-caption text-ink-muted">
              Setara <span className="tabular-nums text-ink">{rupiah(modalPerBotol)}</span> per botol
              {" "}({form.pack_size} botol per dus). Stok & HPP dihitung per botol.
            </p>
          )}

          <Field label="Stok Minimum (botol)">
            <Input type="number" min={0} value={form.min_stock} onChange={(e) => set("min_stock", e.target.value)} />
          </Field>

          <Field label="Keterangan"
            hint="Terisi otomatis dari keterangan pembelian terakhir. Kosongkan untuk menghapus — dokumen pembelian tidak ikut berubah.">
            <Input value={form.note} maxLength={255} placeholder="mis. 2 botol pecah"
              onChange={(e) => set("note", e.target.value)} />
          </Field>

          <p className="text-caption text-ink-subtle">
            Harga jual tidak diisi di sini — berbeda tiap customer dan ditentukan
            saat membuat faktur penjualan.
          </p>

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
