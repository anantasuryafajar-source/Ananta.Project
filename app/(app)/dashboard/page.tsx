"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { KpiCard } from "@/components/ananta/kpi-card";
import { Card } from "@/components/ui/card";

type Summary = {
  revenue_month: string; receivable_total: string;
  payable_total: string; stock_value: string; period: string;
};

export default function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Summary>("/dashboard/summary").then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <Topbar title="Dashboard" />
      <div className="p-6">
        {error && (
          <Card className="border-danger/30">
            <p className="text-sm text-danger">{error}</p>
            <p className="mt-1 text-caption text-ink-subtle">
              Pastikan API berjalan & kamu sudah masuk.
            </p>
          </Card>
        )}

        {!data && !error && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-28 animate-pulse rounded-[var(--radius-card)] bg-surface-sunken" />
            ))}
          </div>
        )}

        {data && (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Pendapatan bulan ini" value={rupiah(data.revenue_month)} hint={`Sejak ${tanggal(data.period)}`} />
              <KpiCard label="Total piutang" value={rupiah(data.receivable_total)} />
              <KpiCard label="Total utang" value={rupiah(data.payable_total)} />
              <KpiCard label="Nilai persediaan" value={rupiah(data.stock_value)} hint="Qty × average cost" />
            </div>
            <Card className="mt-6">
              <p className="text-h3 font-semibold text-ink">Arus kas</p>
              <div className="mt-4 grid h-48 place-items-center text-ink-subtle">
                <p className="text-sm">Grafik arus kas akan tampil di sini (Recharts).</p>
              </div>
            </Card>
          </>
        )}
      </div>
    </>
  );
}
