"use client";
import { useEffect, useState, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Search, CornerDownLeft } from "lucide-react";
import { NAV } from "@/lib/nav";

/**
 * Command palette: tekan Ctrl/Cmd+K dari mana saja untuk melompat cepat
 * ke menu mana pun tanpa mengklik sidebar. Navigasi keyboard penuh
 * (panah atas/bawah, Enter, Esc). Murni sisi klien — memakai daftar NAV.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // toggle dengan Ctrl/Cmd+K
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // reset & fokus saat dibuka
  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const results = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return NAV;
    return NAV.filter((n) => n.label.toLowerCase().includes(t));
  }, [q]);

  useEffect(() => { setActive(0); }, [q]);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (results[active]) go(results[active].href); }
  }

  return (
    <>
      {/* Pemicu terlihat di topbar */}
      <button
        onClick={() => setOpen(true)}
        className="hidden items-center gap-2 rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-1.5 text-ink-subtle transition-colors hover:text-ink md:flex"
        aria-label="Buka pencarian cepat"
      >
        <Search size={15} />
        <span className="text-caption">Cari… (Ctrl+K)</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center bg-black/30 pt-[12vh]"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-pop)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 border-b border-line px-4 py-3">
              <Search size={16} className="text-ink-subtle" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Lompat ke menu… (ketik nama halaman)"
                className="flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-subtle"
              />
              <kbd className="rounded border border-line px-1.5 py-0.5 text-[10px] text-ink-subtle">Esc</kbd>
            </div>

            <div className="max-h-72 overflow-y-auto p-1.5">
              {results.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-ink-subtle">Tidak ada menu yang cocok.</p>
              )}
              {results.map((n, i) => {
                const Icon = n.icon;
                return (
                  <button
                    key={n.href}
                    onClick={() => go(n.href)}
                    onMouseEnter={() => setActive(i)}
                    className={`flex w-full items-center gap-3 rounded-[var(--radius-input)] px-3 py-2 text-left text-sm transition-colors ${
                      i === active ? "bg-primary text-white" : "text-ink hover:bg-surface-sunken"
                    }`}
                  >
                    <Icon size={16} className={i === active ? "text-white" : "text-ink-subtle"} />
                    <span className="flex-1">{n.label}</span>
                    {i === active && <CornerDownLeft size={14} className="text-white/80" />}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-3 border-t border-line px-4 py-2 text-[11px] text-ink-subtle">
              <span className="flex items-center gap-1"><kbd className="rounded border border-line px-1">↑</kbd><kbd className="rounded border border-line px-1">↓</kbd> pilih</span>
              <span className="flex items-center gap-1"><kbd className="rounded border border-line px-1">↵</kbd> buka</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
