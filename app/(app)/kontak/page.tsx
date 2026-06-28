"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupiah } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

type Contact = {
  id: string; name: string; type: string; phone: string | null;
  payment_term_days: number; credit_limit: string;
};

export default function KontakPage() {
  const [items, setItems] = useState<Contact[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Contact[]>("/contacts").then(setItems).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <Topbar title="Kontak" />
      <div className="p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada kontak.</p>
            <p className="mt-1 text-sm text-ink-muted">Tambah pelanggan atau pemasok pertamamu.</p>
          </Card>
        )}
        {items && items.length > 0 && (
          <Card className="p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-caption text-ink-muted">
                  <th className="px-4 py-3 font-medium">Nama</th>
                  <th className="px-4 py-3 font-medium">Tipe</th>
                  <th className="px-4 py-3 font-medium">Termin</th>
                  <th className="px-4 py-3 text-right font-medium">Limit kredit</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{c.name}</td>
                    <td className="px-4 py-3 text-ink-muted capitalize">{c.type}</td>
                    <td className="px-4 py-3 text-ink-muted">{c.payment_term_days} hari</td>
                    <td className="num px-4 py-3 text-right text-ink">{rupiah(c.credit_limit)}</td>
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
