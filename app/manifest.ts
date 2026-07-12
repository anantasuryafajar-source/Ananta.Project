import type { MetadataRoute } from "next";

/**
 * Web App Manifest — membuat Ananta bisa di-install ke layar HP (PWA).
 * Next otomatis menyajikan ini di /manifest.webmanifest dan menautkannya.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Ananta — Akuntansi & Distribusi",
    short_name: "Ananta",
    description: "Sistem manajemen bisnis, akuntansi, dan distribusi PT ASF.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#F6F8F6",
    theme_color: "#2F6F5E",
    lang: "id",
    dir: "ltr",
    categories: ["business", "finance", "productivity"],
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
