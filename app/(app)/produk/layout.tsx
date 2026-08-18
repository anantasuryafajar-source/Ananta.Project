import type { ReactNode } from "react";
import { Topbar } from "@/components/ananta/topbar";
import { TabHalaman } from "@/components/ananta/tab-halaman";

/** Produk & Penyesuaian Stok. Isi tab ada di tab-halaman.tsx. */
export default function LayoutProduk({ children }: { children: ReactNode }) {
  return (
    <>
      <Topbar title="Produk & Stok" />
      <TabHalaman grup="produk" />
      {children}
    </>
  );
}
