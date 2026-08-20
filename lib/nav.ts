import {
  LayoutDashboard, ShoppingCart, Package, Truck, Wallet,
  BookOpen, Users, FileBarChart, Settings, Warehouse, Bike,
  ClipboardList, ClipboardCheck, PiggyBank, Receipt, Landmark, Sparkles,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Kata kunci tambahan untuk Ctrl+K — istilah lain yang mungkin diketik user. */
  kata?: readonly string[];
};

export type NavGroup = { judul: string; items: readonly NavItem[] };

/**
 * Sumber tunggal daftar menu, dikelompokkan supaya sidebar bisa dipindai mata
 * alih-alih dibaca satu per satu.
 *
 * Purchase Order & Sales Order TIDAK lagi jadi menu tersendiri: keduanya tahap
 * awal dari alur yang sama, jadi sekarang berupa tab di dalam Pembelian &
 * Penjualan. Supaya tetap bisa dicari dengan nama lamanya, lihat PINTASAN.
 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    judul: "Utama",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, kata: ["beranda", "home", "ringkasan"] },
      { href: "/asisten", label: "Asisten AI", icon: Sparkles, kata: ["chat", "ai", "tanya", "profiling"] },
    ],
  },
  {
    judul: "Transaksi",
    items: [
      { href: "/penjualan", label: "Penjualan", icon: ShoppingCart, kata: ["faktur", "invoice", "jual", "sales order", "so", "pesanan"] },
      { href: "/pembelian", label: "Pembelian", icon: Truck, kata: ["pengadaan", "bill", "tagihan", "supplier", "purchase order", "po", "pesanan", "beli"] },
    ],
  },
  {
    judul: "Persediaan",
    items: [
      { href: "/produk", label: "Produk & Stok", icon: Package, kata: ["barang", "sku", "master", "modal", "dus", "botol"] },
      { href: "/gudang", label: "Gudang & Transfer", icon: Warehouse, kata: ["mutasi", "pindah", "stok"] },
      { href: "/kurir", label: "Kurir & Ongkir", icon: Bike, kata: ["pengiriman", "ekspedisi", "antar"] },
    ],
  },
  {
    judul: "Keuangan",
    items: [
      { href: "/kas-bank", label: "Kas & Bank", icon: Wallet, kata: ["uang", "saldo", "bayar", "terima"] },
      { href: "/biaya", label: "Biaya Operasional", icon: Receipt, kata: ["pengeluaran", "beban", "ongkos"] },
      { href: "/investor", label: "Investor", icon: PiggyBank, kata: ["modal", "setoran", "pemilik"] },
      { href: "/akuntansi", label: "Akuntansi", icon: BookOpen, kata: ["jurnal", "buku besar", "coa", "akun"] },
      { href: "/rekonsiliasi", label: "Rekonsiliasi Bank", icon: Landmark, kata: ["cocokkan", "mutasi bank"] },
    ],
  },
  {
    judul: "Lainnya",
    items: [
      { href: "/kontak", label: "Kontak", icon: Users, kata: ["customer", "pelanggan", "supplier", "vendor"] },
      { href: "/laporan", label: "Laporan", icon: FileBarChart, kata: ["laba rugi", "neraca", "komisi", "pajak", "omzet"] },
      { href: "/pengaturan", label: "Pengaturan", icon: Settings, kata: ["setelan", "profil", "pengguna", "periode"] },
    ],
  },
];

/** Semua menu sebagai daftar datar (urutan mengikuti kelompok di atas). */
export const NAV: readonly NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

/**
 * Tujuan yang BUKAN menu tersendiri tapi tetap harus bisa dituju lewat Ctrl+K.
 * Tanpa ini, mengetik "purchase order" — nama yang dipakai orang sehari-hari —
 * tidak menemukan apa pun setelah menunya digabung jadi tab.
 */
export const PINTASAN: readonly NavItem[] = [
  {
    href: "/pembelian/pesanan",
    label: "Purchase Order (PO)",
    icon: ClipboardList,
    kata: ["po", "pesanan pembelian", "order ke supplier", "pengadaan"],
  },
  {
    href: "/penjualan/pesanan",
    label: "Sales Order (SO)",
    icon: ClipboardCheck,
    kata: ["so", "pesanan penjualan", "order customer"],
  },
];

/** Daftar yang dipakai command palette: menu + pintasan. */
export const PENCARIAN: readonly NavItem[] = [...NAV, ...PINTASAN];
