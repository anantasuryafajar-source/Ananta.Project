#!/usr/bin/env sh
set -e

echo "[entrypoint] Menyiapkan database (seed idempoten)..."
python -m app.seed_asf || echo "[entrypoint] Seed dilewati (data sudah ada / non-fatal)."

echo "[entrypoint] Menjalankan server di port ${PORT:-8000}..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:${PORT:-8000} \
  --workers ${WEB_CONCURRENCY:-2} \
  --timeout 120
