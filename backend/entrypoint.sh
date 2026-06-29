#!/usr/bin/env sh
set -e

PORT="${PORT:-8000}"

# Seed jalan di BACKGROUND supaya TIDAK memblokir start server.
# /health bisa langsung menjawab walau seed masih berjalan / DB lambat.
echo "[entrypoint] Menjalankan seed di background (non-blocking)..."
(
  python -m app.seed_asf \
    && echo "[entrypoint] Seed selesai." \
    || echo "[entrypoint] Seed gagal/dilewati — server tetap jalan, cek koneksi DB."
) &

echo "[entrypoint] Start server di port ${PORT}..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:"${PORT}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120
