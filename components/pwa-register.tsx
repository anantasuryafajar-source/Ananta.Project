"use client";
import { useEffect } from "react";

/**
 * Mendaftarkan service worker (/sw.js) sekali di sisi klien setelah halaman siap.
 * Tanpa UI — cukup dipasang di root layout.
 */
export function PWARegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;

    const onLoad = () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        /* diamkan — PWA opsional, app tetap jalan tanpanya */
      });
    };

    if (document.readyState === "complete") onLoad();
    else window.addEventListener("load", onLoad);
    return () => window.removeEventListener("load", onLoad);
  }, []);

  return null;
}
