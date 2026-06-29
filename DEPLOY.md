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
4. Setelah service hidup, jalankan seed SEKALI (Railway: tab Shell / one-off command):
   ```
   python -m app.seed_asf
   ```
   Ini membuat tabel + CoA ASF + 18 produk + 54 customer + user admin.
5. Catat URL publik backend, mis. `https://ananta-api.up.railway.app`.
   Cek `GET /health` -> harus `{"status":"ok"}`. Dok API di `/docs`.

## 3. Frontend di Vercel
1. Import repo. Root Directory biarkan `./` (default).
2. Environment Variable: `API_BASE = https://<url-backend>` (dari langkah 2.5).
3. Deploy. Login pakai SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD yang kamu set.

## Checklist kalau login gagal
- `API_BASE` di Vercel sudah benar & sudah redeploy?
- `CORS_ORIGINS` di backend memuat domain Vercel persis (termasuk https)?
- Seed `python -m app.seed_asf` sudah dijalankan di backend?
- Project Supabase tidak ter-pause (free tier pause setelah idle ~7 hari)?
- Salah port? Session pooler = 5432. Jangan campur dengan 6543.
