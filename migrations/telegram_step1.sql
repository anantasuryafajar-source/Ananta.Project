-- Migrasi langkah 1 bot Telegram.
-- Jalankan di Supabase -> SQL Editor (cara paling pasti; lihat "Jebakan 2").
-- Idempotent: aman dijalankan berulang.

CREATE TABLE IF NOT EXISTS telegram_links (
  id               VARCHAR(36) PRIMARY KEY,
  telegram_chat_id BIGINT      NOT NULL UNIQUE,
  user_id          VARCHAR(36) NOT NULL REFERENCES users(id),
  is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_telegram_links_user_id ON telegram_links(user_id);

CREATE TABLE IF NOT EXISTS telegram_sessions (
  id               VARCHAR(36) PRIMARY KEY,
  telegram_chat_id BIGINT      NOT NULL UNIQUE,
  flow             VARCHAR(40),
  step             VARCHAR(40),
  draft            TEXT,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
