"use client";
import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { rupiah } from "@/lib/format";

type Row = { code?: string; name: string; amount: string };
type PL = { income: Row[]; expense: Row[]; total_income: string; total_expense: string; net_profit: string };
type Aging = { buckets: Record<string, string>; total: string; items: { number: string; contact: string; age_days: number; outstanding: string }[] };
type Stock = { items: { sku: string; name: string; quantity: string; avg_cost: string; value: string }[]; total_value: string };
type Cashflow = { months: { month: string; in: string; out: string; net: string }[]; total_in: string; total_out: string; net: string };
type Quarterly = { items: { quarter: string; omzet: string; hpp: string; gross_profit: string }[] };
type ArLimit = { items: { customer: string; outstanding: string; credit_limit: string; ratio: number | null; status: string }[]; total_outstanding: string };
type Commission = { rate: number; items: { sku: string; name: string; qty: string; revenue: string; margin: string; commission: string }[]; total_commission: string };

const TABS = ["Laba Rugi", "Arus Kas", "Rekap Kuartal", "AR Aging", "AR Limit", "Komisi", "GPM", "Valuasi Stok"] as const;
type Tab = (typeof TABS)[number];
const withDate = new Set<Tab>(["Laba Rugi", "Arus Kas", "Komisi", "GPM"]);
type Gpm = { by_sku: { sku: string; name: string; revenue: string; margin: string; gpm: number | null }[]; by_customer: { customer: string; revenue: string; margin: string; gpm: number | null }[] };

const today = () => new Date().toISOString().slice(0, 10);
const yearStart = () => `${new Date().getFullYear()}-01-01`;

export default function LaporanPage() {
  const [tab, setTab] = useState<Tab>("Laba Rugi");
  const [start, setStart] = useState(yearStart());
  const [end, setEnd] = useState(today());
  const [data, setData] = useState<any>(null);
  const [dataTab, setDataTab] = useState<Tab | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setErr(null); setLoading(true); setData(null); setDataTab(null);
    try {
      const url: Record<Tab, string> = {
        "Laba Rugi": `/reports/profit-loss?start=${start}&end=${end}`,
        "Arus Kas": `/reports/cashflow?start=${start}&end=${end}`,
        "Rekap Kuartal": `/reports/quarterly-recap`,
        "AR Aging": `/reports/ar-aging?as_of=${end}`,
        "AR Limit": `/reports/ar-limit`,
        "Komisi": `/reports/commission?start=${start}&end=${end}`,
        "GPM": `/reports/gpm?start=${start}&end=${end}`,
        "Valuasi Stok": `/reports/stock-valuation`,
      };
      setData(await api<any>(url[tab]));
      setDataTab(tab);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal memuat laporan.");
    } finally { setLoading(false); }
  }, [tab, start, end]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Topbar title="Laporan" />
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-[var(--radius-input)] px-3 py-1.5 text-sm transition-colors ${tab === t ? "bg-primary text-white" : "bg-surface-sunken text-ink-muted hover:text-ink"}`}>
              {t}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2 text-sm text-ink-muted">
            {withDate.has(tab) && (
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1" />
            )}
            {(withDate.has(tab) || tab === "AR Aging") && (
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1" />
            )}
            <button onClick={() => exportCSV(tab, data)} disabled={!data || dataTab !== tab}
              className="rounded-[var(--radius-input)] border border-line bg-surface px-3 py-1 text-ink-muted transition-colors hover:text-ink disabled:opacity-40">
              Ekspor CSV
            </button>
            <button onClick={() => printReport(tab, data)} disabled={!data || dataTab !== tab}
              className="rounded-[var(--radius-input)] border border-line bg-surface px-3 py-1 text-ink-muted transition-colors hover:text-ink disabled:opacity-40">
              Cetak / PDF
            </button>
          </div>
        </div>

        {err && <Card className="text-sm text-danger">{err}</Card>}
        {loading && <Card className="text-sm text-ink-muted">Memuat…</Card>}

        {!loading && data && dataTab === tab && tab === "Laba Rugi" && <ProfitLoss pl={data as PL} />}
        {!loading && data && dataTab === tab && tab === "Arus Kas" && <CashflowView cf={data as Cashflow} />}
        {!loading && data && dataTab === tab && tab === "Rekap Kuartal" && <QuarterlyView q={data as Quarterly} />}
        {!loading && data && dataTab === tab && tab === "AR Aging" && <ArAging aging={data as Aging} />}
        {!loading && data && dataTab === tab && tab === "AR Limit" && <ArLimitView a={data as ArLimit} />}
        {!loading && data && dataTab === tab && tab === "Komisi" && <CommissionView c={data as Commission} />}
        {!loading && data && dataTab === tab && tab === "GPM" && <GpmView g={data as Gpm} />}
        {!loading && data && dataTab === tab && tab === "Valuasi Stok" && <StockVal stock={data as Stock} />}
      </div>
    </>
  );
}

/* ---------- Arus Kas ---------- */
function CashflowView({ cf }: { cf: Cashflow }) {
  const chart = cf.months.map((m) => ({ label: m.month.slice(2), value: Number(m.net) }));
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Kas Masuk" value={cf.total_in} tone="text-success" />
        <Stat label="Kas Keluar" value={cf.total_out} tone="text-danger" />
        <Stat label="Arus Kas Bersih" value={cf.net} tone={Number(cf.net) >= 0 ? "text-ink" : "text-danger"} />
      </div>
      <Card>
        <p className="mb-3 text-sm font-medium text-ink">Arus kas bersih per bulan</p>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart}>
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${(v / 1e6).toFixed(0)}jt`} tick={{ fontSize: 11 }} width={42} />
              <Tooltip formatter={(v: number) => rupiah(v)} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chart.map((c, i) => <Cell key={i} fill={c.value >= 0 ? "#2f7d6b" : "#c0392b"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <SimpleTable head={["Bulan", "Masuk", "Keluar", "Bersih"]}
          rows={cf.months.map((m) => [m.month, rupiah(m.in), rupiah(m.out), rupiah(m.net)])}
          empty="Belum ada mutasi kas." />
      </Card>
    </div>
  );
}

/* ---------- Rekap Kuartal ---------- */
function QuarterlyView({ q }: { q: Quarterly }) {
  const chart = q.items.map((i) => ({ label: i.quarter, value: Number(i.gross_profit) }));
  return (
    <Card>
      <p className="mb-3 text-sm font-medium text-ink">Laba kotor per kuartal</p>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chart}>
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => `${(v / 1e6).toFixed(0)}jt`} tick={{ fontSize: 11 }} width={42} />
            <Tooltip formatter={(v: number) => rupiah(v)} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} fill="#2f7d6b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SimpleTable head={["Kuartal", "Omzet", "HPP", "Laba Kotor"]}
        rows={q.items.map((i) => [i.quarter, rupiah(i.omzet), rupiah(i.hpp), rupiah(i.gross_profit)])}
        empty="Belum ada data penjualan." />
    </Card>
  );
}

/* ---------- AR Limit ---------- */
function ArLimitView({ a }: { a: ArLimit }) {
  return (
    <Card>
      <div className="mb-2 flex justify-between text-sm">
        <span className="font-medium text-ink">Piutang vs Limit Kredit</span>
        <span className="tabular-nums text-ink">Total: {rupiah(a.total_outstanding)}</span>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-caption uppercase text-ink-subtle">
          <th className="py-1">Customer</th><th className="text-right">Outstanding</th><th className="text-right">Limit</th><th className="text-right">Rasio</th><th className="text-right">Status</th>
        </tr></thead>
        <tbody>
          {a.items.map((it) => (
            <tr key={it.customer} className="border-t border-line">
              <td className="py-1 text-ink">{it.customer}</td>
              <td className="text-right tabular-nums text-ink">{rupiah(it.outstanding)}</td>
              <td className="text-right tabular-nums text-ink-muted">{rupiah(it.credit_limit)}</td>
              <td className="text-right tabular-nums text-ink-muted">{it.ratio != null ? `${(it.ratio * 100).toFixed(0)}%` : "—"}</td>
              <td className={`text-right font-medium ${it.status === "LEBIH LIMIT" ? "text-danger" : it.status === "AMAN" ? "text-success" : "text-ink-subtle"}`}>{it.status}</td>
            </tr>
          ))}
          {a.items.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-ink-subtle">Tidak ada piutang berjalan.</td></tr>}
        </tbody>
      </table>
    </Card>
  );
}

/* ---------- Komisi ---------- */
function CommissionView({ c }: { c: Commission }) {
  return (
    <Card>
      <div className="mb-2 flex justify-between text-sm">
        <span className="font-medium text-ink">Komisi per SKU (rate {(c.rate * 100).toFixed(0)}% dari margin)</span>
        <span className="tabular-nums text-ink">Total komisi: {rupiah(c.total_commission)}</span>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-caption uppercase text-ink-subtle">
          <th className="py-1">SKU</th><th>Produk</th><th className="text-right">Qty</th><th className="text-right">Omzet</th><th className="text-right">Margin</th><th className="text-right">Komisi</th>
        </tr></thead>
        <tbody>
          {c.items.map((it) => (
            <tr key={it.sku} className="border-t border-line">
              <td className="py-1 text-ink-muted">{it.sku}</td>
              <td className="text-ink">{it.name}</td>
              <td className="text-right tabular-nums text-ink-muted">{Number(it.qty)}</td>
              <td className="text-right tabular-nums text-ink-muted">{rupiah(it.revenue)}</td>
              <td className="text-right tabular-nums text-ink">{rupiah(it.margin)}</td>
              <td className="text-right tabular-nums text-primary">{rupiah(it.commission)}</td>
            </tr>
          ))}
          {c.items.length === 0 && <tr><td colSpan={6} className="py-3 text-center text-ink-subtle">Belum ada penjualan pada periode ini.</td></tr>}
        </tbody>
      </table>
    </Card>
  );
}

/* ---------- helper ---------- */
function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <Card>
      <p className="text-caption text-ink-subtle">{label}</p>
      <p className={`mt-1 text-base font-semibold tabular-nums ${tone}`}>{rupiah(value)}</p>
    </Card>
  );
}
function SimpleTable({ head, rows, empty }: { head: string[]; rows: string[][]; empty: string }) {
  return (
    <table className="mt-3 w-full text-sm">
      <thead><tr className="text-left text-caption uppercase text-ink-subtle">
        {head.map((h, i) => <th key={h} className={i === 0 ? "py-1" : "text-right"}>{h}</th>)}
      </tr></thead>
      <tbody>
        {rows.map((r, ri) => (
          <tr key={ri} className="border-t border-line">
            {r.map((c, ci) => <td key={ci} className={ci === 0 ? "py-1 text-ink-muted" : "text-right tabular-nums text-ink"}>{c}</td>)}
          </tr>
        ))}
        {rows.length === 0 && <tr><td colSpan={head.length} className="py-3 text-center text-ink-subtle">{empty}</td></tr>}
      </tbody>
    </table>
  );
}

/* ---------- laporan lama (dipertahankan) ---------- */
function ProfitLoss({ pl }: { pl: PL }) {
  const net = Number(pl.net_profit);
  const chart = [
    { label: "Pendapatan", value: Number(pl.total_income), fill: "#2f7d6b" },
    { label: "Beban", value: Number(pl.total_expense), fill: "#b4654a" },
    { label: "Laba Bersih", value: net, fill: net >= 0 ? "#2f7d6b" : "#c0392b" },
  ];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <p className="mb-3 text-sm font-medium text-ink">Ringkasan</p>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart}>
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => `${(v / 1e6).toFixed(0)}jt`} tick={{ fontSize: 11 }} width={42} />
              <Tooltip formatter={(v: number) => rupiah(v)} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>{chart.map((c, i) => <Cell key={i} fill={c.fill} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <dl className="mt-2 space-y-1 text-sm">
          <Line k="Total Pendapatan" v={pl.total_income} />
          <Line k="Total Beban" v={pl.total_expense} />
          <div className="border-t border-line pt-1"><Line k="Laba Bersih" v={pl.net_profit} bold /></div>
        </dl>
      </Card>
      <Card>
        <p className="mb-2 text-sm font-medium text-ink">Rincian</p>
        <Section title="Pendapatan" rows={pl.income} />
        <Section title="Beban" rows={pl.expense} />
      </Card>
    </div>
  );
}
function Section({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="mb-3">
      <p className="text-caption uppercase tracking-wide text-ink-subtle">{title}</p>
      {rows.length === 0 && <p className="text-sm text-ink-subtle">—</p>}
      {rows.map((r) => (
        <div key={r.code ?? r.name} className="flex justify-between py-0.5 text-sm">
          <span className="text-ink-muted">{r.name}</span>
          <span className="tabular-nums text-ink">{rupiah(r.amount)}</span>
        </div>
      ))}
    </div>
  );
}
function ArAging({ aging }: { aging: Aging }) {
  const labels: Record<string, string> = { current: "Belum jatuh tempo", d1_30: "1–30 hari", d31_60: "31–60 hari", d61_90: "61–90 hari", d90_plus: "> 90 hari" };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Object.entries(aging.buckets).map(([k, v]) => (
          <Card key={k}>
            <p className="text-caption text-ink-subtle">{labels[k] ?? k}</p>
            <p className={`mt-1 text-base font-semibold tabular-nums ${k === "d90_plus" && Number(v) > 0 ? "text-danger" : "text-ink"}`}>{rupiah(v)}</p>
          </Card>
        ))}
      </div>
      <Card>
        <div className="mb-2 flex justify-between text-sm">
          <span className="font-medium text-ink">Faktur belum lunas</span>
          <span className="tabular-nums text-ink">Total: {rupiah(aging.total)}</span>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-caption uppercase text-ink-subtle"><th className="py-1">No.</th><th>Customer</th><th className="text-right">Umur</th><th className="text-right">Outstanding</th></tr></thead>
          <tbody>
            {aging.items.map((it) => (
              <tr key={it.number} className="border-t border-line">
                <td className="py-1 text-ink-muted">{it.number}</td><td className="text-ink">{it.contact}</td>
                <td className="text-right tabular-nums text-ink-muted">{it.age_days} hr</td>
                <td className="text-right tabular-nums text-ink">{rupiah(it.outstanding)}</td>
              </tr>
            ))}
            {aging.items.length === 0 && <tr><td colSpan={4} className="py-3 text-center text-ink-subtle">Tidak ada piutang berjalan.</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
function StockVal({ stock }: { stock: Stock }) {
  return (
    <Card>
      <div className="mb-2 flex justify-between text-sm">
        <span className="font-medium text-ink">Valuasi Persediaan</span>
        <span className="tabular-nums text-ink">Total: {rupiah(stock.total_value)}</span>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-caption uppercase text-ink-subtle"><th className="py-1">SKU</th><th>Nama</th><th className="text-right">Qty</th><th className="text-right">Avg Cost</th><th className="text-right">Nilai</th></tr></thead>
        <tbody>
          {stock.items.map((it) => (
            <tr key={it.sku} className="border-t border-line">
              <td className="py-1 text-ink-muted">{it.sku}</td><td className="text-ink">{it.name}</td>
              <td className="text-right tabular-nums text-ink-muted">{Number(it.quantity)}</td>
              <td className="text-right tabular-nums text-ink-muted">{rupiah(it.avg_cost)}</td>
              <td className="text-right tabular-nums text-ink">{rupiah(it.value)}</td>
            </tr>
          ))}
          {stock.items.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-ink-subtle">Belum ada stok.</td></tr>}
        </tbody>
      </table>
    </Card>
  );
}
function Line({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className={bold ? "font-medium text-ink" : "text-ink-muted"}>{k}</span>
      <span className={`tabular-nums ${bold ? "font-semibold text-ink" : "text-ink"}`}>{rupiah(v)}</span>
    </div>
  );
}

/* ---------- GPM (margin per SKU & customer) ---------- */
function GpmView({ g }: { g: Gpm }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <p className="mb-2 text-sm font-medium text-ink">GPM per SKU</p>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-caption uppercase text-ink-subtle">
            <th className="py-1">SKU</th><th>Produk</th><th className="text-right">Omzet</th><th className="text-right">Margin</th><th className="text-right">GPM%</th>
          </tr></thead>
          <tbody>
            {g.by_sku.map((r) => (
              <tr key={r.sku} className="border-t border-line">
                <td className="py-1 text-ink-muted">{r.sku}</td><td className="text-ink">{r.name}</td>
                <td className="text-right tabular-nums text-ink-muted">{rupiah(r.revenue)}</td>
                <td className="text-right tabular-nums text-ink">{rupiah(r.margin)}</td>
                <td className="text-right tabular-nums text-primary">{r.gpm != null ? `${r.gpm}%` : "—"}</td>
              </tr>
            ))}
            {g.by_sku.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-ink-subtle">Belum ada penjualan pada periode ini.</td></tr>}
          </tbody>
        </table>
      </Card>
      <Card>
        <p className="mb-2 text-sm font-medium text-ink">GPM per Customer</p>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-caption uppercase text-ink-subtle">
            <th className="py-1">Customer</th><th className="text-right">Omzet</th><th className="text-right">Margin</th><th className="text-right">GPM%</th>
          </tr></thead>
          <tbody>
            {g.by_customer.map((r) => (
              <tr key={r.customer} className="border-t border-line">
                <td className="py-1 text-ink">{r.customer}</td>
                <td className="text-right tabular-nums text-ink-muted">{rupiah(r.revenue)}</td>
                <td className="text-right tabular-nums text-ink">{rupiah(r.margin)}</td>
                <td className="text-right tabular-nums text-primary">{r.gpm != null ? `${r.gpm}%` : "—"}</td>
              </tr>
            ))}
            {g.by_customer.length === 0 && <tr><td colSpan={4} className="py-3 text-center text-ink-subtle">Belum ada penjualan pada periode ini.</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

/* ---------- Ekspor CSV & Cetak/PDF ---------- */
type Tabular = { title: string; headers: string[]; rows: (string | number)[][] };

function tableFor(tab: string, data: any): Tabular {
  switch (tab) {
    case "Laba Rugi": {
      const rows: (string | number)[][] = [];
      (data.income ?? []).forEach((r: any) => rows.push(["Pendapatan", r.name, r.amount]));
      (data.expense ?? []).forEach((r: any) => rows.push(["Beban", r.name, r.amount]));
      rows.push(["", "Laba Bersih", data.net_profit]);
      return { title: "Laba Rugi", headers: ["Kelompok", "Akun", "Jumlah"], rows };
    }
    case "Arus Kas":
      return { title: "Arus Kas", headers: ["Bulan", "Masuk", "Keluar", "Bersih"],
        rows: (data.months ?? []).map((m: any) => [m.month, m.in, m.out, m.net]) };
    case "Rekap Kuartal":
      return { title: "Rekap Kuartal", headers: ["Kuartal", "Omzet", "HPP", "Laba Kotor"],
        rows: (data.items ?? []).map((i: any) => [i.quarter, i.omzet, i.hpp, i.gross_profit]) };
    case "AR Aging":
      return { title: "AR Aging", headers: ["No.", "Customer", "Umur (hari)", "Outstanding"],
        rows: (data.items ?? []).map((i: any) => [i.number, i.contact, i.age_days, i.outstanding]) };
    case "AR Limit":
      return { title: "AR Limit", headers: ["Customer", "Outstanding", "Limit", "Status"],
        rows: (data.items ?? []).map((i: any) => [i.customer, i.outstanding, i.credit_limit, i.status]) };
    case "Komisi":
      return { title: "Komisi", headers: ["SKU", "Produk", "Qty", "Omzet", "Margin", "Komisi"],
        rows: (data.items ?? []).map((i: any) => [i.sku, i.name, i.qty, i.revenue, i.margin, i.commission]) };
    case "GPM":
      return { title: "GPM per SKU", headers: ["SKU", "Produk", "Omzet", "Margin", "GPM%"],
        rows: (data.by_sku ?? []).map((i: any) => [i.sku, i.name, i.revenue, i.margin, i.gpm ?? ""]) };
    case "Valuasi Stok":
      return { title: "Valuasi Stok", headers: ["SKU", "Nama", "Qty", "Avg Cost", "Nilai"],
        rows: (data.items ?? []).map((i: any) => [i.sku, i.name, i.quantity, i.avg_cost, i.value]) };
    default:
      return { title: tab, headers: [], rows: [] };
  }
}

function exportCSV(tab: string, data: any) {
  if (!data) return;
  const t = tableFor(tab, data);
  const esc = (v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [t.headers, ...t.rows].map((r) => r.map(esc).join(",")).join("\r\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${t.title.replace(/\s+/g, "-")}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function printReport(tab: string, data: any) {
  if (!data) return;
  const t = tableFor(tab, data);
  const th = t.headers.map((h) => `<th>${h}</th>`).join("");
  const tr = t.rows.map((r) => `<tr>${r.map((c) => `<td>${String(c ?? "")}</td>`).join("")}</tr>`).join("");
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(`<!doctype html><html><head><title>${t.title}</title>
    <style>
      body{font-family:Arial,sans-serif;padding:24px;color:#1b2a26}
      h1{font-size:18px;margin:0 0 4px} p{color:#666;font-size:12px;margin:0 0 16px}
      table{width:100%;border-collapse:collapse;font-size:12px}
      th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}
      th{background:#f3f5f3} td:nth-child(n+3){text-align:right}
    </style></head><body>
    <h1>Ananta — ${t.title}</h1><p>Dicetak ${new Date().toLocaleString("id-ID")}</p>
    <table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>
    <script>window.onload=function(){window.print()}</script>
    </body></html>`);
  w.document.close();
}
