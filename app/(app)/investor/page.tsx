"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Banknote, HandCoins } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/form";

type Investor = {
  id: string; name: string; scheme: string | null; principal: string;
  received_total: string; roi_rate: string; start_date: string | null;
  due_date: string | null; status: string;
};
type Payout = { id: string; investor_id: string; number: string; date: string; type: string; amount: string };

const today = () => new Date().toISOString().slice(0, 10);
const CASH_OPTS = [
  { code: "1-1000", label: "Kas" },
  { code: "1-1100", label: "Bank" },
  { code: "1-1110", label: "Bank BCA - Silo" },
  { code: "1-1120", label: "Bank OCBC - Silo" },
];

export default function InvestorPage() {
  const [items, setItems] = useState<Investor[] | null>(null);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [error, setError] = useState<string | null>(null);

  // form investor baru
  const [openNew, setOpenNew] = useState(false);
  const [nf, setNf] = useState({ name: "", scheme: "", principal: "", roi_rate: "", start_date: "", due_date: "", notes: "" });

  // form aksi (terima dana / payout)
  const [action, setAction] = useState<{ mode: "receive" | "payout"; inv: Investor } | null>(null);
  const [af, setAf] = useState({ date: today(), amount: "", type: "dividend", cash: "1-1100", note: "" });

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function muat() {
    api<Investor[]>("/investors").then(setItems).catch((e) => setError(e.message));
    api<Payout[]>("/investors/payouts").then(setPayouts).catch(() => {});
  }
  useEffect(muat, []);

  async function simpanBaru(e: FormEvent) {
    e.preventDefault(); setFormError(null); setSaving(true);
    try {
      await api("/investors", {
        method: "POST",
        body: JSON.stringify({
          name: nf.name.trim(), scheme: nf.scheme || null,
          principal: nf.principal || "0", roi_rate: nf.roi_rate || "0",
          start_date: nf.start_date || null, due_date: nf.due_date || null,
          notes: nf.notes || null,
        }),
      });
      setOpenNew(false);
      setNf({ name: "", scheme: "", principal: "", roi_rate: "", start_date: "", due_date: "", notes: "" });
      muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal menyimpan."); }
    finally { setSaving(false); }
  }

  function bukaAksi(mode: "receive" | "payout", inv: Investor) {
    setFormError(null);
    setAf({ date: today(), amount: "", type: "dividend", cash: "1-1100", note: "" });
    setAction({ mode, inv });
  }

  async function simpanAksi(e: FormEvent) {
    e.preventDefault();
    if (!action) return;
    setFormError(null);
    if (!(Number(af.amount) > 0)) return setFormError("Nominal harus lebih dari 0.");
    setSaving(true);
    try {
      if (action.mode === "receive") {
        await api(`/investors/${action.inv.id}/receive`, {
          method: "POST",
          body: JSON.stringify({ date: af.date, amount: af.amount, cash_account_code: af.cash }),
        });
      } else {
        await api(`/investors/${action.inv.id}/payout`, {
          method: "POST",
          body: JSON.stringify({ date: af.date, type: af.type, amount: af.amount, cash_account_code: af.cash, note: af.note || null }),
        });
      }
      setAction(null);
      muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal memproses."); }
    finally { setSaving(false); }
  }

  return (
    <>
      <Topbar title="Investor & Bagi Hasil" />
      <div className="space-y-4 p-6">
        <div className="flex justify-end">
          <Button onClick={() => setOpenNew(true)}><Plus size={16} /> Tambah Investor</Button>
        </div>
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}

        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada investor.</p>
            <p className="mt-1 text-sm text-ink-muted">Tambah investor, catat dana masuk, lalu bayar dividen/pokok — jurnal otomatis.</p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">Investor</th>
                <th className="px-4 py-3 font-medium">Skema</th>
                <th className="px-4 py-3 text-right font-medium">Pokok</th>
                <th className="px-4 py-3 text-right font-medium">Diterima</th>
                <th className="px-4 py-3 font-medium">Jatuh Tempo</th>
                <th className="px-4 py-3 text-right font-medium">Aksi</th>
              </tr></thead>
              <tbody>
                {items.map((v) => (
                  <tr key={v.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{v.name}</td>
                    <td className="px-4 py-3 text-ink-muted">{v.scheme ?? "—"}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(v.principal)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(v.received_total)}</td>
                    <td className="px-4 py-3 text-ink-muted">{v.due_date ? tanggal(v.due_date) : "—"}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Button variant="secondary" onClick={() => bukaAksi("receive", v)}>
                          <Banknote size={15} /> Terima Dana
                        </Button>
                        <Button variant="secondary" onClick={() => bukaAksi("payout", v)}>
                          <HandCoins size={15} /> Bayar
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        <Card className="overflow-hidden p-0">
          <div className="border-b border-line px-4 py-3 text-sm font-medium text-ink">Riwayat Pembayaran</div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
              <th className="px-4 py-3 font-medium">No.</th>
              <th className="px-4 py-3 font-medium">Tanggal</th>
              <th className="px-4 py-3 font-medium">Investor</th>
              <th className="px-4 py-3 font-medium">Jenis</th>
              <th className="px-4 py-3 text-right font-medium">Nominal</th>
            </tr></thead>
            <tbody>
              {payouts.map((pp) => (
                <tr key={pp.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 text-ink">{pp.number}</td>
                  <td className="px-4 py-3 text-ink-muted">{tanggal(pp.date)}</td>
                  <td className="px-4 py-3 text-ink-muted">{items?.find((i) => i.id === pp.investor_id)?.name ?? "—"}</td>
                  <td className="px-4 py-3 text-ink-muted">{pp.type === "dividend" ? "Dividen" : "Pokok"}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(pp.amount)}</td>
                </tr>
              ))}
              {payouts.length === 0 && <tr><td colSpan={5} className="px-4 py-4 text-center text-ink-subtle">Belum ada pembayaran.</td></tr>}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Modal investor baru */}
      <Modal open={openNew} onClose={() => setOpenNew(false)} title="Tambah Investor">
        <form onSubmit={simpanBaru} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Nama"><Input value={nf.name} onChange={(e) => setNf((f) => ({ ...f, name: e.target.value }))} required placeholder="Silo" /></Field>
            <Field label="Skema"><Input value={nf.scheme} onChange={(e) => setNf((f) => ({ ...f, scheme: e.target.value }))} placeholder="Opsi III (opsional)" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Dana pokok (Rp)"><Input type="number" min={0} value={nf.principal} onChange={(e) => setNf((f) => ({ ...f, principal: e.target.value }))} /></Field>
            <Field label="ROI % / periode"><Input type="number" min={0} step="0.01" value={nf.roi_rate} onChange={(e) => setNf((f) => ({ ...f, roi_rate: e.target.value }))} /></Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Mulai"><input type="date" value={nf.start_date} onChange={(e) => setNf((f) => ({ ...f, start_date: e.target.value }))} className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" /></Field>
            <Field label="Jatuh tempo"><input type="date" value={nf.due_date} onChange={(e) => setNf((f) => ({ ...f, due_date: e.target.value }))} className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" /></Field>
          </div>
          <Field label="Catatan"><Textarea rows={2} value={nf.notes} onChange={(e) => setNf((f) => ({ ...f, notes: e.target.value }))} placeholder="opsional" /></Field>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenNew(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      {/* Modal aksi */}
      <Modal open={!!action} onClose={() => setAction(null)}
        title={action?.mode === "receive" ? `Terima Dana — ${action?.inv.name}` : `Bayar Investor — ${action?.inv.name}`}>
        <form onSubmit={simpanAksi} className="space-y-4">
          {action?.mode === "payout" && (
            <Field label="Jenis pembayaran">
              <Select value={af.type} onChange={(e) => setAf((f) => ({ ...f, type: e.target.value }))}>
                <option value="dividend">Dividen / bagi hasil (beban)</option>
                <option value="principal">Pengembalian pokok (kurangi utang investor)</option>
              </Select>
            </Field>
          )}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Tanggal"><input type="date" value={af.date} onChange={(e) => setAf((f) => ({ ...f, date: e.target.value }))} required className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" /></Field>
            <Field label="Nominal (Rp)"><Input type="number" min={0} value={af.amount} onChange={(e) => setAf((f) => ({ ...f, amount: e.target.value }))} required /></Field>
          </div>
          <Field label={action?.mode === "receive" ? "Masuk ke" : "Dibayar dari"}>
            <Select value={af.cash} onChange={(e) => setAf((f) => ({ ...f, cash: e.target.value }))}>
              {CASH_OPTS.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
            </Select>
          </Field>
          {action?.mode === "payout" && (
            <Field label="Catatan"><Input value={af.note} onChange={(e) => setAf((f) => ({ ...f, note: e.target.value }))} placeholder="opsional" /></Field>
          )}
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setAction(null)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Memproses…" : action?.mode === "receive" ? "Catat Dana Masuk" : "Bayar"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
