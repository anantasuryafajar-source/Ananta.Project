"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Trash2, Printer, Truck, Search, Ban, Wallet } from "lucide-react";
import { api } from "@/lib/api";
import { printInvoiceDoc, printDeliveryNote, type InvoiceDetail, type CompanyInfo } from "@/lib/print";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea, NumCell } from "@/components/ui/form";

type Invoice = {
  id: string; number: string; date: string; due_date: string | null;
  status: string; total: string; paid_total: string;
};
type Contact = { id: string; name: string; type: string };
type Product = { id: string; name: string; sale_price: string };

type Line = {
  product_id: string; description: string;
  quantity: string; unit_price: string; discount: string; tax_rate: string;
};

const STATUS: Record<string, string> = {
  draft: "text-ink-subtle", posted: "text-primary", paid: "text-success",
  overdue: "text-danger", void: "text-ink-subtle",
};

const today = () => new Date().toISOString().slice(0, 10);
const baris = (): Line => ({
  product_id: "", description: "", quantity: "1",
  unit_price: "0", discount: "0", tax_rate: "0",
});

function lineTotal(l: Line): number {
  const q = Number(l.quantity) || 0;
  const p = Number(l.unit_price) || 0;
  const d = Number(l.discount) || 0;
  const t = Number(l.tax_rate) || 0;
  const net = Math.max(q * p - d, 0);
  return net + net * (t / 100);
}

export default function PenjualanPage() {
  const [items, setItems] = useState<Invoice[] | null>(null);
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
  const [q, setQ] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [printing, setPrinting] = useState<string | null>(null);
  const [payFor, setPayFor] = useState<Invoice | null>(null);
  const [pays, setPays] = useState<{ id: string; number: string; date: string; amount: string }[]>([]);

  async function bukaPembayaran(v: Invoice) {
    setPayFor(v);
    try { setPays(await api(`/payments/received?invoice_id=${v.id}`)); }
    catch { setPays([]); }
  }
  async function voidPembayaran(pid: string) {
    if (!window.confirm("Batalkan pembayaran ini? Jurnal balik dibuat & sisa tagihan dikembalikan. Hanya owner.")) return;
    try {
      await api(`/payments/received/${pid}/void`, { method: "POST" });
      if (payFor) { await bukaPembayaran(payFor); }
      muat(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal membatalkan pembayaran."); }
  }
  const PAGE = 50;

  async function muat(reset = true, query = q) {
    try {
      const offset = reset ? 0 : (items?.length ?? 0);
      const res = await api<Invoice[]>(
        `/invoices?limit=${PAGE}&offset=${offset}${query ? `&q=${encodeURIComponent(query)}` : ""}`);
      setItems((prev) => (reset || !prev ? res : [...prev, ...res]));
      setHasMore(res.length === PAGE);
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal memuat."); }
  }
  useEffect(() => { muat(true, ""); }, []);

  async function muatLagi() {
    setLoadingMore(true);
    await muat(false);
    setLoadingMore(false);
  }

  async function cetak(id: string, mode: "faktur" | "sj") {
    setPrinting(id + mode);
    try {
      const [detail, co] = await Promise.all([
        api<InvoiceDetail>(`/invoices/${id}/detail`),
        api<CompanyInfo>("/settings/company"),
      ]);
      if (mode === "faktur") printInvoiceDoc(detail, co);
      else printDeliveryNote(detail, co);
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal menyiapkan dokumen."); }
    finally { setPrinting(null); }
  }

  async function hapusPermanen(v: Invoice) {
    if (!window.confirm(`HAPUS PERMANEN faktur ${v.number}?\n\nDokumen, jurnal, pembayaran & mutasi stoknya dihapus TOTAL tanpa jejak (stok dikembalikan). Khusus data uji. Hanya owner.`)) return;
    try {
      await api(`/invoices/${v.id}/hard`, { method: "DELETE" });
      muat(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal menghapus."); }
  }

  async function batalkan(v: Invoice) {
    if (!window.confirm(`Batalkan faktur ${v.number}? Jurnal balik dibuat & stok dikembalikan. Hanya owner yang bisa melakukan ini.`)) return;
    try {
      await api(`/invoices/${v.id}/void`, { method: "POST" });
      muat(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal membatalkan."); }
  }

  function bukaForm() {
    setFormError(null);
    setContactId(""); setDate(today()); setNotes(""); setLines([baris()]);
    setOpen(true);
    api<Contact[]>("/contacts?type=customer").then(setContacts).catch(() => {});
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
      unit_price: p ? p.sale_price : lines[i].unit_price,
    });
  }

  const total = lines.reduce((s, l) => s + lineTotal(l), 0);

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!contactId) return setFormError("Pilih pelanggan dulu.");
    const valid = lines.filter((l) => Number(l.quantity) > 0);
    if (valid.length === 0) return setFormError("Tambahkan minimal satu baris.");
    setSaving(true);
    try {
      await api("/invoices", {
        method: "POST",
        body: JSON.stringify({
          contact_id: contactId,
          date,
          notes: notes || null,
          lines: valid.map((l) => ({
            product_id: l.product_id || null,
            description: l.description || null,
            quantity: l.quantity,
            unit_price: l.unit_price || "0",
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
      <Topbar title="Penjualan" />
      <div className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 rounded-[var(--radius-input)] border border-line bg-surface px-3 py-1.5">
            <Search size={15} className="text-ink-subtle" />
            <input value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") muat(true); }}
              placeholder="Cari no. faktur… (Enter)"
              className="w-52 bg-transparent text-sm text-ink outline-none placeholder:text-ink-subtle" />
          </div>
          <Button onClick={bukaForm}><Plus size={16} /> Buat Faktur</Button>
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada faktur.</p>
            <p className="mt-1 text-sm text-ink-muted">Klik “Buat Faktur” — jurnal &amp; stok terpotong otomatis.</p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No. Faktur</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 text-right font-medium">Terbayar</th>
                <th className="px-4 py-3 text-right font-medium">Cetak</th>
              </tr></thead>
              <tbody>
                {items.map((v) => (
                  <tr key={v.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{v.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(v.date)}</td>
                    <td className={`px-4 py-3 capitalize ${STATUS[v.status] ?? "text-ink-muted"}`}>{v.status}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(v.total)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(v.paid_total)}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => cetak(v.id, "faktur")} disabled={printing === v.id + "faktur"}
                          title="Cetak faktur" className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-ink disabled:opacity-40">
                          <Printer size={15} />
                        </button>
                        <button onClick={() => cetak(v.id, "sj")} disabled={printing === v.id + "sj"}
                          title="Cetak surat jalan" className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-ink disabled:opacity-40">
                          <Truck size={15} />
                        </button>
                        {Number(v.paid_total) > 0 && v.status !== "void" && (
                          <button onClick={() => bukaPembayaran(v)} title="Kelola pembayaran"
                            className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-ink">
                            <Wallet size={15} />
                          </button>
                        )}
                        {v.status !== "void" && Number(v.paid_total) === 0 && (
                          <button onClick={() => batalkan(v)}
                            title="Batalkan (void) — hanya owner" className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
                            <Ban size={15} />
                          </button>
                        )}
                        <button onClick={() => hapusPermanen(v)}
                          title="Hapus permanen (data uji) — hanya owner" className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
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
        {hasMore && (
          <div className="mt-3 flex justify-center">
            <Button variant="secondary" onClick={muatLagi} disabled={loadingMore}>
              {loadingMore ? "Memuat…" : "Muat lebih banyak"}
            </Button>
          </div>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Buat Faktur Penjualan" width="max-w-3xl">
        <form onSubmit={simpan} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Pelanggan">
              <Select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
                <option value="">— pilih pelanggan —</option>
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
                  <th className="px-2 py-2 text-right font-medium">Harga</th>
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
                      <td className="px-2 py-1.5 w-28"><NumCell value={l.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value })} /></td>
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
            <Button type="submit" disabled={saving}>{saving ? "Memproses…" : "Terbitkan Faktur"}</Button>
          </div>
        </form>
      </Modal>
      {payFor && (
        <Modal open={!!payFor} onClose={() => setPayFor(null)} title={`Pembayaran — ${payFor.number}`}>
          <div className="space-y-3">
            {pays.length === 0 && <p className="text-sm text-ink-subtle">Belum ada pembayaran tercatat.</p>}
            {pays.map((p) => (
              <div key={p.id} className="flex items-center justify-between rounded-[var(--radius-input)] border border-line px-3 py-2 text-sm">
                <div>
                  <p className="text-ink">{p.number}</p>
                  <p className="text-caption text-ink-subtle">{tanggal(p.date)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="tabular-nums text-ink">{rupiah(p.amount)}</span>
                  <button onClick={() => voidPembayaran(p.id)} title="Batalkan pembayaran ini"
                    className="rounded p-1 text-ink-subtle hover:bg-surface-sunken hover:text-danger">
                    <Ban size={15} />
                  </button>
                </div>
              </div>
            ))}
            <p className="text-caption text-ink-subtle">Membatalkan pembayaran akan mengembalikan sisa tagihan. Setelah lunas dibatalkan, faktur bisa di-void.</p>
          </div>
        </Modal>
      )}
    </>
  );
}
