import {
  LayoutDashboard, ShoppingCart, Package, Truck, Wallet,
  BookOpen, Users, FileBarChart, Settings, Warehouse, Bike,
  ClipboardList, ClipboardCheck, PiggyBank, Receipt,
} from "lucide-react";

export const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/sales-orders", label: "Sales Order", icon: ClipboardCheck },
  { href: "/penjualan", label: "Penjualan", icon: ShoppingCart },
  { href: "/purchase-orders", label: "Purchase Order", icon: ClipboardList },
  { href: "/pembelian", label: "Pembelian", icon: Truck },
  { href: "/produk", label: "Produk & Stok", icon: Package },
  { href: "/gudang", label: "Gudang & Transfer", icon: Warehouse },
  { href: "/kurir", label: "Kurir & Ongkir", icon: Bike },
  { href: "/kas-bank", label: "Kas & Bank", icon: Wallet },
  { href: "/biaya", label: "Biaya Operasional", icon: Receipt },
  { href: "/investor", label: "Investor", icon: PiggyBank },
  { href: "/akuntansi", label: "Akuntansi", icon: BookOpen },
  { href: "/kontak", label: "Kontak", icon: Users },
  { href: "/laporan", label: "Laporan", icon: FileBarChart },
  { href: "/pengaturan", label: "Pengaturan", icon: Settings },
] as const;
