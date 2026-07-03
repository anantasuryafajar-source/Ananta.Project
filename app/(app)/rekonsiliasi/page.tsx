"use client";
import { useEffect, useState, useCallback } from "react";
import { Landmark, Check } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/form";

type Acc = { id: string; code: string; name: string };
type Entry = { entry_id: string; date: string; number: string; memo: string | null; debit: string; credit: string; reconciled: boolean };
type Data = {
  account: { code: string; name: string };
  book_balance: string; reconciled_balance: string; unreconciled: string;
  entries: Entry[];
};

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`; };

export default function RekonsiliasiPage() {
  const [accs, setAccs] = useState<Acc[]>([]);
  const [accId, setAccId] = useState("");
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(today());
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Acc[]>("/reconcile/accounts").then((a) => {
      setAccs(a);
      if (a.length && !accId) setAccId(a[0].id);
    }).catch((e) => setError(e.message));
  }, []);

  const muat = useCallback(async () => {
    if (!accId) return;
    setLoading(true); setError(null);
    try {
      setData(await api<Data>(`/reconcile/entries?account_id=${accId}&start=${start}&end=${end}`));
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal memuat."); }
    finally { setLoading(false); }
  }, [accId, start, end]);

  useEffect(() => { muat(); }, [muat]);

  async function toggle(en: Entry) {
    try {
      await api("/reconcile/toggle", {
        method: "POST",
        body: JSON.stringify({ entry_id: en.entry_id, account_id: accId, reconciled: !en.reconciled }),
      });
      // update lokal cepat
      setData((d) => d ? { ...d, entries: d.entries.map((x) => x.entry_id === en.entry_id ? { ...x, reconciled: !x.reconciled } : x) } : d);
      muat();
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal menandai."); }
  }

  return (
    <>
      <Topbar title="Rekonsiliasi Bank" />
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Select value={accId} onChange={(e) => setAccId(e.target.value)} className="w-64">
            {accs.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}
          </Select>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
            className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1.5 text-ink" />
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
            className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1.5 text-ink" />
        </div>

        {error && <Card className="text-sm text-danger">{error}</Card>}
        {loading && <Card className="text-sm text-ink-muted">Memuat…</Card>}

        {data && !loading && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <Card>
                <p className="text-caption text-ink-subtle">Saldo buku</p>
                <p className="mt-1 text-base font-semibold tabular-nums text-ink">{rupiah(data.book_balance)}</p>
              </Card>
              <Card>
                <p className="text-caption text-ink-subtle">Sudah dicocokkan</p>
                <p className="mt-1 text-base font-semibold tabular-nums text-success">{rupiah(data.reconciled_balance)}</p>
              </Card>
              <Card>
                <p className="text-caption text-ink-subtle">Belum dicocokkan</p>
                <p className={`mt-1 text-base font-semibold tabular-nums ${Number(data.unreconciled) === 0 ? "text-success" : "text-warning"}`}>{rupiah(data.unreconciled)}</p>
              </Card>
            </div>

            <Card className="overflow-hidden p-0">
              <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm">
                <Landmark size={16} className="text-primary" />
                <span className="font-medium text-ink">{data.account.code} · {data.account.name}</span>
                <span className="ml-auto text-caption text-ink-subtle">Centang baris yang cocok dengan rekening koran</span>
              </div>
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                  <th className="w-14 px-4 py-2 font-medium">Cocok</th>
                  <th className="px-4 py-2 font-medium">Tanggal</th>
                  <th className="px-4 py-2 font-medium">No. Jurnal</th>
                  <th className="px-4 py-2 font-medium">Keterangan</th>
                  <th className="px-4 py-2 text-right font-medium">Masuk</th>
                  <th className="px-4 py-2 text-right font-medium">Keluar</th>
                </tr></thead>
                <tbody>
                  {data.entries.map((en) => (
                    <tr key={en.entry_id} className={`border-b border-line last:border-0 ${en.reconciled ? "bg-success/5" : ""}`}>
                      <td className="px-4 py-2">
                        <button onClick={() => toggle(en)}
                          className={`grid h-5 w-5 place-items-center rounded border ${en.reconciled ? "border-success bg-success text-white" : "border-line bg-surface text-transparent hover:border-primary"}`}
                          title={en.reconciled ? "Lepas tanda" : "Tandai cocok"}>
                          <Check size={13} />
                        </button>
                      </td>
                      <td className="px-4 py-2 text-ink-muted">{tanggal(en.date)}</td>
                      <td className="px-4 py-2 text-ink">{en.number}</td>
                      <td className="max-w-72 truncate px-4 py-2 text-ink-muted">{en.memo ?? "—"}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-success">{Number(en.debit) > 0 ? rupiah(en.debit) : "—"}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-danger">{Number(en.credit) > 0 ? rupiah(en.credit) : "—"}</td>
                    </tr>
                  ))}
                  {data.entries.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-6 text-center text-ink-subtle">Tidak ada mutasi pada periode ini.</td></tr>
                  )}
                </tbody>
              </table>
            </Card>
            <p className="text-caption text-ink-subtle">
              Saat "Belum dicocokkan" = Rp 0, seluruh mutasi buku sudah cocok dengan rekening koran untuk periode ini.
              Tanda rekonsiliasi tersimpan permanen dan tidak memengaruhi jurnal.
            </p>
          </>
        )}
      </div>
    </>
  );
}
