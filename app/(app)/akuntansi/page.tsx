"use client";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

export default function Page() {
  return (
    <>
      <Topbar title="Akuntansi" />
      <div className="p-6">
        <Card className="text-center">
          <p className="text-ink">Modul Akuntansi</p>
          <p className="mt-1 text-sm text-ink-muted">CoA via /api/v1/accounts. Tiap transaksi memposting jurnal otomatis (debit=kredit).</p>
        </Card>
      </div>
    </>
  );
}
