-- Migrasi insight terjadwal (penjaga idempotensi scheduler).
-- Jalankan di Supabase -> SQL Editor. Idempotent.

CREATE TABLE IF NOT EXISTS scheduler_runs (
  id         VARCHAR(36) PRIMARY KEY,
  job        VARCHAR(60) NOT NULL,
  run_key    VARCHAR(40) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_scheduler_job_key UNIQUE (job, run_key)
);
CREATE INDEX IF NOT EXISTS ix_scheduler_runs_job ON scheduler_runs(job);
