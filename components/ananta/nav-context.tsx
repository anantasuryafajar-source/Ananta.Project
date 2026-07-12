"use client";
import { createContext, useContext, useState, type ReactNode } from "react";

/**
 * State drawer navigasi mobile — dibagikan antara tombol hamburger di Topbar
 * dan komponen Sidebar. Di desktop (md+) sidebar selalu tampil, state ini
 * hanya dipakai untuk layar sempit.
 */
type MobileNav = { open: boolean; setOpen: (v: boolean) => void };

const Ctx = createContext<MobileNav>({ open: false, setOpen: () => {} });

export function MobileNavProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <Ctx.Provider value={{ open, setOpen }}>{children}</Ctx.Provider>;
}

export const useMobileNav = () => useContext(Ctx);
