# Ananta — Sistem Manajemen Bisnis & Akuntansi

Monorepo: **Next.js 16 (web)** + **FastAPI (api)** + **PostgreSQL 17** + **Redis**.
Design system "Calm Ledger". UI & istilah dalam Bahasa Indonesia.

> Status: **fondasi (Fase 0) + inti mesin transaksi**. Lihat `STATUS.md` untuk
> rincian apa yang sudah jalan vs yang masih scaffold.

## Struktur

```
ananta/
├─ apps/api/    FastAPI · SQLAlchemy 2 async · Pydantic v2 · Alembic
├─ apps/web/    Next.js 16 · React 19 · Tailwind v4 · TanStack
├─ packages/types/  Tipe TS hasil OpenAPI
└─ docker-compose.yml
```

## Prasyarat
- Node.js 22 LTS, Python 3.12+, dan Docker (untuk Postgres + Redis).
- `uv` untuk dependency Python: `pip install uv`.

## Jalankan cepat (dev)

1) **Infra (Postgres + Redis):**
```bash
cp .env.example .env
docker compose up -d db redis
```

2) **Backend:**
```bash
cd apps/api
cp .env.example .env        # samakan kredensial dengan root .env
uv venv && source .venv/bin/activate
uv pip install -r pyproject.toml --group dev
python -m app.seed          # buat tabel + CoA Indonesia + admin
uvicorn app.main:app --reload
```
API di http://localhost:8000 · dokumentasi OpenAPI di `/docs`.
Login awal: `admin@ananta.local` / `admin12345`.

3) **Frontend:**
```bash
cd apps/web
npm install
npm run dev
```
Web di http://localhost:3000 (proxy `/api/*` ke FastAPI).

## Migrasi (Alembic)
Untuk dev cepat, `python -m app.seed` sudah `create_all`. Untuk produksi:
```bash
cd apps/api
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

## Test (logika akuntansi)
```bash
cd apps/api
pytest          # uji jurnal balance & posting faktur (pakai SQLite in-memory)
```

## Generate tipe TS dari OpenAPI
```bash
npm run gen:types   # butuh API hidup di :8000
```

## Catatan keamanan
- RBAC dicek di backend (`app/deps.py::require_roles`), bukan hanya UI.
- Password di-hash Argon2; JWT access pendek + refresh.
- Semua nilai uang `Numeric(18,2)` (Decimal), bukan float.
- Setiap transaksi keuangan lewat `services/journal.py` yang menjamin debit=kredit.
