"use client";
import { Search } from "lucide-react";

export function Topbar({ title }: { title: string }) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-line bg-surface px-6">
      <h1 className="text-h3 font-semibold text-ink">{title}</h1>
      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-1.5 text-ink-subtle md:flex">
          <Search size={15} />
          <span className="text-caption">Cari… (Ctrl+K)</span>
        </div>
        <div className="grid h-8 w-8 place-items-center rounded-full bg-primary-soft text-sm font-medium text-primary">
          A
        </div>
      </div>
    </header>
  );
}
