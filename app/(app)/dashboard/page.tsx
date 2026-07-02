"use client";
import { useEffect, useState } from "react";
import { AlertTriangle, PackageSearch, Clock, TrendingUp, TrendingDown } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

type Summary = {
  period: string;
  revenue_month: string; revenue_prev_month: string;
  cash_bank: string; receivable_total: string; payable_total: string; stock_value: string;
  trend: { month: string; omzet: string }[];
  alerts: {
    low_stock: { sku: string; name: string; quantity: string; min_stock: string }[];
    overdue_invoices: { number: string; due_date: string; customer: string; outstanding: string; days_late: number }[];
    over_limit: { customer: string; outstanding: string; credit_limit: string }[];
  };
  recent_invoices: { number: string; date: string; total: string; status: string; customer: string }[];
};

export default function DashboardPage() {
  const [d, setD] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Summary>("/dashboard/summary").then(setD).catch((e) => setError(e.message));
  }, []);

  const delta = d ? Number(d.revenue_month) - Number(d.revenue_prev_month) : 0;
  const deltaPct = d && Number(d.revenue_prev_month) > 0
    ? (delta / Number(d.revenue_prev_month)) * 100 : null;
  const alertCount = d
    ? d.alerts.low_stock.length + d.alerts.overdue_invoices.length + d.alerts.over_limit.length
    : 0;

  return (
    <>
      <Topbar title="Dashboard" />
      <div className="space-y-4 p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {!d && !error && <Card><p className="text-sm text-ink-muted">Memuat…</p></Card>}

        {d && (
          <>
            {/* KPI */}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Card>
                <p className="text-caption text-ink-subtle">Omzet bulan ini</p>
                <p className="mt-1 text-base font-semibold tabular-nums text-ink">{rupiah(d.revenue_month)}</p>
                {deltaPct != null && (
                  <p className={`mt-0.5 flex items-center gap-1 text-caption ${delta >= 0 ? "text-success" : "text-danger"}`}>
                    {delta >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                    {Math.abs(deltaPct).toFixed(0)}% vs bulan lalu
                  </p>
                )}
              </Card>
              <Kpi label="Kas & Bank" value={d.cash_bank} />
              <Kpi label="Piutang berjalan" value={d.receivable_total} />
              <Kpi label="Utang berjalan" value={d.payable_total} />
              <Kpi label="Nilai persediaan" value={d.stock_value} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {/* Tren omzet */}
              <Card>
                <p className="mb-3 text-sm font-medium text-ink">Omzet 6 bulan terakhir</p>
                <div className="h-52">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={d.trend.map((t) => ({ label: t.month.slice(2), value: Number(t.omzet) }))}>
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={(v) => `${(v / 1e6).toFixed(0)}jt`} tick={{ fontSize: 11 }} width={42} />
                      <Tooltip formatter={(v: number) => rupiah(v)} />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]} fill="#2f7d6b" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>

              {/* Peringatan */}
              <Card>
                <div className="mb-2 flex items-center gap-2">
                  <AlertTriangle size={16} className={alertCount ? "text-warning" : "text-ink-subtle"} />
                  <p className="text-sm font-medium text-ink">Peringatan</p>
                  {alertCount > 0 && (
                    <span className="rounded-full bg-danger/10 px-2 py-0.5 text-caption font-medium text-danger">{alertCount}</span>
                  )}
                </div>
                {alertCount === 0 && <p className="text-sm text-ink-subtle">Tidak ada peringatan — semua aman. 👍</p>}

                <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                  {d.alerts.overdue_invoices.map((o) => (
                    <AlertRow key={o.number} icon={<Clock size={14} />}
                      main={`${o.number} · ${o.customer}`}
                      sub={`telat ${o.days_late} hari · sisa ${rupiah(o.outstanding)}`} />
                  ))}
                  {d.alerts.low_stock.map((s) => (
                    <AlertRow key={s.sku} icon={<PackageSearch size={14} />}
                      main={s.name}
                      sub={`stok ${Number(s.quantity)} < minimum ${Number(s.min_stock)}`} />
                  ))}
                  {d.alerts.over_limit.map((c) => (
                    <AlertRow key={c.customer} icon={<AlertTriangle size={14} />}
                      main={c.customer}
                      sub={`piutang ${rupiah(c.outstanding)} melebihi limit ${rupiah(c.credit_limit)}`} />
                  ))}
                </div>
              </Card>
            </div>

            {/* Faktur terbaru */}
            <Card className="overflow-hidden p-0">
              <div className="border-b border-line px-4 py-3 text-sm font-medium text-ink">Faktur terbaru</div>
              <table className="w-full text-sm">
                <tbody>
                  {d.recent_invoices.map((r) => (
                    <tr key={r.number} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-2.5 text-ink">{r.number}</td>
                      <td className="px-4 py-2.5 text-ink-muted">{tanggal(r.date)}</td>
                      <td className="px-4 py-2.5 text-ink-muted">{r.customer}</td>
                      <td className={`px-4 py-2.5 capitalize ${r.status === "paid" ? "text-success" : r.status === "overdue" ? "text-danger" : "text-ink-muted"}`}>{r.status}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-ink">{rupiah(r.total)}</td>
                    </tr>
                  ))}
                  {d.recent_invoices.length === 0 && (
                    <tr><td className="px-4 py-4 text-center text-ink-subtle">Belum ada faktur.</td></tr>
                  )}
                </tbody>
              </table>
            </Card>
          </>
        )}
      </div>
    </>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <p className="text-caption text-ink-subtle">{label}</p>
      <p className="mt-1 text-base font-semibold tabular-nums text-ink">{rupiah(value)}</p>
    </Card>
  );
}

function AlertRow({ icon, main, sub }: { icon: React.ReactNode; main: string; sub: string }) {
  return (
    <div className="flex items-start gap-2 rounded-[var(--radius-input)] bg-surface-sunken px-3 py-2">
      <span className="mt-0.5 text-warning">{icon}</span>
      <div className="min-w-0">
        <p className="truncate text-sm text-ink">{main}</p>
        <p className="text-caption text-ink-subtle">{sub}</p>
      </div>
    </div>
  );
}
