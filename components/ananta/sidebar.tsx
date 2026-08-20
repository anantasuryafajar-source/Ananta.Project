"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { X, ChevronDown, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NAV_GROUPS } from "@/lib/nav";
import { ContinuityRibbon } from "./continuity-ribbon";
import { useMobileNav } from "./nav-context";

const KUNCI_RAMPING = "ananta:sidebar-ramping";
const KUNCI_LIPAT = "ananta:sidebar-lipat";

export function Sidebar() {
  const path = usePathname();
  const { open, setOpen } = useMobileNav();

  // Mode ramping: cuma ikon, tanpa label. Hanya berlaku di layar md ke atas —
  // di mobile sidebar berupa drawer yang memang sudah tersembunyi.
  const [ramping, setRamping] = useState(false);
  // Kelompok yang sedang dilipat, disimpan sebagai daftar judul.
  const [terlipat, setTerlipat] = useState<string[]>([]);
  // Preferensi baru dibaca SETELAH mount supaya render server & klien sama.
  // localStorage tidak ada di server; membacanya saat render bikin hydration
  // mismatch dan React akan membuang seluruh markup sidebar lalu render ulang.
  const [siap, setSiap] = useState(false);

  useEffect(() => {
    try {
      setRamping(localStorage.getItem(KUNCI_RAMPING) === "1");
      const l = localStorage.getItem(KUNCI_LIPAT);
      if (l) setTerlipat(JSON.parse(l));
    } catch {
      /* localStorage diblokir (mode privat/embed) — pakai bawaan saja */
    }
    setSiap(true);
  }, []);

  function simpan(kunci: string, nilai: string) {
    try { localStorage.setItem(kunci, nilai); } catch { /* abaikan */ }
  }

  function toggleRamping() {
    const next = !ramping;
    setRamping(next);
    simpan(KUNCI_RAMPING, next ? "1" : "0");
  }

  function toggleLipat(judul: string) {
    const next = terlipat.includes(judul)
      ? terlipat.filter((j) => j !== judul)
      : [...terlipat, judul];
    setTerlipat(next);
    simpan(KUNCI_LIPAT, JSON.stringify(next));
  }

  // Tutup drawer otomatis tiap pindah halaman.
  useEffect(() => { setOpen(false); }, [path, setOpen]);

  const aktif = (href: string) => path === href || path.startsWith(`${href}/`);

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
        className={`fixed inset-y-0 left-0 z-50 flex h-screen w-60 shrink-0 flex-col border-r border-line bg-surface transition-[transform,width] duration-200 md:static md:z-auto md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        } ${ramping ? "md:w-16" : "md:w-60"}`}
      >
        <div className="flex items-start justify-between px-5 py-5">
          <div className={ramping ? "md:hidden" : ""}>
            <div className="flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-mark.svg" alt="" className="h-6 w-auto" />
              <span className="font-display text-xl font-bold tracking-tight text-ink">Ananta</span>
            </div>
            <ContinuityRibbon className="mt-1 opacity-80" />
          </div>
          {ramping && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src="/logo-mark.svg" alt="Ananta" className="mx-auto hidden h-6 w-auto md:block" />
          )}
          {/* Tombol tutup — hanya mobile */}
          <button
            onClick={() => setOpen(false)}
            className="-mr-1 rounded-[var(--radius-button)] p-1 text-ink-muted hover:bg-surface-sunken md:hidden"
            aria-label="Tutup menu"
          >
            <X size={18} />
          </button>
        </div>

        <nav className={`flex-1 overflow-y-auto px-3 pb-2 ${ramping ? "md:px-2" : ""}`}>
          {NAV_GROUPS.map(({ judul, items }) => {
            // Kelompok yang memuat halaman aktif TIDAK boleh ikut terlipat —
            // kalau tidak, menu yang sedang dibuka menghilang dari sidebar dan
            // orang kehilangan orientasi tentang di mana dirinya berada.
            const punyaAktif = items.some((i) => aktif(i.href));
            const dilipat = siap && terlipat.includes(judul) && !punyaAktif;

            return (
              <div key={judul} className="mb-4 last:mb-0">
                {/* Judul kelompok merangkap tombol lipat. Disembunyikan saat
                    ramping karena tidak ada ruang untuk teksnya. */}
                <button
                  type="button"
                  onClick={() => toggleLipat(judul)}
                  aria-expanded={!dilipat}
                  disabled={punyaAktif}
                  title={punyaAktif ? "Berisi halaman yang sedang dibuka" : undefined}
                  className={`flex w-full items-center justify-between rounded-[var(--radius-input)] px-3 py-1 text-caption font-medium uppercase tracking-wide text-ink-subtle transition-colors hover:text-ink-muted disabled:cursor-default disabled:hover:text-ink-subtle ${
                    ramping ? "md:hidden" : ""
                  }`}
                >
                  {judul}
                  {!punyaAktif && (
                    <ChevronDown
                      size={14}
                      className={`transition-transform ${dilipat ? "-rotate-90" : ""}`}
                    />
                  )}
                </button>

                <div className={`space-y-1 ${dilipat ? "hidden" : ""}`}>
                  {items.map(({ href, label, icon: Icon }) => {
                    const active = aktif(href);
                    return (
                      <Link
                        key={href}
                        href={href}
                        aria-current={active ? "page" : undefined}
                        title={ramping ? label : undefined}
                        className={`flex items-center gap-3 rounded-[var(--radius-input)] px-3 py-2 text-sm transition-colors ${
                          ramping ? "md:justify-center md:px-2" : ""
                        } ${
                          active
                            ? "bg-primary-soft font-medium text-primary"
                            : "text-ink-muted hover:bg-surface-sunken"
                        }`}
                      >
                        <Icon size={18} strokeWidth={1.8} className="shrink-0" />
                        <span className={ramping ? "md:hidden" : ""}>{label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Sempitkan/lebarkan — hanya relevan di layar lebar */}
        <div className={`hidden border-t border-line py-2 md:block ${ramping ? "px-2" : "px-3"}`}>
          <button
            type="button"
            onClick={toggleRamping}
            aria-label={ramping ? "Lebarkan sidebar" : "Sempitkan sidebar"}
            title={ramping ? "Lebarkan sidebar" : "Sempitkan sidebar"}
            className={`flex w-full items-center gap-3 rounded-[var(--radius-input)] px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-sunken ${
              ramping ? "justify-center px-2" : ""
            }`}
          >
            {ramping ? <PanelLeftOpen size={18} strokeWidth={1.8} />
                     : <PanelLeftClose size={18} strokeWidth={1.8} />}
            {!ramping && <span>Sempitkan</span>}
          </button>
        </div>

        <p className={`px-5 py-4 text-caption text-ink-subtle ${ramping ? "md:hidden" : ""}`}>
          v0.9.1 · Calm Ledger
        </p>
      </aside>
    </>
  );
}
