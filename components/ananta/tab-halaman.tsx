"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Truck, ClipboardList, ShoppingCart, ClipboardCheck, Package, ClipboardPen,
  type LucideIcon,
} from "lucide-react";

/**
 * Deret tombol untuk berpindah antar halaman serumpun — mis. Pembelian:
 * "Barang Masuk" & "Pesanan (PO)".
 *
 * Sengaja berbentuk TOMBOL, bukan tab garis bawah: bagian ini mengganti dua
 * menu sidebar yang dulu berdiri sendiri, jadi harus terlihat jelas bisa
 * diklik — bukan sekadar judul. Gayanya mengikuti components/ui/button.tsx
 * (primary & secondary) supaya konsisten dengan tombol lain di aplikasi.
 *
 * Definisi tab ADA DI SINI, bukan di layout.tsx. Layout adalah Server
 * Component, dan komponen ikon tidak bisa dioper melintasi batas server->klien
 * ("Only plain objects can be passed to Client Components"). Karena itu layout
 * hanya mengirim nama grup berupa string, dan seluruh isinya dirakit di modul
 * klien ini.
 *
 * `hint` sengaja ada dan ditampilkan: tab "Pesanan" belum menyentuh jurnal
 * maupun stok, sedangkan tab utama mencatat keduanya. Menggabungkan keduanya
 * dalam satu menu tanpa keterangan membuat orang mengira barang sudah masuk
 * padahal baru dipesan.
 */
type Tab = { href: string; label: string; hint: string; icon: LucideIcon };

export type GrupTab = "pembelian" | "penjualan" | "produk";

const GRUP: Record<GrupTab, readonly Tab[]> = {
  pembelian: [
    {
      href: "/pembelian",
      label: "Barang Masuk",
      hint: "Barang sudah diterima — stok bertambah, utang & jurnal tercatat, modal rata-rata diperbarui.",
      icon: Truck,
    },
    {
      href: "/pembelian/pesanan",
      label: "Pesanan (PO)",
      hint: "Pesanan ke supplier. Belum ada stok, utang, maupun jurnal — semua baru tercatat saat barang diterima.",
      icon: ClipboardList,
    },
  ],
  produk: [
    {
      href: "/produk",
      label: "Produk & Stok",
      hint: "Master produk beserta saldo stok terkini. Angka stok di sini hanya berubah lewat transaksi atau penyesuaian.",
      icon: Package,
    },
    {
      href: "/produk/penyesuaian",
      label: "Penyesuaian Stok",
      hint: "Masukkan hasil hitung fisik gudang. Sistem menghitung sendiri selisihnya terhadap catatan, lalu memposting jurnalnya.",
      icon: ClipboardPen,
    },
  ],
  penjualan: [
    {
      href: "/penjualan",
      label: "Faktur",
      hint: "Barang sudah keluar — stok berkurang, piutang, pendapatan & HPP tercatat di jurnal.",
      icon: ShoppingCart,
    },
    {
      href: "/penjualan/pesanan",
      label: "Pesanan (SO)",
      hint: "Pesanan dari customer. Belum ada stok keluar, piutang, maupun jurnal — semua baru tercatat saat dibuatkan faktur.",
      icon: ClipboardCheck,
    },
  ],
};

export function TabHalaman({ grup }: { grup: GrupTab }) {
  const path = usePathname();
  const tabs = GRUP[grup];
  // Cocok persis, bukan startsWith: tab induk ("/pembelian") akan selalu
  // cocok dengan sub-tab ("/pembelian/pesanan") kalau memakai startsWith.
  const aktif = tabs.find((t) => t.href === path) ?? tabs[0];

  return (
    <div className="border-b border-line bg-surface px-6 py-3">
      <nav className="flex flex-wrap gap-2" aria-label="Bagian halaman">
        {tabs.map(({ href, label, icon: Icon }) => {
          const on = href === aktif.href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={on ? "page" : undefined}
              className={`inline-flex items-center gap-2 rounded-[var(--radius-button)] border px-4 py-2 text-sm font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ring)] ${
                on
                  ? "border-primary bg-primary text-white"
                  : "border-line bg-surface text-ink hover:bg-surface-sunken"
              }`}
            >
              <Icon size={16} strokeWidth={1.8} />
              {label}
            </Link>
          );
        })}
      </nav>
      <p className="mt-2 text-caption text-ink-subtle">{aktif.hint}</p>
    </div>
  );
}
