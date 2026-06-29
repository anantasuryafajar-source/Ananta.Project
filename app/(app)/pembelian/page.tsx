"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

type Bill = {
  id: string; number: string; date: string; status: string;
  total: string; paid_total: string;
};
const STATUS: Record<string, string> = {
  posted: "text-primary", paid: "text-success", overdue: "text-danger",
};

export default function PembelianPage() {
  const [items, setItems] = useState<Bill[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Bill[]>("/bills").then(setItems).catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <Topbar title="Pembelian / Pengadaan" />
      <div className="p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada pengadaan.</p>
            <p className="mt-1 text-sm text-ink-muted">
              POST <code className="rounded bg-surface-sunken px-1">/api/v1/bills</code> — barang masuk + average cost + jurnal utang otomatis.
            </p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No. Bill</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 text-right font-medium">Terbayar</th>
              </tr></thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{b.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(b.date)}</td>
                    <td className={`px-4 py-3 capitalize ${STATUS[b.status] ?? "text-ink-muted"}`}>{b.status}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(b.total)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(b.paid_total)}</td>
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
