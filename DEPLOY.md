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

## 5. Reset TOTAL database (hanya bila datanya memang boleh dibuang)

⚠️ **Menghapus SEMUA data termasuk master.** Dipakai saat pindah dari data dummy ke
data asli. Kalau sudah ada transaksi riil, jangan — buat revisi Alembic biasa.

Kenapa reset dan bukan sekadar `upgrade head`: revisi baseline membuat tabel dengan
`create_all(checkfirst=True)`, yang hanya membuat tabel yang **belum ada** dan tidak
menambah kolom ke tabel lama. Pada database yang skemanya dibuat cara lama (sebelum
Alembic), `upgrade head` akan sukses tapi kolom baru tidak terbentuk — lalu API error.

**Langkah (jalankan dari Railway → tab Shell, atau lokal dengan `DATABASE_URL`
produksi):**

1. Backup dulu, walau datanya dummy:
   ```bash
   pg_dump "$DATABASE_URL" -Fc -f sebelum-reset.dump
   ```
2. Reset + migrasi + seed:
   ```bash
   cd backend
   alembic downgrade base    # DROP semua tabel
   alembic upgrade head      # buat ulang dari model
   python -m app.seed_asf    # CoA + 23 produk + 54 customer + admin
   ```
3. Cek `GET /health` -> `{"status":"ok"}`, lalu login dan buka menu Produk:
   harus ada 23 produk dengan kolom **Isi/Dus** dan **Modal / Dus** terisi.
4. Isi stok awal (lihat bagian 6) sebelum client mulai membuat faktur.

Kalau `downgrade base` gagal karena ada dependensi, jalankan `alembic downgrade
base` sekali lagi, atau drop schema langsung:
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
