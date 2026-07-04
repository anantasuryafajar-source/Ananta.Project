# Bot Telegram — Langkah 1: kerangka + tautan identitas + /tambah_produk

Paket ini menyatukan bot Telegram ke backend Ananta yang sudah ada (Opsi C).
Bot menulis ke database yang SAMA dengan web, lewat service tervalidasi.

## Apa yang berubah
File baru:
- `app/models/telegram.py` — tabel `telegram_links` & `telegram_sessions`
- `app/services/product_service.py` — service `create_product` (dipakai bersama)
- `app/bot/` — `application.py`, `handlers.py`, `state.py`
- `app/routers/telegram.py` — endpoint webhook
- `tests/test_product_service.py` — test (dijalankan CI)
- `migrations/telegram_step1.sql` — SQL pembuatan tabel

File diubah (aman, hanya penambahan):
- `app/main.py` — mount webhook + start/stop bot di lifespan (dibungkus try/except:
  kegagalan bot TIDAK membuat API crash)
- `app/core/config.py` — env var Telegram
- `app/models/__init__.py` — ekspor model baru
- `pyproject.toml` — tambah `python-telegram-bot` di `[project]` (BUKAN dev group)

## Prasyarat yang harus KAMU siapkan
1. Token bot dari **BotFather**: buka Telegram, chat @BotFather, kirim `/newbot`,
   ikuti langkahnya, salin token (bentuk `123456:ABC-...`).
2. Webhook secret: string acak bebas. Di PowerShell bisa:
   ```powershell
   [guid]::NewGuid().ToString('N')
   ```
3. URL publik backend Railway, mis. `https://ananta-api-production-e77c.up.railway.app`.

## Urutan deploy (WAJIB berurutan)

### 1) Buat tabel dulu di Supabase (Jebakan 2)
Supabase project utama -> **SQL Editor** -> tempel isi
`backend/migrations/telegram_step1.sql` -> Run. (Idempotent, aman diulang.)

### 2) Set environment variables di Railway (service ananta-api)
- `TELEGRAM_BOT_TOKEN` = token dari BotFather
- `TELEGRAM_WEBHOOK_SECRET` = string acak dari langkah prasyarat
- `BACKEND_PUBLIC_URL` = URL publik backend (tanpa garis miring di akhir)
- `TELEGRAM_OWNER_CHAT_ID` = KOSONGKAN DULU (diisi setelah tahu chat id, lihat bawah)

### 3) Deploy kode (PowerShell, dari root repo)
Extract zip ini ke root repo, lalu:
```powershell
git add backend/
git commit -m "bot telegram langkah 1: kerangka, tautan identitas, /tambah_produk"
git push
```
Tonton Railway -> Deployments sampai **"Healthcheck succeeded"**. GitHub Actions
juga akan menjalankan pytest (ada test baru `test_product_service`) — pastikan hijau.

## Cara menautkan akun owner (bootstrap)
Karena penautan multi-pengguna dibangun di langkah berikutnya, untuk sekarang
owner ditaut lewat chat id:

1. Buka bot kamu di Telegram (cari nama bot yang dibuat di BotFather), kirim `/start`.
2. Kirim `/link`. Bot akan membalas **"Chat ID kamu: <angka>"**.
3. Salin angka itu ke Railway -> env `TELEGRAM_OWNER_CHAT_ID` -> simpan
   (Railway otomatis restart).
4. Setelah restart, kirim `/link` lagi. Bot membalas
   **"Berhasil tertaut sebagai <email owner> (owner)."**

## Uji /tambah_produk
Kirim `/tambah_produk`, lalu ikuti pertanyaan bot: SKU -> Nama -> Satuan -> Harga.
Ketik `YA` di konfirmasi. Bot menjawab "Tersimpan: ...".
Verifikasi: buka **web Ananta -> menu Produk**, cari produk itu di kotak search.
Kalau muncul, berarti alur Telegram -> database -> web sudah tersambung penuh.

Ketik `/batal` kapan saja untuk membatalkan input yang sedang berjalan.

## Catatan teknis
- **Aman untuk 2 worker.** State percakapan disimpan di tabel `telegram_sessions`
  (bukan memori), jadi tidak masalah gunicorn jalan >1 worker.
- **Bot bersifat opsional.** Bila `TELEGRAM_BOT_TOKEN` kosong atau paket belum
  terpasang, bot mati dan API akuntansi tetap berjalan normal.
- **RBAC & audit ikut sistem lama.** Aksi bot dikaitkan ke user Ananta yang tertaut;
  `/tambah_produk` butuh peran owner/warehouse/finance/sales (owner selalu lolos).
- **Keamanan webhook.** Telegram mengirim header rahasia yang diverifikasi backend;
  request tanpa secret yang benar ditolak (403).

## Yang BELUM di langkah ini (berikutnya)
- Penautan multi-pengguna via kode sekali-pakai (untuk Abay/Pei/Silo/Mik).
- `/tambah_pengeluaran` (memakai ulang `create_expense`, jurnal sederhana).
- Perintah baca: `/report`, `/omzet`, insight terjadwal.
