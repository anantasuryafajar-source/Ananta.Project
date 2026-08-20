# Bot langkah 11 — Insight terjadwal (Bagian 4, versi awal)

Scheduler mengirim SNAPSHOT HARIAN ke chat OWNER pukul 08:00 WIB. Aman untuk 2
worker lewat pengaman idempotensi (hanya 1 worker yang benar-benar mengirim).
Kiriman per-eksekutif menyusul saat akun mereka tertaut.

## PENTING: paket ini KUMULATIF
handlers.py di sini SUDAH termasuk /report & /omzet (langkah 10) + /insight_test.
Jadi cukup deploy paket ini (tidak perlu deploy langkah 10 terpisah).

## File berubah / baru
- app/bot/insights.py (BARU) — snapshot + scheduler aman 2-worker
- app/models/scheduler.py (BARU) — tabel idempotensi scheduler_runs
- app/models/__init__.py (patch) — ekspor model
- app/main.py (patch) — start/stop scheduler di lifespan (dibungkus try/except:
  gagal scheduler TIDAK menjatuhkan API)
- app/bot/handlers.py — /report, /omzet (langkah 10) + /insight_test (BARU)
- pyproject.toml (patch) — tambah apscheduler di [project] (BUKAN dev)
- migrations/scheduler.sql (BARU)

## Urutan deploy
1. Supabase -> SQL Editor -> jalankan migrations/scheduler.sql (idempotent).
2. Dari root repo:
   ```powershell
   git add backend/
   git commit -m "bot langkah 11: insight terjadwal (snapshot harian) + /report /omzet"
   git push
   ```
   Railway rebuild + pasang apscheduler otomatis.
3. Tonton Railway "Healthcheck succeeded" & CI hijau.

Prasyarat env (sudah ada dari langkah 1): TELEGRAM_BOT_TOKEN & TELEGRAM_OWNER_CHAT_ID
harus terisi — scheduler mengirim ke TELEGRAM_OWNER_CHAT_ID. Bila kosong,
scheduler nonaktif otomatis (API tetap jalan).

## Cara uji (pakai akun owner saja — tak perlu akun eksekutif)
- Uji INSTAN: kirim `/insight_test` ke bot. Bot langsung mengirim snapshot harian
  ke chat-mu. Ini membuktikan pipeline (data -> format -> kirim) jalan.
- Uji TERJADWAL: tunggu pukul 08:00 WIB; snapshot terkirim otomatis sekali.

Snapshot kini juga memuat PERINGATAN tagihan supplier jatuh tempo <=3 hari
(termasuk yang lewat tempo & belum lunas) — bagian brief harian Abay di spec.

Contoh snapshot:
  Snapshot Harian - 07 Jul 2026
  Kas masuk (24 jam) : Rp...
  Kas keluar (24 jam): Rp...
  Arus kas bersih    : Rp...
  Omzet bulan berjalan:
  - Lempar  : Rp...
  - Collect : Rp...
  Tagihan supplier jatuh tempo (<=3 hari):
  - 09 Jul BILL/2026/0007 PT Sumber Rp5.000.000

## Desain aman 2-worker (kenapa tak dobel)
Kedua worker menjalankan scheduler & sama-sama terpicu 08:00. Tapi tiap job
'mengklaim' baris UNIQUE(job, tanggal) di scheduler_runs; hanya satu commit yang
berhasil -> hanya satu worker yang mengirim. /insight_test sengaja TANPA klaim
(biar selalu bisa diuji kapan saja).

## Belum (langkah berikutnya)
- Kiriman per-eksekutif (Abay 08:00, Pei 21:00 leaderboard, Silo 07:00 snapshot,
  Mik Sabtu fast/slow-moving) — butuh akun eksekutif tertaut + rute per-peran.
- Deteksi anomali (+2sigma), churn hazard, proyeksi 30 hari — analitik lanjutan.
- Engine keuangan (Bagian 5) tetap terhalang persentase Dana Darurat/Bonus (ASF).

## Catatan jujur
Belum bisa diuji terhadap scheduler/DB sungguhan di lingkungan build (jaringan
mati). Dipastikan: compile, TOML valid + apscheduler di [project], SQL sinkron
model, registrasi & wiring benar, signature laporan cocok. Bukti akhir: deploy
lalu kirim /insight_test.
