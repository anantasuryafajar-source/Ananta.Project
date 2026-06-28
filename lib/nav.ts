import {
  LayoutDashboard, ShoppingCart, Package, Truck, Wallet,
  BookOpen, Users, FileBarChart, Settings,
} from "lucide-react";

export const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/penjualan", label: "Penjualan", icon: ShoppingCart },
  { href: "/pembelian", label: "Pembelian", icon: Truck },
  { href: "/produk", label: "Produk & Stok", icon: Package },
  { href: "/kas-bank", label: "Kas & Bank", icon: Wallet },
  { href: "/akuntansi", label: "Akuntansi", icon: BookOpen },
  { href: "/kontak", label: "Kontak", icon: Users },
  { href: "/laporan", label: "Laporan", icon: FileBarChart },
  { href: "/pengaturan", label: "Pengaturan", icon: Settings },
] as const;
