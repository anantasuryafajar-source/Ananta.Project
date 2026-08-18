import type { ReactNode } from "react";
import { Topbar } from "@/components/ananta/topbar";
import { TabHalaman } from "@/components/ananta/tab-halaman";

/** Pembelian & Purchase Order = satu alur, dua tahap. Isi tab ada di tab-halaman.tsx. */
export default function LayoutPembelian({ children }: { children: ReactNode }) {
  return (
    <>
      <Topbar title="Pembelian" />
      <TabHalaman grup="pembelian" />
      {children}
    </>
  );
}
