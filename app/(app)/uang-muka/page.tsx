"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/form";

type Advance = {
  id: string; number: string; date: string; contact_id: string;
  amount: string; allocated_total: string; status: string;
};
type Contact = { id: string; name: string; type: string };
type Invoice = { id: string; number: string; status: string; contact_id: string; total: string; paid_total: string };

const today = () => new Date().toISOString().slice(0, 10);
const KOSONG = { contact_id: "", amount: "", cash_account_code: "1-1000", note: "" };

export default function UangMukaPage() {
  const [items, setItems] = useState<Advance[] | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...KOSONG });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [alokasi, setAlokasi] = useState<Advance | null>(null);
  const [invId, setInvId] = useState("");
  const [nilai, setNilai] = useState("");
  const [alokError, setAlokError] = useState<string | null>(null);
  const [alokasiJalan, setAlokasiJalan] = useState(false);

  const nama = (id: string) => contacts.find((c) => c.id === id)?.name ?? "—";

  function muat() {
    api<Advance[]>("/receivables/advances").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(() => {
    muat();
    api<Contact[]>("/contacts").then((c) => setContacts(c.filter((x) => x.type === "customer"))).catch(() => {});
  }, []);

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!form.contact_id) return setFormError("Pilih customer dulu.");
    if (!(Number(form.amount) > 0)) return setFormError("Nominal harus lebih dari 0.");
    setSaving(true);
    try {
      await api("/receivables/advances", {
        method: "POST",
        body: JSON.stringify({
          contact_id: form.contact_id, date: today(), amount: form.amount,
          cash_account_code: form.cash_account_code, note: form.note || null,
        }),
      });
      setOpen(false); setForm({ ...KOSONG }); muat();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Gagal menyimpan.");
    } finally { setSaving(false); }
  }

  function bukaAlokasi(a: Advance) {
    setAlokError(null); setInvId(""); setNilai(""); setAlokasi(a);
    api<Invoice[]>("/invoices")
      .then((all) => setInvoices(all.filter(
        (i) => i.contact_id === a.contact_id && (i.status === "posted" || i.status === "overdue"))))
      .catch(() => {});
  }

  async function simpanAlokasi(e: FormEvent) {
    e.preventDefault();
    if (!alokasi) return;
    setAlokError(null);
    if (!invId) return setAlokError("Pilih faktur tujuan.");
    setAlokasiJalan(true);
    try {
      await api(`/receivables/advances/${alokasi.id}/allocate`, {
        method: "POST",
        body: JSON.stringify({ invoice_id: invId, date: today(), amount: nilai }),
      });
      setAlokasi(null); muat();
    } catch (err) {
      setAlokError(err instanceof Error ? err.message : "Gagal mengalokasikan.");
    } finally { setAlokasiJalan(false); }
  }

  const sisaTotal = (items ?? []).reduce(
    (s, a) => s + (Number(a.amount) - Number(a.allocated_total)), 0);
  const fakturTerpilih = invoices.find((i) => i.id === invId);
  const sisaFaktur = fakturTerpilih
    ? Number(fakturTerpilih.total) - Number(fakturTerpilih.paid_total) : 0;

  return (
    <>
      <Topbar title="Uang Muka Pelanggan" />
      <div className="p-6">
        <Card className="mb-4">
          <p className="text-sm text-ink">
            Uang yang diterima <b>sebelum barang keluar</b> dicatat sebagai kewajiban
            (akun 2-1500), bukan pendapatan.
          </p>
          <p className="mt-1 text-caption text-ink-subtle">
            Pendapatan tetap diakui sekali, saat faktur terbit. Setelah faktur ada,
            alokasikan uang mukanya untuk mengurangi piutang.
          </p>
        </Card>

        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-ink-muted">
            Belum terpakai: <b className="tabular-nums text-ink">{rupiah(sisaTotal)}</b>
          </p>
          <Button onClick={() => { setFormError(null); setOpen(true); }}>
            <Plus size={16} /> Terima Uang Muka
          </Button>
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada uang muka.</p>
            <p className="mt-1 text-sm text-ink-muted">
              Catat DP di sini supaya neraca tetap benar sebelum barang dikirim.
            </p>
          </Card>
        )}

        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 text-right font-medium">Diterima</th>
                <th className="px-4 py-3 text-right font-medium">Sisa</th>
                <th className="px-4 py-3" />
              </tr></thead>
              <tbody>
                {items.map((a) => {
                  const sisa = Number(a.amount) - Number(a.allocated_total);
                  return (
                    <tr key={a.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-3 text-ink">{a.number}</td>
                      <td className="px-4 py-3 text-ink-muted">{tanggal(a.date)}</td>
                      <td className="px-4 py-3 text-ink">{nama(a.contact_id)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(a.amount)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(sisa)}</td>
                      <td className="px-4 py-3 text-right">
                        {sisa > 0 && (
                          <Button variant="secondary" onClick={() => bukaAlokasi(a)}>
                            Pakai untuk Faktur
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Terima Uang Muka">
        <form onSubmit={simpan} className="space-y-4">
          <Field label="Customer">
            <Select value={form.contact_id} onChange={(e) => set("contact_id", e.target.value)} required>
              <option value="">— pilih customer —</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Nominal (Rp)">
              <Input type="number" min={0} value={form.amount}
                onChange={(e) => set("amount", e.target.value)} required />
            </Field>
            <Field label="Masuk ke">
              <Select value={form.cash_account_code} onChange={(e) => set("cash_account_code", e.target.value)}>
                <option value="1-1000">Kas</option>
                <option value="1-1100">Bank</option>
                <option value="1-1110">Bank BCA - Silo</option>
                <option value="1-1120">Bank OCBC - Silo</option>
              </Select>
            </Field>
          </div>
          <Field label="Catatan">
            <Textarea rows={2} value={form.note} onChange={(e) => set("note", e.target.value)}
              placeholder="opsional — untuk order apa" />
          </Field>
          <p className="text-caption text-ink-subtle">
            Jurnal: Debit kas/bank, Kredit <b>Uang Muka Pelanggan</b>. Tidak ada
            pendapatan dan tidak ada PPN yang diakui di sini.
          </p>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!alokasi} onClose={() => setAlokasi(null)} title="Pakai Uang Muka">
        <form onSubmit={simpanAlokasi} className="space-y-4">
          <p className="text-sm text-ink">
            {alokasi && nama(alokasi.contact_id)} · sisa{" "}
            <b className="tabular-nums">
              {rupiah(alokasi ? Number(alokasi.amount) - Number(alokasi.allocated_total) : 0)}
            </b>
          </p>
          <Field label="Faktur tujuan" hint="Hanya faktur customer ini yang sudah diposting">
            <Select value={invId} onChange={(e) => setInvId(e.target.value)} required>
              <option value="">— pilih faktur —</option>
              {invoices.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.number} · sisa {rupiah(Number(i.total) - Number(i.paid_total))}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Nominal dipakai (Rp)"
            hint={fakturTerpilih ? `Maksimal ${rupiah(sisaFaktur)} — sisa piutang faktur ini` : undefined}>
            <Input type="number" min={0} value={nilai}
              onChange={(e) => setNilai(e.target.value)} required />
          </Field>
          <p className="text-caption text-ink-subtle">
            Jurnal: Debit Uang Muka Pelanggan, Kredit Piutang Usaha. Tidak ada kas
            yang bergerak — uangnya sudah masuk waktu DP diterima.
          </p>
          {alokError && <p className="text-sm text-danger">{alokError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setAlokasi(null)}>Batal</Button>
            <Button type="submit" disabled={alokasiJalan}>
              {alokasiJalan ? "Memproses…" : "Alokasikan"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
