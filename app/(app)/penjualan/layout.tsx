import type { ReactNode } from "react";
import { Topbar } from "@/components/ananta/topbar";
import { TabHalaman } from "@/components/ananta/tab-halaman";

/** Penjualan & Sales Order = satu alur, dua tahap. Isi tab ada di tab-halaman.tsx. */
export default function LayoutPenjualan({ children }: { children: ReactNode }) {
  return (
    <>
      <Topbar title="Penjualan" />
      <TabHalaman grup="penjualan" />
      {children}
    </>
  );
}
