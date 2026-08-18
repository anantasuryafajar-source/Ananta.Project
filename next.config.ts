import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const apiBase = process.env.API_BASE;

// Akar workspace dikunci ke folder proyek. Tanpa ini Next menemukan
// package-lock.json nyasar di C:\Users\ASUS dan menyimpulkan SELURUH folder
// home sebagai akar — Turbopack lalu memantau area yang jauh lebih luas dari
// yang diperlukan, memperbesar cache .next/dev dan memperlambat dev server.
const akarProyek = path.dirname(fileURLToPath(import.meta.url));

const config: NextConfig = {
  turbopack: { root: akarProyek },

  // Proxy /api ke backend HANYA jika API_BASE diset (mis. saat dev lokal).
  // Di Vercel tanpa backend, rewrite dilewati supaya build & halaman tetap jalan.
  async rewrites() {
    if (!apiBase) return [];
    return [{ source: "/api/:path*", destination: `${apiBase}/api/:path*` }];
  },

  // Purchase Order & Sales Order pindah jadi tab di dalam Pembelian & Penjualan.
  // Alamat lamanya dipertahankan sebagai redirect supaya bookmark, tautan yang
  // pernah dibagikan, dan riwayat browser tidak mati. permanent: false dipilih
  // sengaja — redirect permanen di-cache browser selamanya dan sulit ditarik
  // kembali kalau nanti strukturnya berubah lagi.
  async redirects() {
    return [
      { source: "/purchase-orders", destination: "/pembelian/pesanan", permanent: false },
      { source: "/sales-orders", destination: "/penjualan/pesanan", permanent: false },
    ];
  },
};

export default config;
