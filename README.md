# Ananta — Sistem Manajemen Bisnis & Akuntansi

Struktur disederhanakan untuk **deploy Vercel tanpa konfigurasi**:
- **Root repo = frontend Next.js** → Vercel auto-deploy.
- **`backend/`** = FastAPI + PostgreSQL + Redis (dideploy terpisah, mis. Railway/Render).

## Deploy frontend ke Vercel (otomatis)
1. Import repo ini ke Vercel.
2. Root Directory biarkan `./` (default) — **tidak perlu diubah**.
3. Klik **Deploy**. Selesai.

Halaman utama (`/`) menampilkan landing Ananta; `/login` halaman masuk;
`/dashboard`, `/kontak`, `/produk` halaman aplikasi.

> Catatan: tombol "Masuk" baru berfungsi penuh setelah backend di-deploy dan
> environment variable `API_BASE` diisi (URL backend) di Vercel → Settings →
> Environment Variables. Tanpa itu, halaman tetap tampil normal, hanya proses
> login yang belum jalan.

## Jalankan lokal (lengkap)

**Frontend:**
```bash
npm install
npm run dev          # http://localhost:3000
```

**Backend (folder backend/):**
```bash
cp .env.example .env
docker compose up -d db redis
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows
pip install uv
uv pip install -r pyproject.toml --group dev
python -m app.seed_asf   # buat tabel + CoA ASF + 18 produk + 54 customer + admin
uvicorn app.main:app --reload   # http://localhost:8000  · /docs
```
Login awal: `admin@ananta.local` / `admin12345`.
Saat dev, set `API_BASE=http://localhost:8000` di `.env` frontend (opsional)
agar `/api/*` diproksikan ke backend.

## Deploy backend (ringkas)
Vercel tidak bisa menjalankan Postgres/Redis/FastAPI. Pakai **Railway** atau
**Render**: buat service dari folder `backend/`, tambah Postgres + Redis, set
`DATABASE_URL` & `REDIS_URL`, jalankan `python -m app.seed` sekali, lalu start
`gunicorn app.main:app -k uvicorn.workers.UvicornWorker`. Setelah hidup, isi
`API_BASE` di Vercel dengan URL backend tsb.

Lihat `STATUS.md` untuk rincian fitur yang sudah jalan vs masih scaffold.
