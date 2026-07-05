-- Migrasi Asisten AI web (riwayat percakapan).
-- Jalankan di Supabase -> SQL Editor. Idempotent.

CREATE TABLE IF NOT EXISTS ai_conversations (
  id         VARCHAR(36) PRIMARY KEY,
  company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
  user_id    VARCHAR(36) NOT NULL REFERENCES users(id),
  title      VARCHAR(160) NOT NULL DEFAULT 'Percakapan baru',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_user ON ai_conversations(user_id);

CREATE TABLE IF NOT EXISTS ai_messages (
  id              VARCHAR(36) PRIMARY KEY,
  conversation_id VARCHAR(36) NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
  role            VARCHAR(16) NOT NULL,
  content         TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_messages_conv ON ai_messages(conversation_id);
