"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

type Invoice = {
  id: string; number: string; date: string; due_date: string | null;
  status: string; total: string; paid_total: string;
};
const STATUS: Record<string, string> = {
  draft: "text-ink-subtle", posted: "text-primary", paid: "text-success",
  overdue: "text-danger", void: "text-ink-subtle",
};

export default function PenjualanPage() {
  const [items, setItems] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Invoice[]>("/invoices").then(setItems).catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <Topbar title="Penjualan" />
      <div className="p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada faktur.</p>
            <p className="mt-1 text-sm text-ink-muted">
              POST <code className="rounded bg-surface-sunken px-1">/api/v1/invoices</code> untuk menerbitkan faktur — jurnal & stok otomatis.
            </p>
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
              </tr></thead>
              <tbody>
                {items.map((v) => (
                  <tr key={v.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{v.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(v.date)}</td>
                    <td className={`px-4 py-3 capitalize ${STATUS[v.status] ?? "text-ink-muted"}`}>{v.status}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(v.total)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(v.paid_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </>
  );
}
