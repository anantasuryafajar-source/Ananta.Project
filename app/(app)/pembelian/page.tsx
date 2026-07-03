"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Trash2, Ban } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea, NumCell } from "@/components/ui/form";

type Bill = {
  id: string; number: string; date: string; status: string;
  total: string; paid_total: string;
};
type Contact = { id: string; name: string; type: string };
type Product = { id: string; name: string; purchase_price: string };

type Line = {
  product_id: string; description: string;
  quantity: string; unit_cost: string; discount: string; tax_rate: string;
};

const STATUS: Record<string, string> = {
  void: "text-ink-subtle line-through",
  posted: "text-primary", paid: "text-success", overdue: "text-danger",
};

const today = () => new Date().toISOString().slice(0, 10);
const baris = (): Line => ({
  product_id: "", description: "", quantity: "1",
  unit_cost: "0", discount: "0", tax_rate: "0",
});

function lineTotal(l: Line): number {
  const q = Number(l.quantity) || 0;
  const c = Number(l.unit_cost) || 0;
  const d = Number(l.discount) || 0;
  const t = Number(l.tax_rate) || 0;
  const net = Math.max(q * c - d, 0);
  return net + net * (t / 100);
}

export default function PembelianPage() {
  const [items, setItems] = useState<Bill[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [contactId, setContactId] = useState("");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([baris()]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function hapusPermanen(b: Bill) {
    if (!window.confirm(`HAPUS PERMANEN tagihan ${b.number}?\n\nDokumen, jurnal, pembayaran & stoknya dihapus TOTAL. Khusus data uji. Hanya owner.`)) return;
    try {
      await api(`/bills/${b.id}/hard`, { method: "DELETE" });
      muat();
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal menghapus."); }
  }

  async function batalkan(b: Bill) {
    if (!window.confirm(`Batalkan tagihan ${b.number}? Jurnal balik dibuat & stok ditarik kembali. Hanya owner.`)) return;
    try {
      await api(`/bills/${b.id}/void`, { method: "POST" });
      muat();
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal membatalkan."); }
  }

  function muat() {
    api<Bill[]>("/bills").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(muat, []);

  function bukaForm() {
    setFormError(null);
    setContactId(""); setDate(today()); setNotes(""); setLines([baris()]);
    setOpen(true);
    api<Contact[]>("/contacts?type=supplier").then(setContacts).catch(() => {});
    api<Product[]>("/products").then(setProducts).catch(() => {});
  }

  function setLine(i: number, patch: Partial<Line>) {
    setLines((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function pilihProduk(i: number, pid: string) {
    const p = products.find((x) => x.id === pid);
    setLine(i, {
      product_id: pid,
      description: p?.name ?? "",
      unit_cost: p ? p.purchase_price : lines[i].unit_cost,
    });
  }

  const total = lines.reduce((s, l) => s + lineTotal(l), 0);

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!contactId) return setFormError("Pilih pemasok dulu.");
    const valid = lines.filter((l) => Number(l.quantity) > 0);
    if (valid.length === 0) return setFormError("Tambahkan minimal satu baris.");
    setSaving(true);
    try {
      await api("/bills", {
        method: "POST",
        body: JSON.stringify({
          contact_id: contactId,
          date,
          notes: notes || null,
          lines: valid.map((l) => ({
            product_id: l.product_id || null,
            description: l.description || null,
            quantity: l.quantity,
            unit_cost: l.unit_cost || "0",
            discount: l.discount || "0",
            tax_rate: l.tax_rate || "0",
          })),
        }),
      });
      setOpen(false);
      muat();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Gagal menyimpan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Topbar title="Pembelian / Pengadaan" />
      <div className="p-6">
        <div className="mb-4 flex justify-end">
          <Button onClick={bukaForm}><Plus size={16} /> Buat Pengadaan</Button>
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada pengadaan.</p>
            <p className="mt-1 text-sm text-ink-muted">Klik “Buat Pengadaan” — stok masuk, average cost &amp; jurnal utang otomatis.</p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No. Bill</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 text-right font-medium">Terbayar</th>
                <th className="w-12" />
              </tr></thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{b.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(b.date)}</td>
                    <td className={`px-4 py-3 capitalize ${STATUS[b.status] ?? "text-ink-muted"}`}>{b.status}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(b.total)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(b.paid_total)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        {b.status !== "void" && Number(b.paid_total) === 0 && (
                          <button onClick={() => batalkan(b)} title="Batalkan (void) — hanya owner"
                            className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
                            <Ban size={15} />
                          </button>
                        )}
                        <button onClick={() => hapusPermanen(b)} title="Hapus permanen (data uji) — hanya owner"
                          className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Buat Pengadaan / Pembelian" width="max-w-3xl">
        <form onSubmit={simpan} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Pemasok">
              <Select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
                <option value="">— pilih pemasok —</option>
                {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Tanggal">
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required
                className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" />
            </Field>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium text-ink">Baris</span>
              <Button type="button" variant="secondary" onClick={() => setLines((l) => [...l, baris()])}>
                <Plus size={14} /> Baris
              </Button>
            </div>
            <div className="overflow-x-auto rounded-[var(--radius-input)] border border-line">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line bg-surface-sunken text-left text-caption text-ink-muted">
                  <th className="px-2 py-2 font-medium">Produk / Deskripsi</th>
                  <th className="px-2 py-2 text-right font-medium">Qty</th>
                  <th className="px-2 py-2 text-right font-medium">Harga Beli</th>
                  <th className="px-2 py-2 text-right font-medium">Diskon</th>
                  <th className="px-2 py-2 text-right font-medium">Pajak %</th>
                  <th className="px-2 py-2 text-right font-medium">Subtotal</th>
                  <th className="w-8" />
                </tr></thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-2 py-1.5">
                        <Select value={l.product_id} onChange={(e) => pilihProduk(i, e.target.value)} className="mb-1">
                          <option value="">— manual —</option>
                          {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </Select>
                        {!l.product_id && (
                          <input value={l.description} onChange={(e) => setLine(i, { description: e.target.value })}
                            placeholder="Deskripsi"
                            className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-2 py-1 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" />
                        )}
                      </td>
                      <td className="px-2 py-1.5 w-20"><NumCell value={l.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} /></td>
                      <td className="px-2 py-1.5 w-28"><NumCell value={l.unit_cost} onChange={(e) => setLine(i, { unit_cost: e.target.value })} /></td>
                      <td className="px-2 py-1.5 w-24"><NumCell value={l.discount} onChange={(e) => setLine(i, { discount: e.target.value })} /></td>
                      <td className="px-2 py-1.5 w-16"><NumCell value={l.tax_rate} onChange={(e) => setLine(i, { tax_rate: e.target.value })} /></td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-ink-muted">{rupiah(lineTotal(l))}</td>
                      <td className="px-1 text-center">
                        {lines.length > 1 && (
                          <button type="button" onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))}
                            className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger" aria-label="Hapus baris">
                            <Trash2 size={15} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-2 flex justify-end text-sm">
              <span className="mr-3 text-ink-muted">Total</span>
              <span className="font-semibold tabular-nums text-ink">{rupiah(total)}</span>
            </div>
          </div>

          <Field label="Catatan">
            <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="opsional" />
          </Field>

          {formError && <p className="text-sm text-danger">{formError}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Memproses…" : "Simpan Pengadaan"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
