import type { Metadata } from "next";
import { Hanken_Grotesk, Inter, Geist_Mono } from "next/font/google";
import "./globals.css";

const hanken = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-hanken" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: {
    default: "Ananta — Sistem Akuntansi & Distribusi",
    template: "%s · Ananta",
  },
  description: "Sistem manajemen bisnis, akuntansi, dan distribusi PT ASF.",
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/icon.svg" }],
  },
  other: {
    "facebook-domain-verification": "7pvgqfj2w2nqrwipm2thoquj7jzozu",
  },
};

export const viewport = {
  themeColor: "#2F6F5E",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="id"
      className={`${hanken.variable} ${inter.variable} ${geistMono.variable}`}
    >
      <body className="bg-canvas text-ink antialiased">{children}</body>
    </html>
  );
}
