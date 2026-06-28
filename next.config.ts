import type { NextConfig } from "next";

const apiBase = process.env.API_BASE;

const config: NextConfig = {
  // Proxy /api ke backend HANYA jika API_BASE diset (mis. saat dev lokal).
  // Di Vercel tanpa backend, rewrite dilewati supaya build & halaman tetap jalan.
  async rewrites() {
    if (!apiBase) return [];
    return [{ source: "/api/:path*", destination: `${apiBase}/api/:path*` }];
  },
};

export default config;
