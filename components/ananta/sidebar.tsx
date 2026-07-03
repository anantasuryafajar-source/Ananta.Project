"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/nav";
import { ContinuityRibbon } from "./continuity-ribbon";

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-line bg-surface">
      <div className="px-5 py-5">
        <p className="font-display text-xl font-bold tracking-tight text-ink">
          Ananta
        </p>
        <ContinuityRibbon className="mt-1 opacity-80" />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
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
      </nav>
      <p className="px-5 py-4 text-caption text-ink-subtle">v0.8.2 · Calm Ledger</p>
    </aside>
  );
}
