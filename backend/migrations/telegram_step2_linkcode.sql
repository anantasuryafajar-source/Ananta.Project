-- Migrasi langkah 2 bot Telegram: kode tautan multi-pengguna.
-- Jalankan di Supabase -> SQL Editor. Idempotent (aman diulang).

ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_link_code    VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_link_expires TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_users_telegram_link_code ON users (telegram_link_code);
