# Bot langkah 2 — Penautan multi-pengguna (kode sekali-pakai)

Sekarang eksekutif selain owner bisa menautkan akun Telegram mereka ke Ananta,
lewat kode sekali-pakai yang dibuat owner. Bot TIDAK membuat akun & TIDAK memberi
peran — ia hanya menghubungkan chat ke akun Ananta yang sudah ada. Peran tetap
diatur di Ananta (menu Pengaturan).

## File berubah / baru
- `backend/app/models/user.py` — tambah kolom `telegram_link_code`, `telegram_link_expires`
- `backend/app/bot/handlers.py` — perintah `/buat_kode` + `/link <kode>`
- `backend/migrations/telegram_step2_linkcode.sql` — kolom baru (jalankan di Supabase)

## Urutan deploy
1. Supabase -> SQL Editor -> jalankan `telegram_step2_linkcode.sql` (idempotent).
2. Extract zip ke root repo, lalu:
   ```powershell
   git add backend/
   git commit -m "bot langkah 2: penautan multi-pengguna via kode sekali-pakai"
   git push
   ```
3. Tonton Railway sampai "Healthcheck succeeded" & CI GitHub hijau.

## Cara pakai (alur lengkap)
Prasyarat: eksekutif harus sudah punya AKUN di Ananta dengan peran yang sesuai.

1. Owner buat akun eksekutif di web Ananta -> menu **Pengaturan** -> Tambah
   Pengguna (isi email, nama, password, PERAN). Lihat tabel pemetaan peran di bawah.
2. Owner (di Telegram, sudah tertaut) ketik:
   ```
   /buat_kode abay@anantaasf.com
   ```
   Bot membalas sebuah KODE (berlaku 24 jam).
3. Owner kirim kode itu ke orangnya (WhatsApp/chat).
4. Eksekutif buka bot, ketik:
   ```
   /link <kode>
   ```
   Bot membalas "Berhasil tertaut sebagai <email>."

Setelah tertaut, hak akses eksekutif otomatis mengikuti PERAN Ananta-nya
(mis. finance boleh input pengeluaran; viewer hanya baca).

## Catatan keamanan
- `/buat_kode` hanya bisa dijalankan owner.
- Kode acak, sekali-pakai, kedaluwarsa 24 jam; hangus otomatis setelah dipakai.
- Bot hanya menautkan ke akun yang SUDAH ada — tidak membuat akun / memberi peran.

## KEPUTUSAN OWNER: pemetaan peran (WAJIB diputuskan sebelum buat akun)
Peran Ananta: owner, finance, sales, warehouse, viewer.
Usulan pemetaan dari 5 peran C-level di spec (silakan owner sesuaikan):

  Eksekutif        Peran spec   Usulan peran Ananta   Bisa apa
  Owner            OWNER        owner                 semua
  Abay             CFO          finance               input pengeluaran/pembayaran, laporan keuangan
  Pei              CSO          sales                 hal terkait penjualan
  Silo             CEO          viewer                hanya baca (laporan/insight)
  Mik              CRD          viewer                hanya baca

Poin yang perlu owner putuskan: apakah Silo (CEO) & Mik (CRD) cukup "viewer"
(baca saja), atau perlu peran yang bisa menulis. Sesuaikan saat membuat akun.
