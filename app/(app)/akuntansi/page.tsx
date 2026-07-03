"use client";
import { useEffect, useState, useCallback } from "react";
import { Search, BookOpen } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/form";

type JournalRow = { id: string; number: string; date: string; memo: string | null; source_type: string; total: string };
type JournalDetail = {
  number: string; date: string; memo: string | null; source_type: string;
  entries: { account_code: string; account_name: string; debit: string; credit: string; description: string | null }[];
};
type Account = { id: string; code: string; name: string; type: string };
type Ledger = {
  account: { code: string; name: string; normal_balance: string };
  opening_balance: string;
  entries: { date: string; number: string; memo: string | null; debit: string; credit: string; balance: string }[];
  closing_balance: string;
};

const TABS = ["Jurnal", "Buku Besar", "Bagan Akun"] as const;
type Tab = (typeof TABS)[number];
const today = () => new Date().toISOString().slice(0, 10);
const yearStart = () => `${new Date().getFullYear()}-01-01`;
const PAGE = 50;
const SRC_LABEL: Record<string, string> = {
  invoice: "Faktur", bill: "Tagihan", payment: "Pembayaran", manual: "Manual",
  courier: "Ongkir", expense: "Beban", loan: "Kasbon", loan_payment: "Cicilan",
  investor: "Investor", investor_payout: "Payout", historical: "Histori",
  void_invoice: "Batal Faktur", void_bill: "Batal Tagihan", void_expense: "Batal Beban",
};

export default function AkuntansiPage() {
  const [tab, setTab] = useState<Tab>("Jurnal");

  // ---- Jurnal ----
  const [journals, setJournals] = useState<JournalRow[] | null>(null);
  const [q, setQ] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [detail, setDetail] = useState<JournalDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const muatJurnal = useCallback(async (reset = true, query = q) => {
    try {
      const offset = reset ? 0 : (journals?.length ?? 0);
      const res = await api<JournalRow[]>(
        `/journals?limit=${PAGE}&offset=${offset}${query ? `&q=${encodeURIComponent(query)}` : ""}`);
      setJournals((prev) => (reset || !prev ? res : [...prev, ...res]));
      setHasMore(res.length === PAGE);
    } catch (e) { setErr(e instanceof Error ? e.message : "Gagal memuat jurnal."); }
  }, [q, journals]);

  useEffect(() => { if (tab === "Jurnal" && journals === null) muatJurnal(true, ""); }, [tab, journals, muatJurnal]);

  async function bukaDetail(id: string) {
    try { setDetail(await api<JournalDetail>(`/journals/${id}`)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Gagal memuat detail."); }
  }

  // ---- Buku Besar ----
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accId, setAccId] = useState("");
  const [start, setStart] = useState(yearStart());
  const [end, setEnd] = useState(today());
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [loadingLedger, setLoadingLedger] = useState(false);

  useEffect(() => {
    if ((tab === "Buku Besar" || tab === "Bagan Akun") && accounts.length === 0) {
      api<Account[]>("/accounts").then(setAccounts).catch(() => {});
    }
  }, [tab, accounts.length]);

  useEffect(() => {
    if (tab !== "Buku Besar" || !accId) { setLedger(null); return; }
    setLoadingLedger(true);
    api<Ledger>(`/journals/ledger?account_id=${accId}&start=${start}&end=${end}`)
      .then(setLedger)
      .catch((e) => setErr(e instanceof Error ? e.message : "Gagal memuat buku besar."))
      .finally(() => setLoadingLedger(false));
  }, [tab, accId, start, end]);

  return (
    <>
      <Topbar title="Akuntansi" />
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-[var(--radius-input)] px-3 py-1.5 text-sm transition-colors ${tab === t ? "bg-primary text-white" : "bg-surface-sunken text-ink-muted hover:text-ink"}`}>
              {t}
            </button>
          ))}
        </div>

        {err && <Card className="text-sm text-danger">{err}</Card>}

        {/* ================= JURNAL ================= */}
        {tab === "Jurnal" && (
          <>
            <div className="flex items-center gap-2 rounded-[var(--radius-input)] border border-line bg-surface px-3 py-1.5 w-fit">
              <Search size={15} className="text-ink-subtle" />
              <input value={q} onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") muatJurnal(true); }}
                placeholder="Cari nomor / memo… (Enter)"
                className="w-56 bg-transparent text-sm text-ink outline-none placeholder:text-ink-subtle" />
            </div>
            <Card className="overflow-hidden p-0">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                  <th className="px-4 py-3 font-medium">No. Jurnal</th>
                  <th className="px-4 py-3 font-medium">Tanggal</th>
                  <th className="px-4 py-3 font-medium">Sumber</th>
                  <th className="px-4 py-3 font-medium">Memo</th>
                  <th className="px-4 py-3 text-right font-medium">Nilai</th>
                </tr></thead>
                <tbody>
                  {(journals ?? []).map((j) => (
                    <tr key={j.id} onClick={() => bukaDetail(j.id)}
                      className="cursor-pointer border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-3 text-ink">{j.number}</td>
                      <td className="px-4 py-3 text-ink-muted">{tanggal(j.date)}</td>
                      <td className="px-4 py-3 text-ink-muted">{SRC_LABEL[j.source_type] ?? j.source_type}</td>
                      <td className="max-w-72 truncate px-4 py-3 text-ink-muted">{j.memo ?? "—"}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(j.total)}</td>
                    </tr>
                  ))}
                  {journals?.length === 0 && (
                    <tr><td colSpan={5} className="px-4 py-6 text-center text-ink-subtle">Belum ada jurnal.</td></tr>
                  )}
                </tbody>
              </table>
            </Card>
            {hasMore && (
              <div className="flex justify-center">
                <Button variant="secondary" disabled={loadingMore}
                  onClick={async () => { setLoadingMore(true); await muatJurnal(false); setLoadingMore(false); }}>
                  {loadingMore ? "Memuat…" : "Muat lebih banyak"}
                </Button>
              </div>
            )}
            <p className="text-caption text-ink-subtle">Klik baris untuk melihat entri debit/kredit. Setiap jurnal dijamin balance oleh sistem.</p>
          </>
        )}

        {/* ================= BUKU BESAR ================= */}
        {tab === "Buku Besar" && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Select value={accId} onChange={(e) => setAccId(e.target.value)} className="w-72">
                <option value="">— pilih akun —</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}
              </Select>
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1.5 text-ink" />
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1.5 text-ink" />
            </div>

            {!accId && <Card className="text-sm text-ink-muted">Pilih akun untuk melihat buku besarnya.</Card>}
            {loadingLedger && <Card className="text-sm text-ink-muted">Memuat…</Card>}
            {ledger && !loadingLedger && (
              <Card className="overflow-hidden p-0">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 text-sm">
                  <span className="font-medium text-ink"><BookOpen size={15} className="mr-1 inline text-primary" />
                    {ledger.account.code} · {ledger.account.name}</span>
                  <span className="text-ink-muted">Saldo awal: <b className="tabular-nums text-ink">{rupiah(ledger.opening_balance)}</b>
                    <span className="mx-2">·</span>
                    Saldo akhir: <b className="tabular-nums text-ink">{rupiah(ledger.closing_balance)}</b></span>
                </div>
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                    <th className="px-4 py-2 font-medium">Tanggal</th>
                    <th className="px-4 py-2 font-medium">No. Jurnal</th>
                    <th className="px-4 py-2 font-medium">Keterangan</th>
                    <th className="px-4 py-2 text-right font-medium">Debit</th>
                    <th className="px-4 py-2 text-right font-medium">Kredit</th>
                    <th className="px-4 py-2 text-right font-medium">Saldo</th>
                  </tr></thead>
                  <tbody>
                    {ledger.entries.map((e, i) => (
                      <tr key={i} className="border-b border-line last:border-0">
                        <td className="px-4 py-2 text-ink-muted">{tanggal(e.date)}</td>
                        <td className="px-4 py-2 text-ink">{e.number}</td>
                        <td className="max-w-72 truncate px-4 py-2 text-ink-muted">{e.memo ?? "—"}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-ink">{Number(e.debit) > 0 ? rupiah(e.debit) : "—"}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-ink">{Number(e.credit) > 0 ? rupiah(e.credit) : "—"}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-ink">{rupiah(e.balance)}</td>
                      </tr>
                    ))}
                    {ledger.entries.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-5 text-center text-ink-subtle">Tidak ada mutasi pada periode ini.</td></tr>
                    )}
                  </tbody>
                </table>
              </Card>
            )}
          </>
        )}

        {/* ================= BAGAN AKUN ================= */}
        {tab === "Bagan Akun" && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">Kode</th>
                <th className="px-4 py-3 font-medium">Nama Akun</th>
                <th className="px-4 py-3 font-medium">Tipe</th>
              </tr></thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-2.5 text-ink-muted">{a.code}</td>
                    <td className="px-4 py-2.5 text-ink">{a.name}</td>
                    <td className="px-4 py-2.5 capitalize text-ink-muted">{a.type}</td>
                  </tr>
                ))}
                {accounts.length === 0 && (
                  <tr><td colSpan={3} className="px-4 py-5 text-center text-ink-subtle">Memuat…</td></tr>
                )}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      {/* Modal detail jurnal */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail ? `Jurnal ${detail.number}` : ""} width="max-w-2xl">
        {detail && (
          <div className="space-y-3">
            <p className="text-sm text-ink-muted">
              {tanggal(detail.date)} · {SRC_LABEL[detail.source_type] ?? detail.source_type}
              {detail.memo ? ` · ${detail.memo}` : ""}
            </p>
            <div className="overflow-hidden rounded-[var(--radius-input)] border border-line">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line bg-surface-sunken text-left text-caption text-ink-muted">
                  <th className="px-3 py-2 font-medium">Akun</th>
                  <th className="px-3 py-2 text-right font-medium">Debit</th>
                  <th className="px-3 py-2 text-right font-medium">Kredit</th>
                </tr></thead>
                <tbody>
                  {detail.entries.map((e, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-3 py-2">
                        <span className="text-ink">{e.account_code} · {e.account_name}</span>
                        {e.description && <span className="block text-caption text-ink-subtle">{e.description}</span>}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink">{Number(e.debit) > 0 ? rupiah(e.debit) : "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink">{Number(e.credit) > 0 ? rupiah(e.credit) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => setDetail(null)}>Tutup</Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
