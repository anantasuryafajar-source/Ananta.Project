"use client";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

export default function ProdukPage() {
  return (
    <>
      <Topbar title="Produk & Stok" />
      <div className="p-6">
        <Card className="text-center">
          <p className="text-ink">Modul Produk siap dikembangkan.</p>
          <p className="mt-1 text-sm text-ink-muted">
            API <code className="rounded bg-surface-sunken px-1">/api/v1/products</code> sudah tersedia — tinggal sambungkan tabel & form.
          </p>
        </Card>
      </div>
    </>
  );
}
