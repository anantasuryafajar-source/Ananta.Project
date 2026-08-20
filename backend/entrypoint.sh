#!/usr/bin/env sh
set -e

PORT="${PORT:-8000}"

# Migrasi + seed jalan di BACKGROUND supaya TIDAK memblokir start server.
# /health bisa langsung menjawab walau migrasi masih berjalan / DB lambat.
#
# Skema dikelola Alembic (bukan lagi create_all di dalam seed), jadi menambah
# model baru cukup dengan revisi Alembic — tidak perlu SQL manual lagi.
# Seed hanya mengisi data awal dan tetap dilewati bila company sudah ada.
echo "[entrypoint] Menjalankan migrasi + seed di background (non-blocking)..."
(
  if alembic upgrade head; then
    echo "[entrypoint] Migrasi selesai."
    python -m app.seed_asf \
      && echo "[entrypoint] Seed selesai." \
      || echo "[entrypoint] Seed gagal/dilewati — server tetap jalan, cek koneksi DB."
  else
    echo "[entrypoint] MIGRASI GAGAL — seed dilewati. Server tetap jalan; cek DATABASE_URL."
  fi
) &

echo "[entrypoint] Start server di port ${PORT}..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:"${PORT}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120
