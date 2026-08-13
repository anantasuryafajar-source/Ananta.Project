# Deploy Ananta (Supabase + Railway/Render + Vercel)

Arsitektur: **Vercel** (frontend) + **Railway/Render** (backend FastAPI) + **Supabase** (database Postgres).
Supabase HANYA database — FastAPI tetap perlu di-host terpisah. Redis tidak diperlukan.

## 1. Supabase (database)
1. Buat project di supabase.com. Catat password database.
2. Klik **Connect** di dashboard -> tab **Session pooler**.
3. Salin connection string (port **5432**, host `aws-<region>.pooler.supabase.com`,
   user `postgres.<project-ref>`). Pakai session pooler karena IPv4-friendly &
   dukung prepared statement.
   - Skala besar nanti boleh ganti ke Transaction pooler (port 6543); kode sudah
     otomatis menyesuaikan.
4. Tidak perlu bikin tabel manual — seed yang akan membuatnya.

## 2. Backend di Railway (atau Render)
1. New Project -> Deploy from GitHub -> pilih repo, set **Root Directory = `backend`**.
2. Environment variables:
   ```
   DATABASE_URL = <session pooler string dari Supabase>   (boleh apa adanya)
   JWT_SECRET   = <acak panjang, min 32 karakter>
   ENV          = production
   CORS_ORIGINS = ["https://<nama-app>.vercel.app"]
   SEED_ADMIN_EMAIL    = <email kamu>
   SEED_ADMIN_PASSWORD = <password kuat>     # JANGAN default
   ```
3. Start command:
   ```
   gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT
   ```
4. Tabel dibuat otomatis: `entrypoint.sh` menjalankan `alembic upgrade head` lalu
   `python -m app.seed_asf` saat boot. Tidak perlu perintah manual untuk deploy baru.
   Seed mengisi CoA ASF + 23 produk + 54 customer + user admin, dan dilewati bila
   company sudah ada.
5. Catat URL publik backend, mis. `https://ananta-api.up.railway.app`.
   Cek `GET /health` -> harus `{"status":"ok"}`. Dok API di `/docs`.

## 3. Frontend di Vercel
1. Import repo. Root Directory biarkan `./` (default).
2. Environment Variable: `API_BASE = https://<url-backend>` (dari langkah 2.5).
3. Deploy. Login pakai SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD yang kamu set.

## 4. Migrasi skema (setelah deploy pertama)

Skema dikelola Alembic. Setiap deploy menjalankan `alembic upgrade head` sendiri,
jadi perubahan model yang **punya revisi** akan ikut terpasang otomatis.

Menambah/mengubah model WAJIB disertai revisi:
```bash
cd backend
alembic revision --autogenerate -m "tambah kolom X"   # cek hasilnya sebelum commit
```
Tanpa revisi, tabel/kolom baru TIDAK akan muncul di database yang sudah terisi.

## 5. Upgrade database yang SUDAH TERISI (tanpa kehilangan akun & riwayat)

Ini jalur normal — **tidak perlu reset**. Akun pengguna, role, tautan Telegram,
riwayat chat AI, faktur, dan jurnal semuanya tetap utuh.

Revisi `0002_satuan_dus_botol` khusus mengejar ketertinggalan database yang lahir
sebelum Alembic dipakai: ia menambahkan kolom satuan ke tabel yang sudah ada dan
melebarkan presisi `avg_cost`. Semua operasinya dijaga (idempoten), jadi aman juga
di database baru yang kolomnya sudah lengkap.

**Langkah:**

1. Backup dulu — cara termudah: GitHub → **Actions** → "Backup Database Harian" →
   **Run workflow**. Manual dari komputer:
   ```bash
   pg_dump "$DATABASE_URL" -Fc -f sebelum-upgrade.dump   # butuh pg_dump v17
   ```
2. Deploy kode baru. `entrypoint.sh` otomatis menjalankan `alembic upgrade head`,
   jadi kolom satuan langsung terbentuk saat boot. Kalau mau menjalankan manual
   (Railway → tab Shell):
   ```bash
   cd backend && alembic upgrade head
   ```
3. Selaraskan master produk dengan daftar resmi client (23 produk). Lihat rencananya
   dulu, baru terapkan:
   ```bash
   python -m app.master_asf              # dry-run, hanya menampilkan rencana
   python -m app.master_asf --terapkan   # simpan
   ```
   Skrip ini mengganti nama produk yang berubah, memperbaiki isi/dus & modal per dus,
   dan menambah produk baru. **Tidak menghapus produk apa pun** dan tidak menyentuh
   stok maupun jurnal. Aman dijalankan berulang.
4. Cek `GET /health` -> `{"status":"ok"}`, lalu login dan buka menu Produk: harus ada
   23 produk dengan kolom **Isi/Dus** dan **Modal / Dus** terisi.
5. Isi stok awal (lihat bagian 6) sebelum client mulai membuat faktur.

Apa yang terjadi pada data lama:
- `products.purchase_price` lama dianggap **modal per DUS** (memang begitu isinya di
  seed lama) -> dipindah ke `pack_purchase_price`, lalu modal per botol dihitung ulang.
- Isi per dus diisi 12, kecuali Robinson Vodka (48). Nilai final diperbaiki langkah 3.
- Baris transaksi lama dianggap satuan **botol** dengan faktor 1, sehingga angka stok
  dan HPP historis tidak bergeser sama sekali. Riwayatnya tampil sebagai "n botol".
- SKU lama tidak diubah (SKU pendek seperti `B`/`RBV` lebih enak diketik di bot).

### Reset TOTAL — hanya bila memang ingin membuang semuanya

⚠️ Menghapus SEMUA data termasuk akun pengguna. Password tidak bisa dipulihkan
(hash Argon2), dan tautan bot Telegram harus dibuat ulang. Pakai hanya kalau isi
database benar-benar tidak diperlukan.

```bash
pg_dump "$DATABASE_URL" -Fc -f sebelum-reset.dump
cd backend
alembic downgrade base && alembic upgrade head && python -m app.seed_asf
```

Kalau `downgrade base` gagal karena dependensi, jalankan sekali lagi, atau drop
schema langsung:
`psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'`
lalu ulangi `upgrade head` + seed.

## 6. Stok awal — jangan dilewati

Setelah reset, `avg_cost` semua produk NOL. Artinya penjualan pertama tercatat
dengan **HPP nol**, laba terlihat 100%, dan laporan GPM jadi tidak berarti.

Cara yang disarankan: **catat stok fisik yang ada sekarang sebagai Pengadaan**
(menu Pembelian) — per dus, dengan modal riil. Ini sekaligus membuat `avg_cost`
benar dan jejak auditnya rapi. Lakukan sebelum input penjualan pertama.

## Checklist kalau login gagal
- `API_BASE` di Vercel sudah benar & sudah redeploy?
- `CORS_ORIGINS` di backend memuat domain Vercel persis (termasuk https)?
- Seed `python -m app.seed_asf` sudah dijalankan di backend?
- Project Supabase tidak ter-pause (free tier pause setelah idle ~7 hari)?
- Salah port? Session pooler = 5432. Jangan campur dengan 6543.
