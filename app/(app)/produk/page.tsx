"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupiah } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

type Product = {
  id: string; sku: string; name: string; unit: string;
  sale_price: string; purchase_price: string;
};
type StockItem = { sku: string; quantity: string; avg_cost: string; value: string };
type Stock = { items: StockItem[]; total_value: string };

export default function ProdukPage() {
  const [items, setItems] = useState<Product[] | null>(null);
  const [stock, setStock] = useState<Record<string, StockItem>>({});
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Product[]>("/products").then(setItems).catch((e) => setError(e.message));
    api<Stock>("/reports/stock-valuation")
      .then((s) => setStock(Object.fromEntries(s.items.map((i) => [i.sku, i]))))
      .catch(() => {});
  }, []);
  return (
    <>
      <Topbar title="Produk & Stok" />
      <div className="p-6">
        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">SKU</th>
                <th className="px-4 py-3 font-medium">Nama</th>
                <th className="px-4 py-3 text-right font-medium">Modal</th>
                <th className="px-4 py-3 text-right font-medium">Harga Jual</th>
                <th className="px-4 py-3 text-right font-medium">Stok</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
              </tr></thead>
              <tbody>
                {items.map((p) => {
                  const s = stock[p.sku];
                  return (
                    <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                      <td className="px-4 py-3 text-ink-muted">{p.sku}</td>
                      <td className="px-4 py-3 text-ink">{p.name}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{rupiah(p.purchase_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(p.sale_price)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{s ? Number(s.quantity) : 0}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{s ? rupiah(s.value) : rupiah(0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </>
  );
}
