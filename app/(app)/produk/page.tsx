"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
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
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...KOSONG });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

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
    setSaving(true);
    setFormError(null);
    try {
      await api("/products", {
        method: "POST",
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

  return (
    <>
      <Topbar title="Produk & Stok" />
      <div className="p-6">
        <div className="mb-4 flex justify-end">
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} /> Tambah Produk
          </Button>
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Nama</th>
                <th className="px-4 py-3 text-right font-medium">Modal</th>
                <th className="px-4 py-3 text-right font-medium">Harga Jual</th>
                <th className="px-4 py-3 text-right font-medium">Stok</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
              </tr></thead>
              <tbody>
                {items.map((p) => {
                  const s = stock[p.sku];
                  return (
                    <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-3 text-ink-muted">{p.sku}</td>
                      <td className="px-4 py-3 text-ink">{p.name}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(p.purchase_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(p.sale_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{s ? Number(s.quantity) : 0}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{s ? rupiah(s.value) : rupiah(0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Tambah Produk">
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
