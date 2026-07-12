import type { Metadata } from "next";
import { Hanken_Grotesk, Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import { PWARegister } from "@/components/pwa-register";

const hanken = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-hanken" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: {
    default: "Ananta — Sistem Akuntansi & Distribusi",
    template: "%s · Ananta",
  },
  description: "Sistem manajemen bisnis, akuntansi, dan distribusi PT ASF.",
  applicationName: "Ananta",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Ananta",
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", type: "image/png", sizes: "192x192" },
      { url: "/icon-512.png", type: "image/png", sizes: "512x512" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  other: {
    "facebook-domain-verification": "7pvgqfj2w2nqrwipm2thoquj7jzozu",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#2F6F5E",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="id"
      className={`${hanken.variable} ${inter.variable} ${geistMono.variable}`}
    >
      <body className="bg-canvas text-ink antialiased">
        <PWARegister />
        {children}
      </body>
    </html>
  );
}
