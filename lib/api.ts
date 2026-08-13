// Client API tipis. Token disimpan di memori + localStorage (sederhana untuk MVP;
// untuk produksi, pertimbangkan httpOnly cookie via route handler).
//
// Sesi: access token berumur pendek (ACCESS_TOKEN_MINUTES, default 30 menit).
// Dulu refresh token dibuat backend tapi TIDAK dipakai di sini, sehingga sesi mati
// tanpa penjelasan di tengah pekerjaan — sales di lapangan tiba-tiba diminta login
// lagi. Sekarang setiap 401 memicu satu kali refresh lalu request diulang; kalau
// refresh juga gagal, token dibuang dan user diarahkan ke halaman login.
const BASE = "/api/v1";

const AKSES = "ananta_token";
const REFRESH = "ananta_refresh";

function token(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AKSES);
}

function refreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH);
}

/** Simpan/hapus token. `null` = keluar (kedua token dibuang). */
export function setToken(t: string | null, r?: string | null) {
  if (typeof window === "undefined") return;
  if (t) {
    window.localStorage.setItem(AKSES, t);
    if (r) window.localStorage.setItem(REFRESH, r);
  } else {
    window.localStorage.removeItem(AKSES);
    window.localStorage.removeItem(REFRESH);
  }
}

/** Satu proses refresh dipakai bersama semua request yang kena 401 berbarengan,
 *  supaya 6 request paralel tidak memicu 6 refresh (dan saling membatalkan). */
let sedangRefresh: Promise<boolean> | null = null;

async function segarkanSesi(): Promise<boolean> {
  const r = refreshToken();
  if (!r) return false;
  if (sedangRefresh) return sedangRefresh;

  sedangRefresh = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: r }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      setToken(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      sedangRefresh = null;
    }
  })();

  return sedangRefresh;
}

function keLogin() {
  if (typeof window === "undefined") return;
  setToken(null);
  // Jangan looping bila sudah di halaman login.
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

async function kirim(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  return fetch(`${BASE}${path}`, { ...init, headers });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await kirim(path, init);

  // Sesi kedaluwarsa: coba refresh SEKALI, lalu ulangi request yang sama.
  if (res.status === 401 && !path.startsWith("/auth/")) {
    if (await segarkanSesi()) {
      res = await kirim(path, init);
    }
    if (res.status === 401) {
      keLogin();
      throw new Error("Sesi berakhir. Silakan masuk lagi.");
    }
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Gagal memuat (${res.status})`);
  }
  // 204 No Content atau body kosong (mis. DELETE) -> tidak ada JSON untuk di-parse
  if (res.status === 204) return null as T;
  const text = await res.text();
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

export async function login(email: string, password: string) {
  const form = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) throw new Error("Email atau kata sandi salah.");
  const data = await res.json();
  setToken(data.access_token, data.refresh_token);
  return data;
}
