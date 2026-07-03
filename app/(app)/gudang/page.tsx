"use client";
import { rupiah } from "@/lib/format";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, ArrowRightLeft, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Field, Select, NumCell } from "@/components/ui/form";
import { Input } from "@/components/ui/input";

type Warehouse = { id: string; code: string; name: string; is_default: boolean };
type StockRow = { product_id: string; sku: string; name: string; quantity: string; avg_cost: string };
type Product = { id: string; name: string };
type Line = { product_id: string; quantity: string };

const today = () => new Date().toISOString().slice(0, 10);

export default function GudangPage() {
  const [whs, setWhs] = useState<Warehouse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [stock, setStock] = useState<StockRow[]>([]);

  // form gudang
  const [openWh, setOpenWh] = useState(false);
  const [whForm, setWhForm] = useState({ code: "", name: "" });

  // form transfer
  const [openTf, setOpenTf] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [fromWh, setFromWh] = useState("");
  const [toWh, setToWh] = useState("");
  const [tfLines, setTfLines] = useState<Line[]>([{ product_id: "", quantity: "1" }]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function muat() {
    api<Warehouse[]>("/warehouses").then((w) => {
      setWhs(w);
      if (w.length && !selected) setSelected(w[0].id);
    }).catch((e) => setError(e.message));
  }
  useEffect(muat, []);
  useEffect(() => {
    if (selected) api<StockRow[]>(`/warehouses/${selected}/stock`).then(setStock).catch(() => setStock([]));
  }, [selected]);

  async function simpanWh(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/warehouses", { method: "POST", body: JSON.stringify({ ...whForm, is_default: false }) });
      setOpenWh(false); setWhForm({ code: "", name: "" }); muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal."); }
  }

  function bukaTransfer() {
    setFormError(null); setFromWh(selected || ""); setToWh(""); setTfLines([{ product_id: "", quantity: "1" }]);
    setOpenTf(true);
    api<Product[]>("/products").then(setProducts).catch(() => {});
  }

  async function simpanTransfer(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!fromWh || !toWh) return setFormError("Pilih gudang asal & tujuan.");
    if (fromWh === toWh) return setFormError("Gudang asal & tujuan tidak boleh sama.");
    const lines = tfLines.filter((l) => l.product_id && Number(l.quantity) > 0);
    if (!lines.length) return setFormError("Tambahkan minimal satu baris.");
    setSaving(true);
    try {
      await api("/transfers", {
        method: "POST",
        body: JSON.stringify({ from_warehouse_id: fromWh, to_warehouse_id: toWh, date: today(), lines }),
      });
      setOpenTf(false); muat();
      if (selected) api<StockRow[]>(`/warehouses/${selected}/stock`).then(setStock).catch(() => {});
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Gagal transfer.");
    } finally { setSaving(false); }
  }

  return (
    <>
      <Topbar title="Gudang & Transfer" />
      <div className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm text-ink-muted">Gudang:</span>
            <Select value={selected} onChange={(e) => setSelected(e.target.value)} className="w-56">
              {whs?.map((w) => <option key={w.id} value={w.id}>{w.name}{w.is_default ? " (default)" : ""}</option>)}
            </Select>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setOpenWh(true)}><Plus size={16} /> Gudang</Button>
            <Button onClick={bukaTransfer}><ArrowRightLeft size={16} /> Transfer Stok</Button>
          </div>
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {whs?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada gudang.</p>
            <p className="mt-1 text-sm text-ink-muted">Tambahkan gudang untuk mulai mengelola stok per lokasi.</p>
          </Card>
        )}

        {whs && whs.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Produk</th>
                <th className="px-4 py-3 text-right font-medium">Stok</th>
                <th className="px-4 py-3 text-right font-medium">Rata-rata Modal</th>
              </tr></thead>
              <tbody>
                {stock.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-6 text-center text-ink-subtle">Belum ada stok di gudang ini.</td></tr>
                )}
                {stock.map((s) => (
                  <tr key={s.product_id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink-muted">{s.sku}</td>
                    <td className="px-4 py-3 text-ink">{s.name}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{Number(s.quantity)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(s.avg_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      {/* Modal tambah gudang */}
      <Modal open={openWh} onClose={() => setOpenWh(false)} title="Tambah Gudang">
        <form onSubmit={simpanWh} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Kode"><Input value={whForm.code} onChange={(e) => setWhForm((f) => ({ ...f, code: e.target.value }))} required placeholder="GD-01" /></Field>
            <Field label="Nama"><Input value={whForm.name} onChange={(e) => setWhForm((f) => ({ ...f, name: e.target.value }))} required placeholder="Gudang Utama" /></Field>
          </div>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenWh(false)}>Batal</Button>
            <Button type="submit">Simpan</Button>
          </div>
        </form>
      </Modal>

      {/* Modal transfer */}
      <Modal open={openTf} onClose={() => setOpenTf(false)} title="Transfer Stok Antar-Gudang" width="max-w-2xl">
        <form onSubmit={simpanTransfer} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Dari gudang">
              <Select value={fromWh} onChange={(e) => setFromWh(e.target.value)} required>
                <option value="">— pilih —</option>
                {whs?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Field label="Ke gudang">
              <Select value={toWh} onChange={(e) => setToWh(e.target.value)} required>
                <option value="">— pilih —</option>
                {whs?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium text-ink">Barang</span>
              <Button type="button" variant="secondary" onClick={() => setTfLines((l) => [...l, { product_id: "", quantity: "1" }])}>
                <Plus size={14} /> Baris
              </Button>
            </div>
            <div className="rounded-[var(--radius-input)] border border-line">
              <table className="w-full text-sm">
                <tbody>
                  {tfLines.map((l, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-2 py-1.5">
                        <Select value={l.product_id} onChange={(e) => setTfLines((ls) => ls.map((x, idx) => idx === i ? { ...x, product_id: e.target.value } : x))}>
                          <option value="">— pilih produk —</option>
                          {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </Select>
                      </td>
                      <td className="w-24 px-2 py-1.5">
                        <NumCell value={l.quantity} onChange={(e) => setTfLines((ls) => ls.map((x, idx) => idx === i ? { ...x, quantity: e.target.value } : x))} />
                      </td>
                      <td className="w-8 px-1 text-center">
                        {tfLines.length > 1 && (
                          <button type="button" onClick={() => setTfLines((ls) => ls.filter((_, idx) => idx !== i))} className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
                            <Trash2 size={15} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenTf(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Memproses…" : "Transfer"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
