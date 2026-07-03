// Client API tipis. Token disimpan di memori + localStorage (sederhana untuk MVP;
// untuk produksi, pertimbangkan httpOnly cookie via route handler).
const BASE = "/api/v1";

function token(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("ananta_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) window.localStorage.setItem("ananta_token", t);
  else window.localStorage.removeItem("ananta_token");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
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
  setToken(data.access_token);
  return data;
}
