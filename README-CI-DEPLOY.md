# Pasang CI Test Otomatis (Fase 1 — Jaring Pengaman)

Paket ini menambah **satu file**: `.github/workflows/ci.yml`.
Tidak menyentuh kode aplikasi, tidak menyentuh database, tidak menyentuh produksi.
Aman 100% — cuma menambah pemeriksaan otomatis.

## Apa yang dilakukan

Setiap kali ada push ke `main` atau Pull Request yang menyentuh folder `backend/`,
GitHub akan otomatis menjalankan `pytest`. Fokus utamanya: **invarian jurnal
(debit = kredit)** yang sudah punya test di `backend/tests/`. Test pakai SQLite
in-memory, jadi cepat dan tidak butuh Postgres/Supabase.

Kalau ada perubahan yang bikin akuntansi tidak balance, kamu langsung dapat
tanda silang merah + email dari GitHub — sebelum masalahnya jadi angka salah di
buku perusahaan.

## Cara pasang (PowerShell, dari root repo)

Extract isi zip ini ke **root repo** (folder yang ada `.github`, `backend`, `app`, dst).
File akan mendarat di `.github/workflows/ci.yml`. Lalu:

```powershell
# pastikan kamu di root repo Ananta.Project
git add .github/workflows/ci.yml
git commit -m "ci: jalankan pytest otomatis untuk jaga invarian jurnal"
git push
```

## Cara memastikan berhasil

1. Buka GitHub → repo `Ananta.Project` → tab **Actions**.
2. Harus muncul workflow **"CI - Uji Backend (pytest)"** yang berjalan.
3. Tunggu sampai centang hijau. Kalau merah, klik untuk lihat test mana yang gagal.
4. Mau uji manual kapan saja: di tab Actions → pilih workflow itu → **Run workflow**.

Push ini **tidak memicu deploy** apa pun ke Railway/Vercel karena hanya menyentuh
`.github/` (backend & frontend tidak berubah). Jadi tidak ada risiko ke produksi.

## PENTING — apa yang CI ini lakukan & TIDAK lakukan

- ✅ **Lakukan:** memberi tahu kamu (silang merah + email) kalau ada test yang gagal.
- ❌ **Belum lakukan:** memblokir deploy Railway secara otomatis. Railway memantau
  branch `main` langsung, terpisah dari GitHub Actions. Jadi CI ini adalah *sinyal*,
  belum *gerbang*.

Untuk menjadikannya gerbang sungguhan (deploy ditolak kalau test merah), langkah
lanjutannya nanti:

1. Aktifkan **Branch protection** di GitHub untuk `main`: Settings → Branches →
   Add rule → centang "Require status checks to pass before merging" → pilih
   check **pytest**.
2. Mulai kerja lewat **Pull Request** ke `main`, bukan push langsung.
3. (Opsional) Di Railway, aktifkan "Wait for CI" bila tersedia di plan-mu.

Itu perubahan cara kerja (workflow culture), bukan sekadar file — jadi kita lakukan
terpisah setelah CI dasar ini terbukti hijau.

## Catatan

Test di CI **tidak** menyentuh database produksi sama sekali — semuanya SQLite
in-memory yang dibuat & dibuang di dalam runner GitHub. Connection string Supabase
tidak dipakai dan tidak perlu ada di sini.
