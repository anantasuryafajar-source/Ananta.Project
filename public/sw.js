/* Ananta PWA — service worker minimal & aman.
 *
 * Prinsip:
 * - JANGAN pernah cache /api/* (data keuangan harus selalu segar dari jaringan).
 * - Aset statis (_next/static, ikon, font) di-cache (cache-first) untuk buka cepat.
 * - Navigasi (HTML) network-first; kalau offline tampilkan halaman /offline.
 *
 * Naikkan versi CACHE saat ada perubahan agar cache lama dibuang.
 */
const CACHE = "ananta-v1";
const OFFLINE_URL = "/offline";
const PRECACHE = [OFFLINE_URL, "/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Lewati lintas-origin & SEMUA panggilan API — selalu jaringan, tanpa cache.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  // Navigasi halaman: network-first, fallback ke halaman offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Aset statis: cache-first, isi cache saat pertama diambil.
  const isStatic =
    url.pathname.startsWith("/_next/static/") ||
    /\.(?:png|svg|ico|webmanifest|woff2?|ttf)$/.test(url.pathname);

  if (isStatic) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
            return res;
          })
      )
    );
  }
});
