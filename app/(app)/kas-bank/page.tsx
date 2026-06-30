"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, Select } from "@/components/ui/form";

type Doc = {
  id: string; number: string; date: string;
  total: string; paid_total: string; status: string;
};
type Mode = "receive" | "pay";

const today = () => new Date().toISOString().slice(0, 10);
const sisa = (d: Doc) => Number(d.total) - Number(d.paid_total);

export default function KasBankPage() {
  const [mode, setMode] = useState<Mode>("receive");
  const [docs, setDocs] = useState<Doc[]>([]);
  const [docId, setDocId] = useState("");
  const [date, setDate] = useState(today());
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  function muat() {
    const path = mode === "receive" ? "/invoices" : "/bills";
    api<Doc[]>(path)
      .then((all) => setDocs(all.filter((d) => sisa(d) > 0 && d.status !== "void")))
      .catch(() => setDocs([]));
  }
  useEffect(() => {
    setDocId(""); setAmount(""); setMsg(null);
    muat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  function pilihDoc(id: string) {
    setDocId(id);
    const d = docs.find((x) => x.id === id);
    if (d) setAmount(String(sisa(d)));
  }

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (!docId) return setMsg({ ok: false, text: mode === "receive" ? "Pilih faktur dulu." : "Pilih tagihan dulu." });
    if (!(Number(amount) > 0)) return setMsg({ ok: false, text: "Jumlah harus lebih dari 0." });
    setSaving(true);
    try {
      const endpoint = mode === "receive" ? "/payments/receive" : "/payments/pay";
      const body = mode === "receive"
        ? { invoice_id: docId, date, amount }
        : { bill_id: docId, date, amount };
      const res = await api<{ number: string }>(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMsg({ ok: true, text: `Berhasil dicatat (No. ${res.number}). Jurnal kas otomatis dibuat.` });
      setDocId(""); setAmount("");
      muat();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Gagal menyimpan." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Topbar title="Kas & Bank" />
      <div className="p-6">
        <div className="mx-auto max-w-xl space-y-4">
          <div className="inline-flex rounded-[var(--radius-button)] border border-line bg-surface-sunken p-1 text-sm">
            <button
              onClick={() => setMode("receive")}
              className={`rounded-[var(--radius-button)] px-4 py-1.5 font-medium transition-colors ${mode === "receive" ? "bg-surface text-ink shadow-[var(--shadow-pop)]" : "text-ink-muted"}`}
            >
              Penerimaan (piutang)
            </button>
            <button
              onClick={() => setMode("pay")}
              className={`rounded-[var(--radius-button)] px-4 py-1.5 font-medium transition-colors ${mode === "pay" ? "bg-surface text-ink shadow-[var(--shadow-pop)]" : "text-ink-muted"}`}
            >
              Pembayaran (utang)
            </button>
          </div>

          <Card>
            <form onSubmit={simpan} className="space-y-4">
              <Field label={mode === "receive" ? "Faktur belum lunas" : "Tagihan belum lunas"}>
                <Select value={docId} onChange={(e) => pilihDoc(e.target.value)} required>
                  <option value="">
                    {docs.length === 0 ? "— tidak ada yang belum lunas —" : "— pilih —"}
                  </option>
                  {docs.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.number} · {tanggal(d.date)} · sisa {rupiah(sisa(d))}
                    </option>
                  ))}
                </Select>
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Tanggal">
                  <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required
                    className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" />
                </Field>
                <Field label="Jumlah (Rp)">
                  <Input type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} required placeholder="0" />
                </Field>
              </div>

              {msg && (
                <p className={`text-sm ${msg.ok ? "text-success" : "text-danger"}`}>{msg.text}</p>
              )}

              <div className="flex justify-end">
                <Button type="submit" disabled={saving}>
                  {saving ? "Memproses…" : mode === "receive" ? "Catat Penerimaan" : "Catat Pembayaran"}
                </Button>
              </div>
            </form>
          </Card>

          <p className="text-caption text-ink-subtle">
            Catatan: endpoint <code className="rounded bg-surface-sunken px-1">/payments</code> butuh peran <b>finance</b>.
            Setiap pelunasan otomatis memposting jurnal kas (debit=kredit).
          </p>
        </div>
      </div>
    </>
  );
}
