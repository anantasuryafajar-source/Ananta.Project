"use client";
import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { NAV_GROUPS } from "@/lib/nav";
import { ContinuityRibbon } from "./continuity-ribbon";
import { useMobileNav } from "./nav-context";

export function Sidebar() {
  const path = usePathname();
  const { open, setOpen } = useMobileNav();

  // Tutup drawer otomatis tiap pindah halaman.
  useEffect(() => {
    setOpen(false);
  }, [path, setOpen]);

  return (
    <>
      {/* Lapisan gelap di belakang drawer (hanya mobile) */}
      <div
        onClick={() => setOpen(false)}
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden
      />

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen w-60 shrink-0 flex-col border-r border-line bg-surface transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-start justify-between px-5 py-5">
          <div>
            <div className="flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-mark.svg" alt="" className="h-6 w-auto" />
              <span className="font-display text-xl font-bold tracking-tight text-ink">Ananta</span>
            </div>
            <ContinuityRibbon className="mt-1 opacity-80" />
          </div>
          {/* Tombol tutup — hanya tampil di mobile */}
          <button
            onClick={() => setOpen(false)}
            className="-mr-1 rounded-[var(--radius-button)] p-1 text-ink-muted hover:bg-surface-sunken md:hidden"
            aria-label="Tutup menu"
          >
            <X size={18} />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 pb-2">
          {NAV_GROUPS.map(({ judul, items }) => (
            <div key={judul} className="mb-4 last:mb-0">
              <p className="px-3 pb-1 text-caption font-medium uppercase tracking-wide text-ink-subtle">
                {judul}
              </p>
              <div className="space-y-1">
                {items.map(({ href, label, icon: Icon }) => {
                  // startsWith, bukan cocok persis: menu induk harus tetap
                  // menyala saat sub-tab dibuka (mis. /pembelian/pesanan).
                  const active = path === href || path.startsWith(`${href}/`);
                  return (
                    <Link
                      key={href}
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-3 rounded-[var(--radius-input)] px-3 py-2 text-sm transition-colors ${
                        active
                          ? "bg-primary-soft font-medium text-primary"
                          : "text-ink-muted hover:bg-surface-sunken"
                      }`}
                    >
                      <Icon size={18} strokeWidth={1.8} />
                      {label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <p className="px-5 py-4 text-caption text-ink-subtle">v0.9.1 · Calm Ledger</p>
      </aside>
    </>
  );
}
