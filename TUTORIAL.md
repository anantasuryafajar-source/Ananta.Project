# Tutorial Deploy Ananta — dari Nol sampai Online

Sistem ini punya **3 bagian** yang di-deploy ke 3 tempat berbeda:

| Bagian | Teknologi | Di-host di | Fungsi |
|---|---|---|---|
| Frontend | Next.js | **Vercel** | Tampilan web yang dibuka user |
| Backend | FastAPI | **Railway** atau **Render** | Otak akuntansi (jurnal, laporan) |
| Database | PostgreSQL | **Supabase** | Tempat semua data disimpan |

> Supabase **hanya** database. Backend FastAPI tetap perlu host sendiri. Redis tidak dipakai.

Estimasi waktu: ~20 menit. Tidak perlu coding — hanya klik & tempel.

---

## Persiapan (sekali saja)

Buat akun gratis di: **github.com**, **supabase.com**, **railway.app** (atau **render.com**), **vercel.com**.

### Push kode ke GitHub
Kalau repo sudah ada di GitHub, lewati. Kalau belum:
```bash
git add -A
git commit -m "chore: siap deploy (Supabase + Railway + Vercel)"
git push origin main
```

> ⚠️ **Keamanan:** kalau token GitHub kamu pernah ikut ter-commit di URL remote, **revoke** dulu di GitHub → Settings → Developer settings → Personal access tokens, lalu:
> ```bash
> git remote set-url origin https://github.com/<user>/<repo>.git
> ```

---

## Langkah 1 — Database di Supabase

1. Masuk supabase.com → **New project**. Isi nama, **password database** (catat baik-baik), pilih region terdekat (mis. Southeast Asia / Singapore), **Create**.
2. Tunggu project aktif (~2 menit).
3. Klik tombol **Connect** di atas → tab **Session pooler**.
4. Salin connection string-nya. Bentuknya:
   ```
   postgresql://postgres.<project-ref>:<password>@aws-<region>.pooler.supabase.com:5432/postgres
   ```
   - Ganti `<password>` dengan password yang kamu buat di langkah 1.
   - **Pakai Session pooler (port 5432)**, bukan Direct (IPv6) atau Transaction (6543). Ini paling kompatibel dengan Railway/Render.
5. Simpan string ini — dipakai di Langkah 2.

> Tidak perlu bikin tabel manual. Tabel + data awal (CoA ASF, 18 produk, 54 customer, user admin) dibuat **otomatis** saat backend pertama kali start.

---

## Langkah 2 — Backend di Railway (rekomendasi)

1. railway.app → **New Project** → **Deploy from GitHub repo** → pilih repo Ananta.
2. Setelah service dibuat, buka **Settings** service:
   - **Root Directory** → isi `backend`
   - Railway akan otomatis pakai `Dockerfile` & `railway.json` yang sudah ada.
3. Buka tab **Variables**, tambahkan (klik **Raw Editor**, tempel ini, sesuaikan):
   ```
   DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-<region>.pooler.supabase.com:5432/postgres
   JWT_SECRET=<ketik-acak-panjang-min-32-karakter>
   ENV=production
   CORS_ORIGINS=["https://<nama-app>.vercel.app"]
   SEED_ADMIN_EMAIL=admin@ananta.co
   SEED_ADMIN_PASSWORD=<password-kuat-pilihanmu>
   ```
   - `CORS_ORIGINS` boleh diisi belakangan setelah tahu domain Vercel (Langkah 3). Untuk sementara boleh `["http://localhost:3000"]`.
   - `SEED_ADMIN_EMAIL` & `SEED_ADMIN_PASSWORD` = **akun login pertamamu**. Jangan pakai default.
4. Railway akan build & deploy. Tunggu sampai status **Active**.
5. Buka tab **Settings → Networking → Generate Domain** untuk dapat URL publik, mis:
   ```
   https://ananta-api-production.up.railway.app
   ```
6. Cek sehat: buka `https://<url-backend>/health` → harus muncul `{"status":"ok"}`.
   Dokumentasi API otomatis ada di `https://<url-backend>/docs`.

> **Seed jalan otomatis.** Saat container start, `entrypoint.sh` menjalankan `python -m app.seed_asf` (idempoten — kalau data sudah ada, dilewati). Jadi user admin langsung dibuat tanpa langkah manual.

### Alternatif: Render
Repo sudah punya `render.yaml`. Di render.com → **New → Blueprint** → pilih repo → Render baca `render.yaml` otomatis. Isi variable yang `sync:false` (DATABASE_URL, CORS_ORIGINS, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD) di dashboard. `JWT_SECRET` di-generate otomatis.

---

## Langkah 3 — Frontend di Vercel

1. vercel.com → **Add New → Project** → import repo Ananta.
2. **Root Directory** biarkan default (`./`). Framework otomatis terdeteksi Next.js.
3. Buka **Settings → Environment Variables**, tambah:
   ```
   API_BASE = https://<url-backend-dari-langkah-2>
   ```
   (tanpa garis miring di akhir)
4. **Deploy**. Setelah selesai, catat domain Vercel-nya, mis. `https://ananta.vercel.app`.
5. **Balik ke Railway/Render**, update `CORS_ORIGINS` jadi domain Vercel tadi:
   ```
   CORS_ORIGINS=["https://ananta.vercel.app"]
   ```
   lalu redeploy backend (Railway redeploy otomatis saat variable berubah).

---

## Langkah 4 — Login pertama

1. Buka `https://<domain-vercel>/login`.
2. Masuk dengan **SEED_ADMIN_EMAIL** & **SEED_ADMIN_PASSWORD** yang kamu set di Langkah 2.
3. Selesai — dashboard, penjualan, pembelian, produk, dan laporan sudah aktif.

> Mulai isi data: catat **Pembelian** dulu (supaya stok & average cost terbentuk), baru **Penjualan** (HPP otomatis benar). Laporan Laba Rugi, AR Aging, dan Valuasi Stok langsung terisi dari jurnal.

---

## Kalau login gagal — cek ini

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| Halaman login muncul tapi "Email/sandi salah" terus | Backend belum konek / seed belum jalan | Cek `/health` backend hidup; lihat log apakah seed sukses |
| Error jaringan / 502 saat login | `API_BASE` salah / belum diset di Vercel | Pastikan `API_BASE` = URL backend persis, lalu **redeploy** Vercel |
| Diblokir CORS di console browser | `CORS_ORIGINS` tidak memuat domain Vercel | Set `CORS_ORIGINS=["https://<domain>.vercel.app"]`, redeploy backend |
| Backend gagal start, error prepared statement | Pakai port 6543 tanpa setelan | Kode sudah menangani; pastikan pakai **port 5432** (session pooler) |
| Tiba-tiba mati setelah beberapa hari | Supabase free tier **pause** saat idle ±7 hari | Buka dashboard Supabase → **Resume project** |
| Error `sslmode`/`pgbouncer` | Query nyangkut di URL | Tidak masalah — kode otomatis membuangnya |

---

## Ganti password / tambah user

Endpoint ganti-password via UI belum dibangun. Sementara:
- **Paling mudah:** set `SEED_ADMIN_PASSWORD` ke nilai baru, hapus baris data company di Supabase (Table Editor → `companies`) **sekali**, lalu restart backend agar seed ulang. (Hanya untuk fase awal sebelum ada data penting.)
- **Untuk produksi nyata:** minta saya tambahkan endpoint `POST /auth/change-password` + halaman Pengaturan. Tinggal bilang.

---

## Jalankan di komputer (opsional, untuk ngoprek)

**Backend:**
```bash
cd backend
cp ../.env.example .env        # isi DATABASE_URL Supabase
pip install uv && uv pip install -r pyproject.toml --group dev
python -m app.seed_asf
uvicorn app.main:app --reload  # http://localhost:8000/docs
```
**Frontend:**
```bash
npm install
echo "API_BASE=http://localhost:8000" > .env.local
npm run dev                    # http://localhost:3000
```

---

## Ringkasan variable (contekan)

**Backend (Railway/Render):**
```
DATABASE_URL         = <session pooler Supabase, port 5432>
JWT_SECRET           = <acak panjang>
ENV                  = production
CORS_ORIGINS         = ["https://<app>.vercel.app"]
SEED_ADMIN_EMAIL     = <email login>
SEED_ADMIN_PASSWORD  = <password login>
```
**Frontend (Vercel):**
```
API_BASE = https://<url-backend>
```
