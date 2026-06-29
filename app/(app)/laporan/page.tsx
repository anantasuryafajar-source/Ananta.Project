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
type PL = {
  period: { start: string; end: string };
  income: Row[]; expense: Row[];
  total_income: string; total_expense: string; net_profit: string;
};
type Aging = {
  buckets: Record<string, string>; total: string;
  items: { number: string; contact: string; age_days: number; outstanding: string }[];
};
type Stock = { items: { sku: string; name: string; quantity: string; avg_cost: string; value: string }[]; total_value: string };

const TABS = ["Laba Rugi", "AR Aging", "Valuasi Stok"] as const;
type Tab = (typeof TABS)[number];

function today() { return new Date().toISOString().slice(0, 10); }
function yearStart() { return `${new Date().getFullYear()}-01-01`; }

export default function LaporanPage() {
  const [tab, setTab] = useState<Tab>("Laba Rugi");
  const [start, setStart] = useState(yearStart());
  const [end, setEnd] = useState(today());
  const [pl, setPl] = useState<PL | null>(null);
  const [aging, setAging] = useState<Aging | null>(null);
  const [stock, setStock] = useState<Stock | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setErr(null); setLoading(true);
    try {
      if (tab === "Laba Rugi")
        setPl(await api<PL>(`/reports/profit-loss?start=${start}&end=${end}`));
      else if (tab === "AR Aging")
        setAging(await api<Aging>(`/reports/ar-aging?as_of=${end}`));
      else setStock(await api<Stock>(`/reports/stock-valuation`));
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
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-[var(--radius-input)] px-3 py-1.5 text-sm transition-colors ${
                tab === t ? "bg-primary text-white" : "bg-surface-sunken text-ink-muted hover:text-ink"
              }`}
            >
              {t}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2 text-sm text-ink-muted">
            {tab === "Laba Rugi" && (
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1" />
            )}
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
              className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1" />
          </div>
        </div>

        {err && <Card className="text-sm text-danger">{err}</Card>}
        {loading && <Card className="text-sm text-ink-muted">Memuat…</Card>}

        {!loading && tab === "Laba Rugi" && pl && <ProfitLoss pl={pl} />}
        {!loading && tab === "AR Aging" && aging && <ArAging aging={aging} />}
        {!loading && tab === "Valuasi Stok" && stock && <StockVal stock={stock} />}
      </div>
    </>
  );
}

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
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chart.map((c, i) => <Cell key={i} fill={c.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <dl className="mt-2 space-y-1 text-sm">
          <Line k="Total Pendapatan" v={pl.total_income} />
          <Line k="Total Beban" v={pl.total_expense} />
          <div className="border-t border-line pt-1">
            <Line k="Laba Bersih" v={pl.net_profit} bold />
          </div>
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
  const labels: Record<string, string> = {
    current: "Belum jatuh tempo", d1_30: "1–30 hari", d31_60: "31–60 hari",
    d61_90: "61–90 hari", d90_plus: "> 90 hari",
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Object.entries(aging.buckets).map(([k, v]) => (
          <Card key={k}>
            <p className="text-caption text-ink-subtle">{labels[k]}</p>
            <p className={`mt-1 text-base font-semibold tabular-nums ${k === "d90_plus" && Number(v) > 0 ? "text-danger" : "text-ink"}`}>
              {rupiah(v)}
            </p>
          </Card>
        ))}
      </div>
      <Card>
        <div className="mb-2 flex justify-between text-sm">
          <span className="font-medium text-ink">Faktur belum lunas</span>
          <span className="tabular-nums text-ink">Total: {rupiah(aging.total)}</span>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-caption uppercase text-ink-subtle">
            <th className="py-1">No.</th><th>Customer</th><th className="text-right">Umur</th><th className="text-right">Outstanding</th>
          </tr></thead>
          <tbody>
            {aging.items.map((it) => (
              <tr key={it.number} className="border-t border-line">
                <td className="py-1 text-ink-muted">{it.number}</td>
                <td className="text-ink">{it.contact}</td>
                <td className="text-right tabular-nums text-ink-muted">{it.age_days} hr</td>
                <td className="text-right tabular-nums text-ink">{rupiah(it.outstanding)}</td>
              </tr>
            ))}
            {aging.items.length === 0 && (
              <tr><td colSpan={4} className="py-3 text-center text-ink-subtle">Tidak ada piutang berjalan.</td></tr>
            )}
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
        <thead><tr className="text-left text-caption uppercase text-ink-subtle">
          <th className="py-1">SKU</th><th>Nama</th><th className="text-right">Qty</th>
          <th className="text-right">Avg Cost</th><th className="text-right">Nilai</th>
        </tr></thead>
        <tbody>
          {stock.items.map((it) => (
            <tr key={it.sku} className="border-t border-line">
              <td className="py-1 text-ink-muted">{it.sku}</td>
              <td className="text-ink">{it.name}</td>
              <td className="text-right tabular-nums text-ink-muted">{Number(it.quantity)}</td>
              <td className="text-right tabular-nums text-ink-muted">{rupiah(it.avg_cost)}</td>
              <td className="text-right tabular-nums text-ink">{rupiah(it.value)}</td>
            </tr>
          ))}
          {stock.items.length === 0 && (
            <tr><td colSpan={5} className="py-3 text-center text-ink-subtle">Belum ada stok. Catat pembelian dulu.</td></tr>
          )}
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
